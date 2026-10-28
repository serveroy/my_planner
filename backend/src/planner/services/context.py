"""Build the structured inputs the models receive from database state."""

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from planner.config import get_settings
from planner.db.models import ChatMessage, Goal, PlanRevision, User
from planner.lang import detect_language
from planner.llm.contracts import (
    AnswerFormat,
    AvailableTime,
    ChatTurn,
    CoachContext,
    GoalBrief,
    Language,
    PlanOverview,
    PlanOverviewTask,
    QAItem,
    ResponseStyle,
    SafetyFlag,
)
from planner.services import progress
from planner.services.schedule import describe_schedule


def goal_brief(goal: Goal) -> GoalBrief:
    return GoalBrief(
        title=goal.title,
        description=goal.description,
        current_state=goal.current_state,
        deadline=goal.deadline,
        available_time=AvailableTime.model_validate(goal.available_time or {}),
        extra_context=goal.extra_context,
    )


def goal_language(goal: Goal, user: User) -> Language:
    """Language of the goal as the user wrote it; falls back to the UI language."""
    return detect_language(f"{goal.title} {goal.description} {goal.current_state}", default=user.language)  # type: ignore[arg-type]


def response_style(goal: Goal, user: User, text_hint: str | None = None) -> ResponseStyle:
    fmt = AnswerFormat.model_validate(goal.answer_format or {})
    lang = detect_language(text_hint, default=goal_language(goal, user)) if text_hint else goal_language(goal, user)
    return fmt.resolve(lang)


def safety_flags(goal: Goal) -> list[SafetyFlag]:
    return [SafetyFlag.model_validate(f) for f in goal.safety_flags or []]


def qa_history(goal: Goal) -> list[QAItem]:
    return [
        QAItem(question=t.question, field=t.field, answer=t.answer, skipped=t.skipped)
        for t in goal.intake_turns
        if t.answer is not None or t.skipped
    ]


def chat_turns(db: Session, goal: Goal, limit: int | None = None) -> list[ChatTurn]:
    limit = limit or get_settings().chat_context_messages
    rows = db.scalars(
        select(ChatMessage).where(ChatMessage.goal_id == goal.id).order_by(ChatMessage.id.desc()).limit(limit)
    ).all()
    return [ChatTurn(role=r.role, content=r.content) for r in reversed(rows)]  # type: ignore[arg-type]


def pending_revision(db: Session, goal: Goal) -> PlanRevision | None:
    return db.scalar(
        select(PlanRevision)
        .where(PlanRevision.goal_id == goal.id, PlanRevision.status == "pending")
        .order_by(PlanRevision.id.desc())
    )


def coach_context(
    db: Session,
    goal: Goal,
    user: User,
    now_local: datetime,
    *,
    text_hint: str | None = None,
    actions_taken: list[str] | None = None,
) -> CoachContext:
    style = response_style(goal, user, text_hint)
    plan = progress.current_plan(db, goal)
    ctx = CoachContext(
        now=now_local.replace(second=0, microsecond=0),
        user_name=user.display_name,
        style=style,
        goal=goal_brief(goal),
        memory_summary=goal.memory_summary,
        constraints=[c["text"] for c in goal.constraints or []],
        actions_taken=actions_taken or [],
        plan_update_mode=goal.update_mode,  # type: ignore[arg-type]
        safety_flags=safety_flags(goal),
    )
    if pending := pending_revision(db, goal):
        ctx.pending_revision = pending.explanation
    if plan is None:
        return ctx
    today = now_local.date()
    report = progress.progress_report(db, goal, plan, today)
    ctx.plan = PlanOverview(
        title=plan.title,
        summary=plan.summary,
        end_date=plan.end_date,
        milestones=report.milestones,
        tasks=[PlanOverviewTask(id=t.id, title=t.title, schedule=describe_schedule(t, "en")) for t in plan.tasks],
        metrics=report.metrics,
    )
    ctx.today_tasks = progress.today_tasks(db, goal, plan, today)
    ctx.days_left = report.days_left
    ctx.adherence_7d = report.adherence_7d
    ctx.streak_days = report.streak_days
    return ctx
