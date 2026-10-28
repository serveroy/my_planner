"""Plan revisions (planner.revise), applied automatically or after the user approves.

Flow: something triggers a review (chat request, new constraint, low adherence, weekly review)
-> planner.revise returns edit operations -> they are validated by applying them to a copy of the
plan -> stored as a PlanRevision. In "auto" mode it is applied immediately; in "ask" mode the user
gets a proposal message + notification and approves or rejects it.
"""

import logging
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from planner.db.models import ChatMessage, Goal, PlanRevision, User, utcnow
from planner.llm.contracts import Plan, ReviseInput, ReviseOutput, RevisionOp, RevisionTrigger
from planner.llm.gateway import ModelGateway, ModelOutputError, ModelUnavailableError
from planner.services import notifications, progress
from planner.services.context import goal_brief, response_style, safety_flags
from planner.services.plan_ops import InvalidRevisionError, apply_operations
from planner.services.planning import save_version
from planner.services.timeutil import local_today

log = logging.getLogger(__name__)

USER_TRIGGERS = {"user_request", "constraint_change"}
# Automatic reviews of the same kind are not repeated within this period.
COOLDOWN = {
    "low_adherence": timedelta(days=5),
    "behind_schedule": timedelta(days=5),
    "ahead_of_schedule": timedelta(days=7),
    "weekly_review": timedelta(days=6),
}

TITLES = {
    "proposal": {"en": "Suggested plan update", "he": "הצעה לעדכון התוכנית"},
    "applied": {"en": "Your plan was updated", "he": "התוכנית שלך עודכנה"},
}


class RevisionError(ValueError):
    pass


def has_pending(db: Session, goal: Goal) -> bool:
    return db.scalar(
        select(PlanRevision.id).where(PlanRevision.goal_id == goal.id, PlanRevision.status == "pending")
    ) is not None


def _recently_done(db: Session, goal: Goal, trigger: str) -> bool:
    period = COOLDOWN.get(trigger)
    if period is None:
        return False
    since = utcnow() - period
    return db.scalar(
        select(PlanRevision.id).where(
            PlanRevision.goal_id == goal.id, PlanRevision.trigger == trigger, PlanRevision.created_at >= since
        )
    ) is not None


def _ask_planner(gw: ModelGateway, inp: ReviseInput, plan: Plan) -> tuple[ReviseOutput, Plan | None]:
    out = gw.revise_plan(inp)
    if not out.should_revise or not out.operations:
        return out, None
    try:
        return out, apply_operations(plan, out.operations)
    except InvalidRevisionError as e:
        log.warning("revision invalid (%s), asking again", e)
        retry = inp.model_copy(update={"trigger_details": f"{inp.trigger_details}\n\nYour previous operations were invalid: {e}. "
                                                          "Use only existing ids and valid fields."})
        out = gw.revise_plan(retry)
        if not out.should_revise or not out.operations:
            return out, None
        try:
            return out, apply_operations(plan, out.operations)
        except InvalidRevisionError as e2:
            log.warning("revision still invalid: %s", e2)
            return ReviseOutput(should_revise=False, explanation=""), None


def propose(
    db: Session, goal: Goal, user: User, gw: ModelGateway, trigger: RevisionTrigger, details: str = ""
) -> PlanRevision | None:
    plan = progress.current_plan(db, goal)
    if plan is None or goal.status != "active":
        return None
    if trigger not in USER_TRIGGERS and _recently_done(db, goal, trigger):
        return None
    today = local_today(user)
    inp = ReviseInput(
        today=today,
        goal=goal_brief(goal),
        style=response_style(goal, user, details if trigger in USER_TRIGGERS else None),
        plan=plan,
        progress=progress.progress_report(db, goal, plan, today),
        trigger=trigger,
        trigger_details=details,
        constraints=[c["text"] for c in goal.constraints or []],
        memory_summary=goal.memory_summary,
        safety_flags=safety_flags(goal),
    )
    try:
        out, new_plan = _ask_planner(gw, inp, plan)
    except (ModelOutputError, ModelUnavailableError):
        log.exception("planner.revise failed for goal %s", goal.id)
        return None

    if new_plan is None:
        # Nothing to change. Record automatic reviews (for the cooldown); tell the user if they asked.
        db.add(PlanRevision(goal_id=goal.id, base_version=goal.current_plan_version or 0, trigger=trigger,
                            trigger_details=details, explanation=out.explanation, status="no_change"))
        if trigger in USER_TRIGGERS and out.explanation:
            db.add(ChatMessage(goal_id=goal.id, role="assistant", kind="chat", content=out.explanation))
        db.commit()
        return None

    for old in db.scalars(select(PlanRevision).where(PlanRevision.goal_id == goal.id, PlanRevision.status == "pending")):
        old.status, old.decided_at = "superseded", utcnow()
    rev = PlanRevision(
        goal_id=goal.id,
        base_version=goal.current_plan_version or 0,
        trigger=trigger,
        trigger_details=details,
        explanation=out.explanation,
        operations=[op.model_dump(mode="json") for op in out.operations],
        status="pending",
    )
    db.add(rev)
    db.flush()
    lang = inp.style.language
    if goal.update_mode == "auto":
        _apply(db, goal, rev, new_plan)
        msg = ChatMessage(goal_id=goal.id, role="assistant", kind="revision_applied", content=out.explanation,
                          meta={"revision_id": rev.id, "version": rev.new_version})
        kind = "applied"
    else:
        msg = ChatMessage(goal_id=goal.id, role="assistant", kind="revision_proposal", content=out.explanation,
                          meta={"revision_id": rev.id})
        kind = "proposal"
    db.add(msg)
    db.flush()
    notifications.notify(db, user.id, goal.id, f"revision_{kind}", TITLES[kind][lang], out.explanation,
                         {"revision_id": rev.id, "message_id": msg.id})
    db.commit()
    return rev


def _apply(db: Session, goal: Goal, rev: PlanRevision, new_plan: Plan) -> None:
    version = save_version(db, goal, new_plan, "revision", revision_id=rev.id)
    rev.status, rev.new_version, rev.decided_at = "applied", version.version, utcnow()


def approve(db: Session, goal: Goal, rev: PlanRevision) -> PlanRevision:
    if rev.status != "pending":
        raise RevisionError(f"revision is {rev.status}")
    plan = progress.current_plan(db, goal)
    if plan is None:
        raise RevisionError("goal has no plan")
    try:
        # If the plan changed since the proposal, the operations must still apply cleanly.
        new_plan = apply_operations(plan, [RevisionOp.model_validate(op) for op in rev.operations])
    except InvalidRevisionError as e:
        rev.status, rev.decided_at = "superseded", utcnow()
        db.commit()
        raise RevisionError(f"the plan changed and this proposal no longer applies: {e}") from e
    _apply(db, goal, rev, new_plan)
    _resolve_proposal_message(db, rev, "approved")
    db.commit()
    return rev


def reject(db: Session, goal: Goal, rev: PlanRevision) -> PlanRevision:
    if rev.status != "pending":
        raise RevisionError(f"revision is {rev.status}")
    rev.status, rev.decided_at = "rejected", utcnow()
    _resolve_proposal_message(db, rev, "rejected")
    db.commit()
    return rev


def _resolve_proposal_message(db: Session, rev: PlanRevision, decision: str) -> None:
    for msg in db.scalars(select(ChatMessage).where(ChatMessage.goal_id == rev.goal_id, ChatMessage.kind == "revision_proposal")):
        if msg.meta.get("revision_id") == rev.id:
            msg.meta = {**msg.meta, "decision": decision}
