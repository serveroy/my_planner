"""Proactive check-ins and automatic plan reviews.

Rules decide *when* and *why* to reach out (trigger); coach.checkin writes *what* to say.
``tick()`` runs every few minutes from a background thread (and on demand via /dev/tick).
"""

import logging
import threading
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from planner.config import get_settings
from planner.db.models import ChatMessage, CheckinLog, Goal, PlanRevision, User, utcnow
from planner.llm.contracts import CheckinInput, CheckinSettings, CheckinTrigger, Plan, ProgressReport
from planner.llm.gateway import ModelGateway, ModelOutputError, ModelUnavailableError
from planner.services import notifications, progress, revisions
from planner.services.context import chat_turns, coach_context
from planner.services.schedule import tasks_due_on
from planner.services.timeutil import local_now, parse_hhmm

log = logging.getLogger(__name__)


@dataclass
class Trigger:
    type: CheckinTrigger
    details: str
    dedupe_key: str


def _naive_utc(now_utc: datetime | None) -> datetime:
    if now_utc is None:
        return utcnow()
    return now_utc.astimezone(timezone.utc).replace(tzinfo=None) if now_utc.tzinfo else now_utc


def _in_quiet_hours(now: time, cfg: CheckinSettings) -> bool:
    start, end = time(*parse_hhmm(cfg.quiet_start)), time(*parse_hhmm(cfg.quiet_end))
    if start <= end:
        return start <= now < end
    return now >= start or now < end


def _sent_today(db: Session, goal: Goal, today: date) -> int:
    return db.scalar(
        select(func.count(CheckinLog.id)).where(CheckinLog.goal_id == goal.id, CheckinLog.local_date == today)
    ) or 0


def _already_sent(db: Session, goal: Goal, key: str) -> bool:
    return db.scalar(select(CheckinLog.id).where(CheckinLog.goal_id == goal.id, CheckinLog.dedupe_key == key)) is not None


def _daily_trigger(db: Session, goal: Goal, plan: Plan, today: date) -> Trigger | None:
    due = progress.today_tasks(db, goal, plan, today)
    if not due:
        return None
    if all(t.status == "done" for t in due):
        return Trigger("all_done", "", f"all_done:{today}")
    pending = [t.title for t in due if t.status == "pending"]
    if pending:
        return Trigger("daily_tasks", ", ".join(pending), f"daily:{today}")
    return None


def _daytime_triggers(
    db: Session, goal: Goal, plan: Plan, report: ProgressReport, cfg: CheckinSettings, now: datetime, ref_utc: datetime
) -> list[Trigger]:
    today = now.date()
    out: list[Trigger] = []

    yesterday = today - timedelta(days=1)
    if yesterday >= plan.start_date and now.hour < 12:
        due = tasks_due_on(plan, yesterday)
        logs = progress.task_logs(db, goal, yesterday, yesterday)
        if due and not any((t.id, yesterday) in logs for t in due):
            out.append(Trigger("missed_yesterday", ", ".join(t.title for t in due), f"missed:{yesterday}"))

    for m in report.milestones:
        if m.status == "due_soon" and m.target_date >= today:
            out.append(Trigger("milestone_upcoming", f"{m.title} ({m.target_date:%d/%m})", f"milestone:{m.id}"))

    if 0 < report.days_left <= 7:
        out.append(Trigger("deadline_near", str(report.days_left), "deadline_near"))

    last_active = goal.last_user_activity_at or goal.created_at
    if ref_utc - last_active >= timedelta(days=cfg.inactivity_days):
        # At most one re-engagement message per inactivity period.
        period = (today - plan.start_date).days // cfg.inactivity_days
        out.append(Trigger("inactivity", "", f"inactive:{period}"))

    if (today - plan.start_date).days >= 3:
        for m in report.metrics:
            if m.latest_date is None or (today - m.latest_date).days >= 7:
                week = today.isocalendar()
                out.append(Trigger("metric_reminder", m.name, f"metric:{m.key}:{week.year}-{week.week}"))
    return out


def evaluate(db: Session, goal: Goal, user: User, now_utc: datetime | None = None) -> Trigger | None:
    """Pick at most one check-in to send now, or None."""
    cfg = CheckinSettings.model_validate(goal.checkin_settings or {})
    if not cfg.enabled or goal.status != "active":
        return None
    now = local_now(user, now_utc)
    ref_utc = _naive_utc(now_utc)
    if _in_quiet_hours(now.time(), cfg):
        return None
    plan = progress.current_plan(db, goal)
    if plan is None or not (plan.start_date <= now.date() <= plan.end_date + timedelta(days=1)):
        return None
    if goal.last_user_activity_at and timedelta(0) <= ref_utc - goal.last_user_activity_at < timedelta(minutes=15):
        return None  # the user is in the app right now; don't interrupt
    sent = _sent_today(db, goal, now.date())
    if sent >= cfg.max_per_day:
        return None

    daily_at = time(*parse_hhmm(cfg.daily_time))
    if now.time() >= daily_at:
        trig = _daily_trigger(db, goal, plan, now.date())
        if trig and not _already_sent(db, goal, trig.dedupe_key):
            return trig
    # Keep one slot free for the evening check-in on days with tasks.
    has_tasks_today = bool(tasks_due_on(plan, now.date()))
    if has_tasks_today and now.time() < daily_at and sent >= cfg.max_per_day - 1:
        return None
    report = progress.progress_report(db, goal, plan, now.date())
    for trig in _daytime_triggers(db, goal, plan, report, cfg, now, ref_utc):
        if not _already_sent(db, goal, trig.dedupe_key):
            return trig
    return None


def send(db: Session, goal: Goal, user: User, gw: ModelGateway, trig: Trigger, now_utc: datetime | None = None) -> ChatMessage | None:
    now = local_now(user, now_utc)
    ctx = coach_context(db, goal, user, now)
    try:
        text = gw.checkin(CheckinInput(
            context=ctx, trigger=trig.type, trigger_details=trig.details, recent_messages=chat_turns(db, goal, 6)
        ))
    except (ModelOutputError, ModelUnavailableError):
        log.exception("coach.checkin failed for goal %s", goal.id)
        return None
    msg = ChatMessage(goal_id=goal.id, role="assistant", kind="checkin", content=text, meta={"trigger": trig.type})
    db.add(msg)
    db.flush()
    db.add(CheckinLog(goal_id=goal.id, trigger=trig.type, local_date=now.date(), dedupe_key=trig.dedupe_key, message_id=msg.id))
    notifications.notify(db, user.id, goal.id, "checkin", goal.title, text, {"message_id": msg.id, "trigger": trig.type})
    db.commit()
    return msg


def review_trigger(db: Session, goal: Goal, plan: Plan, today: date, ref_utc: datetime) -> tuple[str, str] | None:
    """Decide whether the planner should take an automatic look at the plan."""
    report = progress.progress_report(db, goal, plan, today)
    due_recent = sum(t.due for t in report.tasks)
    if report.days_elapsed >= 7 and report.adherence_7d is not None and report.adherence_7d < 0.4 and due_recent >= 3:
        return "low_adherence", f"Only {round(report.adherence_7d * 100)}% of last week's sessions were done."
    for m in report.metrics:
        if None in (m.latest, m.expected_now, m.baseline, m.target) or m.target == m.baseline:
            continue
        span = abs(m.target - m.baseline)  # type: ignore[operator]
        sign = -1 if m.direction == "decrease" else 1
        lead = sign * (m.latest - m.expected_now)  # type: ignore[operator]
        if lead < -0.15 * span and report.days_elapsed >= 14:
            return "behind_schedule", f"{m.name} is {m.latest} vs. {m.expected_now} expected by now."
        if lead > 0.2 * span and report.days_elapsed >= 14:
            return "ahead_of_schedule", f"{m.name} is {m.latest}, ahead of the {m.expected_now} expected by now."
    if report.days_elapsed >= 7:
        last = db.scalar(select(func.max(PlanRevision.created_at)).where(PlanRevision.goal_id == goal.id))
        if last is None or ref_utc - last >= timedelta(days=7):
            return "weekly_review", "Scheduled weekly review."
    return None


def tick(gw: ModelGateway, session_factory, now_utc: datetime | None = None, user_id: int | None = None) -> dict[str, int]:
    """One scheduler pass over all active goals (or only one user's, for the dev endpoint)."""
    stats = {"checkins": 0, "reviews": 0}
    with session_factory() as db:
        q = select(Goal.id).where(Goal.status == "active")
        if user_id is not None:
            q = q.where(Goal.user_id == user_id)
        goal_ids = db.scalars(q).all()
    for goal_id in goal_ids:
        with session_factory() as db:
            goal = db.get(Goal, goal_id)
            if goal is None:
                continue
            user = goal.user
            try:
                if (trig := evaluate(db, goal, user, now_utc)) and send(db, goal, user, gw, trig, now_utc):
                    stats["checkins"] += 1
                now = local_now(user, now_utc)
                cfg = CheckinSettings.model_validate(goal.checkin_settings or {})
                plan = progress.current_plan(db, goal)
                if plan and not _in_quiet_hours(now.time(), cfg) and not revisions.has_pending(db, goal):
                    if review := review_trigger(db, goal, plan, now.date(), _naive_utc(now_utc)):
                        if revisions.propose(db, goal, user, gw, review[0], review[1]):  # type: ignore[arg-type]
                            stats["reviews"] += 1
            except Exception:
                db.rollback()
                log.exception("scheduler failed for goal %s", goal_id)
    return stats


class Scheduler:
    def __init__(self, gw: ModelGateway, session_factory, interval_seconds: int | None = None) -> None:
        self.gw = gw
        self.session_factory = session_factory
        self.interval = interval_seconds or get_settings().scheduler_interval_seconds
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        self._thread = threading.Thread(target=self._run, name="checkin-scheduler", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()

    def _run(self) -> None:
        while not self._stop.wait(self.interval):
            try:
                tick(self.gw, self.session_factory)
            except Exception:
                log.exception("scheduler tick failed")
