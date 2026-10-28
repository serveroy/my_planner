from datetime import date

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from planner.api.deps import current_user, gateway, owned_goal
from planner.api.schemas import (
    AnswerIn,
    ChatIn,
    ChatMessageOut,
    ChatOut,
    GoalCreate,
    GoalOut,
    GoalPatch,
    IntakeStateOut,
    IntakeTurnOut,
    MetricLogIn,
    MetricPoint,
    PlanOut,
    PlanVersionOut,
    ProgressOut,
    RevisionOut,
    RevisionRequestIn,
    TaskLogIn,
    TodayOut,
)
from planner.config import get_settings
from planner.db.models import ChatMessage, Goal, Notification, PlanRevision, PlanVersion, User, utcnow
from planner.db.session import get_db, new_session
from planner.llm.contracts import Plan, RevisionOp
from planner.llm.gateway import ModelGateway
from planner.services import coach, intake, planning, progress, revisions
from planner.services.context import pending_revision
from planner.services.plan_ops import describe_operation
from planner.services.timeutil import local_today

router = APIRouter(prefix="/goals", tags=["goals"])


def _goal_out(db: Session, goal: Goal) -> GoalOut:
    out = GoalOut.model_validate(goal)
    out.has_pending_revision = pending_revision(db, goal) is not None
    out.unread_notifications = db.scalar(
        select(func.count(Notification.id)).where(Notification.goal_id == goal.id, Notification.read_at.is_(None))
    ) or 0
    return out


def _require_plan(db: Session, goal: Goal) -> Plan:
    plan = progress.current_plan(db, goal)
    if plan is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "this goal has no plan yet")
    return plan


# ---- goals ------------------------------------------------------------------------------------


@router.get("", response_model=list[GoalOut])
def list_goals(user: User = Depends(current_user), db: Session = Depends(get_db)):
    goals = db.scalars(
        select(Goal).where(Goal.user_id == user.id, Goal.status != "archived").order_by(Goal.created_at.desc())
    ).all()
    return [_goal_out(db, g) for g in goals]


@router.post("", response_model=GoalOut, status_code=201)
def create_goal(body: GoalCreate, user: User = Depends(current_user), db: Session = Depends(get_db),
                gw: ModelGateway = Depends(gateway)):
    if body.deadline <= local_today(user):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "deadline must be in the future")
    goal = Goal(user_id=user.id, **body.model_dump(mode="json") | {"deadline": body.deadline})
    db.add(goal)
    db.commit()
    intake.advance(db, goal, user, gw)  # prepare the first question
    return _goal_out(db, goal)


@router.get("/{goal_id}", response_model=GoalOut)
def get_goal(goal: Goal = Depends(owned_goal), db: Session = Depends(get_db)):
    return _goal_out(db, goal)


@router.patch("/{goal_id}", response_model=GoalOut)
def update_goal(body: GoalPatch, goal: Goal = Depends(owned_goal), db: Session = Depends(get_db)):
    if body.status and goal.current_plan_version is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "the goal has no plan yet")
    for k, v in body.model_dump(mode="json", exclude_none=True).items():
        setattr(goal, k, date.fromisoformat(v) if k == "deadline" else v)
    db.commit()
    return _goal_out(db, goal)


@router.delete("/{goal_id}", status_code=204)
def delete_goal(goal: Goal = Depends(owned_goal), db: Session = Depends(get_db)):
    db.delete(goal)
    db.commit()


# ---- intake -----------------------------------------------------------------------------------


def _intake_state(goal: Goal) -> IntakeStateOut:
    current = intake.current_turn(goal) if goal.status == "intake" else None
    return IntakeStateOut(
        status="in_progress" if goal.status == "intake" else "finished",
        current=IntakeTurnOut.model_validate(current) if current else None,
        history=[IntakeTurnOut.model_validate(t) for t in goal.intake_turns if t is not current],
        summary=goal.intake_summary,
        max_questions=get_settings().intake_max_questions,
    )


@router.get("/{goal_id}/intake", response_model=IntakeStateOut)
def get_intake(goal: Goal = Depends(owned_goal), user: User = Depends(current_user), db: Session = Depends(get_db),
               gw: ModelGateway = Depends(gateway)):
    intake.advance(db, goal, user, gw)
    return _intake_state(goal)


@router.post("/{goal_id}/intake/answer", response_model=IntakeStateOut)
def answer_intake(body: AnswerIn, goal: Goal = Depends(owned_goal), user: User = Depends(current_user),
                  db: Session = Depends(get_db), gw: ModelGateway = Depends(gateway)):
    try:
        intake.answer(db, goal, user, gw, body.turn_id, body.answer, skip=body.skip)
    except intake.IntakeError as e:
        raise HTTPException(status.HTTP_409_CONFLICT, str(e)) from e
    return _intake_state(goal)


@router.post("/{goal_id}/intake/finish", response_model=IntakeStateOut)
def finish_intake(goal: Goal = Depends(owned_goal), user: User = Depends(current_user), db: Session = Depends(get_db),
                  gw: ModelGateway = Depends(gateway)):
    intake.finish_now(db, goal, user, gw)
    return _intake_state(goal)


# ---- plan -------------------------------------------------------------------------------------


@router.post("/{goal_id}/plan/generate", response_model=PlanOut)
def generate_plan(goal: Goal = Depends(owned_goal), user: User = Depends(current_user), db: Session = Depends(get_db),
                  gw: ModelGateway = Depends(gateway)):
    try:
        version, warnings = planning.generate(db, goal, user, gw)
    except planning.PlanningError as e:
        raise HTTPException(status.HTTP_409_CONFLICT, str(e)) from e
    return PlanOut(version=version.version, source=version.source, created_at=version.created_at,
                   plan=Plan.model_validate(version.content), warnings=warnings)


@router.get("/{goal_id}/plan", response_model=PlanOut)
def get_plan(goal: Goal = Depends(owned_goal), db: Session = Depends(get_db), version: int | None = None):
    v = version or goal.current_plan_version
    row = db.scalar(select(PlanVersion).where(PlanVersion.goal_id == goal.id, PlanVersion.version == v)) if v else None
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "no plan")
    return PlanOut(version=row.version, source=row.source, created_at=row.created_at, plan=Plan.model_validate(row.content))


@router.get("/{goal_id}/plan/versions", response_model=list[PlanVersionOut])
def plan_versions(goal: Goal = Depends(owned_goal), db: Session = Depends(get_db)):
    return db.scalars(select(PlanVersion).where(PlanVersion.goal_id == goal.id).order_by(PlanVersion.version.desc())).all()


# ---- daily tasks & progress -------------------------------------------------------------------


@router.get("/{goal_id}/today", response_model=TodayOut)
def today(goal: Goal = Depends(owned_goal), user: User = Depends(current_user), db: Session = Depends(get_db),
          day: date | None = Query(None, alias="date")):
    plan = _require_plan(db, goal)
    day = day or local_today(user)
    return TodayOut(date=day, tasks=progress.today_tasks(db, goal, plan, day))


@router.post("/{goal_id}/tasks/{task_id}/log", response_model=TodayOut)
def log_task(task_id: str, body: TaskLogIn, goal: Goal = Depends(owned_goal), user: User = Depends(current_user),
             db: Session = Depends(get_db)):
    plan = _require_plan(db, goal)
    if task_id not in {t.id for t in plan.tasks}:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "task not found")
    if body.date > local_today(user):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "cannot log a future day")
    if body.status == "pending":
        progress.clear_task_log(db, goal, task_id, body.date)
    else:
        progress.log_task(db, goal, task_id, body.date, body.status, body.note)
    goal.last_user_activity_at = utcnow()
    db.commit()
    return TodayOut(date=body.date, tasks=progress.today_tasks(db, goal, plan, body.date))


@router.post("/{goal_id}/metrics/{key}/log", response_model=ProgressOut)
def log_metric(key: str, body: MetricLogIn, goal: Goal = Depends(owned_goal), user: User = Depends(current_user),
               db: Session = Depends(get_db)):
    plan = _require_plan(db, goal)
    if key not in {m.key for m in plan.metrics}:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "metric not found")
    progress.log_metric(db, goal, key, body.value, body.date or local_today(user), body.note)
    db.commit()
    return get_progress(goal, user, db)


@router.get("/{goal_id}/progress", response_model=ProgressOut)
def get_progress(goal: Goal = Depends(owned_goal), user: User = Depends(current_user), db: Session = Depends(get_db)):
    plan = _require_plan(db, goal)
    history: dict[str, list[MetricPoint]] = {}
    for row in progress.metric_history(db, goal):
        history.setdefault(row.metric_key, []).append(MetricPoint(date=row.date, value=row.value))
    return ProgressOut(report=progress.progress_report(db, goal, plan, local_today(user)), metric_history=history)


# ---- revisions --------------------------------------------------------------------------------


def _revision_out(db: Session, goal: Goal, rev: PlanRevision) -> RevisionOut:
    out = RevisionOut.model_validate(rev)
    base = db.scalar(select(PlanVersion).where(PlanVersion.goal_id == goal.id, PlanVersion.version == rev.base_version))
    if base:
        plan = Plan.model_validate(base.content)
        out.changes = [describe_operation(RevisionOp.model_validate(op), plan) for op in rev.operations]
    return out


@router.get("/{goal_id}/revisions", response_model=list[RevisionOut])
def list_revisions(goal: Goal = Depends(owned_goal), db: Session = Depends(get_db)):
    rows = db.scalars(
        select(PlanRevision).where(PlanRevision.goal_id == goal.id, PlanRevision.status != "no_change")
        .order_by(PlanRevision.id.desc())
    ).all()
    return [_revision_out(db, goal, r) for r in rows]


@router.post("/{goal_id}/revisions/request", response_model=RevisionOut | None)
def request_revision(body: RevisionRequestIn, goal: Goal = Depends(owned_goal), user: User = Depends(current_user),
                     db: Session = Depends(get_db), gw: ModelGateway = Depends(gateway)):
    _require_plan(db, goal)
    rev = revisions.propose(db, goal, user, gw, "user_request", body.message)
    return _revision_out(db, goal, rev) if rev else None


def _get_revision(db: Session, goal: Goal, rev_id: int) -> PlanRevision:
    rev = db.get(PlanRevision, rev_id)
    if rev is None or rev.goal_id != goal.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "revision not found")
    return rev


@router.post("/{goal_id}/revisions/{rev_id}/approve", response_model=RevisionOut)
def approve_revision(rev_id: int, goal: Goal = Depends(owned_goal), db: Session = Depends(get_db)):
    rev = _get_revision(db, goal, rev_id)
    try:
        revisions.approve(db, goal, rev)
    except revisions.RevisionError as e:
        raise HTTPException(status.HTTP_409_CONFLICT, str(e)) from e
    return _revision_out(db, goal, rev)


@router.post("/{goal_id}/revisions/{rev_id}/reject", response_model=RevisionOut)
def reject_revision(rev_id: int, goal: Goal = Depends(owned_goal), db: Session = Depends(get_db)):
    rev = _get_revision(db, goal, rev_id)
    try:
        revisions.reject(db, goal, rev)
    except revisions.RevisionError as e:
        raise HTTPException(status.HTTP_409_CONFLICT, str(e)) from e
    return _revision_out(db, goal, rev)


# ---- chat -------------------------------------------------------------------------------------


@router.get("/{goal_id}/chat", response_model=list[ChatMessageOut])
def list_messages(goal: Goal = Depends(owned_goal), db: Session = Depends(get_db),
                  after_id: int = 0, limit: int = Query(100, le=500)):
    rows = db.scalars(
        select(ChatMessage).where(ChatMessage.goal_id == goal.id, ChatMessage.id > after_id)
        .order_by(ChatMessage.id.desc()).limit(limit)
    ).all()
    return list(reversed(rows))


def _after_chat(goal_id: int, revision: coach.RevisionRequest | None, gw: ModelGateway) -> None:
    """Slow follow-ups of a chat message, run after the response is sent."""
    with new_session() as db:
        goal = db.get(Goal, goal_id)
        if goal is None:
            return
        if revision:
            revisions.propose(db, goal, goal.user, gw, revision.trigger, revision.details)
        coach.maybe_summarize(db, goal, gw)


@router.post("/{goal_id}/chat", response_model=ChatOut)
def send_message(body: ChatIn, background: BackgroundTasks, goal: Goal = Depends(owned_goal),
                 user: User = Depends(current_user), db: Session = Depends(get_db), gw: ModelGateway = Depends(gateway)):
    if goal.status == "intake":
        raise HTTPException(status.HTTP_409_CONFLICT, "finish the intake first")
    result = coach.handle_user_message(db, goal, user, gw, body.content.strip())
    background.add_task(_after_chat, goal.id, result.revision, gw)
    return ChatOut(
        user_message=ChatMessageOut.model_validate(result.user_message),
        reply=ChatMessageOut.model_validate(result.reply),
        actions=result.actions,
        revision_in_progress=result.revision is not None,
    )
