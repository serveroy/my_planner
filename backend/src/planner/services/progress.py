"""Progress tracking: task/metric logs, adherence, streaks and milestone status."""

from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from planner.db.models import Goal, MetricLog, PlanVersion, TaskLog
from planner.llm.contracts import (
    MetricProgress,
    MilestoneStatus,
    Plan,
    ProgressReport,
    TaskProgress,
    TodayTask,
)
from planner.services.schedule import is_due, tasks_due_on


def current_plan(db: Session, goal: Goal) -> Plan | None:
    if goal.current_plan_version is None:
        return None
    row = db.scalar(
        select(PlanVersion).where(PlanVersion.goal_id == goal.id, PlanVersion.version == goal.current_plan_version)
    )
    return Plan.model_validate(row.content) if row else None


def task_logs(db: Session, goal: Goal, start: date, end: date) -> dict[tuple[str, date], TaskLog]:
    rows = db.scalars(
        select(TaskLog).where(TaskLog.goal_id == goal.id, TaskLog.date >= start, TaskLog.date <= end)
    ).all()
    return {(r.task_id, r.date): r for r in rows}


def log_task(db: Session, goal: Goal, task_id: str, day: date, status: str, note: str = "", source: str = "user") -> TaskLog:
    row = db.scalar(select(TaskLog).where(TaskLog.goal_id == goal.id, TaskLog.task_id == task_id, TaskLog.date == day))
    if row is None:
        row = TaskLog(goal_id=goal.id, task_id=task_id, date=day, status=status, note=note, source=source)
        db.add(row)
    else:
        row.status, row.source = status, source
        if note:
            row.note = note
    return row


def clear_task_log(db: Session, goal: Goal, task_id: str, day: date) -> None:
    row = db.scalar(select(TaskLog).where(TaskLog.goal_id == goal.id, TaskLog.task_id == task_id, TaskLog.date == day))
    if row is not None:
        db.delete(row)


def log_metric(db: Session, goal: Goal, key: str, value: float, day: date, note: str = "", source: str = "user") -> MetricLog:
    row = MetricLog(goal_id=goal.id, metric_key=key, value=value, date=day, note=note, source=source)
    db.add(row)
    return row


def metric_history(db: Session, goal: Goal, key: str | None = None) -> list[MetricLog]:
    q = select(MetricLog).where(MetricLog.goal_id == goal.id)
    if key:
        q = q.where(MetricLog.metric_key == key)
    return list(db.scalars(q.order_by(MetricLog.date, MetricLog.id)).all())


def today_tasks(db: Session, goal: Goal, plan: Plan, day: date) -> list[TodayTask]:
    logs = task_logs(db, goal, day, day)
    out = []
    for t in tasks_due_on(plan, day):
        log = logs.get((t.id, day))
        out.append(TodayTask(
            task_id=t.id, title=t.title, duration_minutes=t.duration_minutes,
            time_of_day=t.schedule.time_of_day, status=log.status if log else "pending",  # type: ignore[arg-type]
        ))
    return out


def _adherence(due: int, done: int, partial: int) -> float | None:
    return round((done + 0.5 * partial) / due, 2) if due else None


def _window_adherence(plan: Plan, logs: dict, start: date, end: date) -> float | None:
    due = done = partial = 0
    day = max(start, plan.start_date)
    while day <= end:
        for t in tasks_due_on(plan, day):
            due += 1
            status = logs.get((t.id, day))
            done += status is not None and status.status == "done"
            partial += status is not None and status.status == "partial"
        day += timedelta(days=1)
    return _adherence(due, done, partial)


def streak_days(plan: Plan, logs: dict, today: date) -> int:
    """Consecutive days with every due task done, ending today (if complete) or yesterday."""
    def complete(day: date) -> bool | None:
        due = tasks_due_on(plan, day)
        if not due:
            return None  # rest day: doesn't break or extend the streak
        return all((log := logs.get((t.id, day))) is not None and log.status == "done" for t in due)

    streak, day = 0, today
    if complete(today) is False:
        day = today - timedelta(days=1)
    while day >= plan.start_date:
        c = complete(day)
        if c is False:
            break
        if c:
            streak += 1
        day -= timedelta(days=1)
    return streak


def metric_progress(db: Session, goal: Goal, plan: Plan, today: date) -> list[MetricProgress]:
    out = []
    total = max((plan.end_date - plan.start_date).days, 1)
    frac = min(max((today - plan.start_date).days / total, 0.0), 1.0)
    for m in plan.metrics:
        hist = metric_history(db, goal, m.key)
        latest = hist[-1] if hist else None
        expected = None
        if m.baseline is not None and m.target is not None:
            expected = round(m.baseline + (m.target - m.baseline) * frac, 2)
        out.append(MetricProgress(
            key=m.key, name=m.name, unit=m.unit, baseline=m.baseline, target=m.target, direction=m.direction,
            latest=latest.value if latest else None, latest_date=latest.date if latest else None, expected_now=expected,
        ))
    return out


def milestone_statuses(plan: Plan, today: date) -> list[MilestoneStatus]:
    out = []
    for m in plan.milestones:
        delta = (m.target_date - today).days
        status = "passed" if delta < -3 else "overdue" if delta < 0 else "due_soon" if delta <= 3 else "upcoming"
        out.append(MilestoneStatus(id=m.id, title=m.title, target_date=m.target_date, status=status))  # type: ignore[arg-type]
    return out


def progress_report(db: Session, goal: Goal, plan: Plan, today: date) -> ProgressReport:
    start28 = today - timedelta(days=27)
    logs = task_logs(db, goal, min(start28, plan.start_date), today)
    tasks = []
    for t in plan.tasks:
        due = done = partial = skipped = 0
        day = max(start28, plan.start_date)
        while day <= today:
            if is_due(t, day, plan):
                due += 1
                log = logs.get((t.id, day))
                if log:
                    done += log.status == "done"
                    partial += log.status == "partial"
                    skipped += log.status == "skipped"
            day += timedelta(days=1)
        tasks.append(TaskProgress(task_id=t.id, title=t.title, due=due, done=done, partial=partial, skipped=skipped,
                                  adherence=_adherence(due, done, partial)))
    # Today isn't over yet: adherence windows end yesterday so evening tasks don't count as missed.
    yesterday = today - timedelta(days=1)
    return ProgressReport(
        as_of=today,
        days_elapsed=max((today - plan.start_date).days, 0),
        days_left=max((plan.end_date - today).days, 0),
        adherence_7d=_window_adherence(plan, logs, today - timedelta(days=7), yesterday),
        adherence_28d=_window_adherence(plan, logs, start28 - timedelta(days=1), yesterday),
        streak_days=streak_days(plan, logs, today),
        tasks=tasks,
        metrics=metric_progress(db, goal, plan, today),
        milestones=milestone_statuses(plan, today),
    )
