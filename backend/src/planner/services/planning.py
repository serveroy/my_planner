"""Plan generation (planner.generate) and plan version storage."""

import logging

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from planner.db.models import ChatMessage, Goal, PlanVersion, User
from planner.llm.contracts import CheckinInput, GenerateInput, Plan
from planner.llm.gateway import ModelGateway, ModelOutputError, ModelUnavailableError
from planner.services import notifications, safety
from planner.services.context import coach_context, goal_brief, qa_history, response_style, safety_flags
from planner.services.timeutil import local_now, local_today

log = logging.getLogger(__name__)


class PlanningError(ValueError):
    pass


def save_version(db: Session, goal: Goal, plan: Plan, source: str, revision_id: int | None = None) -> PlanVersion:
    latest = db.scalar(select(func.max(PlanVersion.version)).where(PlanVersion.goal_id == goal.id)) or 0
    row = PlanVersion(
        goal_id=goal.id, version=latest + 1, content=plan.model_dump(mode="json"), source=source, revision_id=revision_id
    )
    db.add(row)
    goal.current_plan_version = row.version
    return row


def _normalize(plan: Plan, goal: Goal, user: User) -> Plan:
    """Clamp model output to the goal's real dates; models sometimes drift."""
    today = local_today(user)
    doc = plan.model_dump(mode="json")
    if plan.start_date < today:
        doc["start_date"] = today.isoformat()
    if plan.end_date > goal.deadline:
        doc["end_date"] = goal.deadline.isoformat()
    if doc["end_date"] < doc["start_date"]:
        doc["end_date"] = doc["start_date"]
    return Plan.model_validate(doc)


def generate(db: Session, goal: Goal, user: User, gw: ModelGateway) -> tuple[PlanVersion, list[str]]:
    if goal.status not in ("planning", "active"):
        raise PlanningError("finish the intake interview first")
    inp = GenerateInput(
        today=local_today(user),
        goal=goal_brief(goal),
        style=response_style(goal, user),
        profile=goal.profile or {},
        intake_summary=goal.intake_summary,
        qa_history=qa_history(goal),
        safety_flags=safety_flags(goal),
    )
    plan = _normalize(gw.generate_plan(inp), goal, user)
    warnings = safety.check_plan(plan, inp.goal.available_time.minutes_per_day)
    if warnings:
        log.info("plan warnings for goal %s: %s", goal.id, warnings)
    first_plan = goal.current_plan_version is None
    version = save_version(db, goal, plan, "generated")
    goal.status = "active"
    db.flush()

    if first_plan:
        _welcome(db, goal, user, gw)
    db.commit()
    return version, warnings


def _welcome(db: Session, goal: Goal, user: User, gw: ModelGateway) -> None:
    """Coach opens the conversation once the first plan exists."""
    ctx = coach_context(db, goal, user, local_now(user))
    try:
        text = gw.checkin(CheckinInput(context=ctx, trigger="plan_ready"))
    except (ModelOutputError, ModelUnavailableError):
        return
    msg = ChatMessage(goal_id=goal.id, role="assistant", kind="plan_ready", content=text)
    db.add(msg)
    db.flush()
    notifications.notify(db, user.id, goal.id, "plan_ready", goal.title, text, {"message_id": msg.id})
