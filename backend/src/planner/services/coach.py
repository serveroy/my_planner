"""The in-app coach chat.

For each user message:
1. rule-based crisis check (fixed, safe response; no model involved)
2. coach.extract finds events (task done, weight logged, new constraint, change request, mood...)
3. the app applies them (task/metric logs, constraints, safety flags) and records what it did
4. coach.chat writes the reply, knowing what the app just did
5. in the background: planner.revise if the user asked for a change, and memory summarization
"""

import logging
from dataclasses import dataclass, field
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from planner.config import get_settings
from planner.db.models import ChatMessage, Goal, User, utcnow
from planner.lang import PY_WEEKDAYS, detect_language
from planner.llm.contracts import (
    ChatTurn,
    CoachChatInput,
    ExtractedEvent,
    ExtractInput,
    ExtractMetric,
    ExtractTask,
    Language,
    Plan,
    RevisionTrigger,
    SafetyFlag,
    SummarizeInput,
)
from planner.llm.gateway import ModelGateway, ModelOutputError, ModelUnavailableError
from planner.services import progress, safety
from planner.services.context import chat_turns, coach_context
from planner.services.schedule import tasks_due_on
from planner.services.timeutil import local_now

log = logging.getLogger(__name__)

FALLBACK_REPLY = {
    "en": "Sorry, I'm having trouble answering right now. Your message is saved — please try again in a moment.",
    "he": "סליחה, יש לי בעיה לענות כרגע. ההודעה שלך נשמרה — נסה/י שוב בעוד רגע.",
}


@dataclass
class RevisionRequest:
    trigger: RevisionTrigger
    details: str


@dataclass
class ChatResult:
    user_message: ChatMessage
    reply: ChatMessage
    actions: list[str] = field(default_factory=list)
    revision: RevisionRequest | None = None


def _status_words(status: str, lang: Language) -> str:
    return {
        "done": {"en": "done", "he": "בוצע"},
        "partial": {"en": "partly done", "he": "בוצע חלקית"},
        "skipped": {"en": "skipped", "he": "דולג"},
    }[status][lang]


def apply_events(
    db: Session, goal: Goal, plan: Plan | None, events: list[ExtractedEvent], today, lang: Language, message: str
) -> tuple[list[str], RevisionRequest | None]:
    """Turn extracted events into database changes. Returns human-readable actions + revision request."""
    actions: list[str] = []
    revision: RevisionRequest | None = None
    tasks = {t.id: t for t in plan.tasks} if plan else {}
    metrics = {m.key: m for m in plan.metrics} if plan else {}

    for ev in events:
        if ev.type in ("task_done", "task_partial", "task_skipped") and ev.task_id in tasks and plan:
            day = ev.date or today
            if not (max(plan.start_date, today - timedelta(days=7)) <= day <= today):
                continue  # ignore implausible dates (future, or more than a week ago)
            status = ev.type.removeprefix("task_")
            progress.log_task(db, goal, ev.task_id, day, status, source="chat")  # type: ignore[arg-type]
            when = "" if day == today else f" ({day:%d/%m})"
            title = tasks[ev.task_id].title
            actions.append(f"סימנתי את '{title}' כ{_status_words(status, lang)}{when}" if lang == "he"
                           else f"marked '{title}' as {_status_words(status, lang)}{when}")
        elif ev.type == "metric_value" and ev.metric_key in metrics and ev.value is not None:
            day = ev.date if ev.date and ev.date <= today else today
            progress.log_metric(db, goal, ev.metric_key, ev.value, day, source="chat")  # type: ignore[arg-type]
            m = metrics[ev.metric_key]  # type: ignore[index]
            actions.append(f"רשמתי {m.name}: {ev.value:g} {m.unit}".strip() if lang == "he"
                           else f"logged {m.name}: {ev.value:g} {m.unit}".strip())
        elif ev.type == "constraint" and ev.text:
            known = {c["text"] for c in goal.constraints or []}
            if ev.text not in known:
                goal.constraints = (goal.constraints or []) + [{"text": ev.text, "since": today.isoformat()}]
            revision = revision or RevisionRequest("constraint_change", f"{ev.text}\nUser's words: {message}")
        elif ev.type == "plan_change_request":
            revision = RevisionRequest("user_request", f"{ev.text or ''}\nUser's words: {message}")
        elif ev.type == "safety_concern":
            goal.safety_flags = safety.merge_flags(goal.safety_flags or [], [SafetyFlag(
                code="user_reported_concern", severity="caution",
                guidance=f"The user mentioned: {ev.text or 'a health or safety concern'}. Check in with care, "
                         "do not push intensity, and suggest professional advice when relevant.",
            )])
    return actions, revision


def _extract(gw: ModelGateway, plan: Plan | None, today, history: list[ChatTurn], text: str) -> list[ExtractedEvent]:
    due = {t.id for t in tasks_due_on(plan, today)} if plan else set()
    inp = ExtractInput(
        today=today,
        weekday=PY_WEEKDAYS[today.weekday()],
        tasks=[ExtractTask(id=t.id, title=t.title, due_today=t.id in due) for t in plan.tasks] if plan else [],
        metrics=[ExtractMetric(key=m.key, name=m.name, unit=m.unit) for m in plan.metrics] if plan else [],
        recent_messages=history[-4:],
        message=text,
    )
    try:
        return gw.extract(inp).events
    except (ModelOutputError, ModelUnavailableError):
        log.exception("coach.extract failed; continuing without events")
        return []


def handle_user_message(db: Session, goal: Goal, user: User, gw: ModelGateway, text: str) -> ChatResult:
    now = local_now(user)
    lang: Language = detect_language(text, default=user.language)  # type: ignore[arg-type]
    history = chat_turns(db, goal)
    user_msg = ChatMessage(goal_id=goal.id, role="user", kind="chat", content=text)
    db.add(user_msg)
    goal.last_user_activity_at = utcnow()

    if safety.detect_crisis(text):
        goal.safety_flags = safety.merge_flags(goal.safety_flags or [], [safety.crisis_flag()])
        reply = ChatMessage(goal_id=goal.id, role="assistant", kind="safety", content=safety.crisis_response(lang))
        db.add(reply)
        db.commit()
        return ChatResult(user_message=user_msg, reply=reply)

    plan = progress.current_plan(db, goal)
    events = _extract(gw, plan, now.date(), history, text)
    actions, revision = apply_events(db, goal, plan, events, now.date(), lang, text)
    user_msg.meta = {"events": [e.model_dump(mode="json", exclude_none=True) for e in events]}
    db.flush()

    ctx = coach_context(db, goal, user, now, text_hint=text, actions_taken=actions)
    ctx.revision_in_progress = revision is not None
    turns = history + [ChatTurn(role="user", content=text)]
    try:
        content = gw.chat(CoachChatInput(context=ctx, messages=turns))
    except (ModelOutputError, ModelUnavailableError):
        log.exception("coach.chat failed")
        content = FALLBACK_REPLY[lang]
    reply = ChatMessage(goal_id=goal.id, role="assistant", kind="chat", content=content, meta={"actions": actions})
    db.add(reply)
    db.commit()
    return ChatResult(user_message=user_msg, reply=reply, actions=actions, revision=revision)


def maybe_summarize(db: Session, goal: Goal, gw: ModelGateway) -> bool:
    """Fold old messages into goal.memory_summary once enough have accumulated."""
    s = get_settings()
    rows = db.scalars(
        select(ChatMessage).where(ChatMessage.goal_id == goal.id, ChatMessage.id > goal.memory_cursor).order_by(ChatMessage.id)
    ).all()
    if len(rows) < s.summary_every_n_messages + s.chat_context_messages:
        return False
    old = rows[: -s.chat_context_messages]
    try:
        summary = gw.summarize(SummarizeInput(
            goal_title=goal.title,
            previous_summary=goal.memory_summary,
            messages=[ChatTurn(role=r.role, content=r.content) for r in old],  # type: ignore[arg-type]
        ))
    except (ModelOutputError, ModelUnavailableError):
        log.exception("coach.summarize failed")
        return False
    goal.memory_summary, goal.memory_cursor = summary, old[-1].id
    db.commit()
    return True
