"""Task recurrence: which plan tasks are due on which day."""

from datetime import date

from planner.lang import PY_WEEKDAYS, WEEKDAY_NAMES
from planner.llm.contracts import Language, Plan, PlanTask


def is_due(task: PlanTask, day: date, plan: Plan) -> bool:
    s = task.schedule
    if s.type == "once":
        return s.date == day
    start = s.start_date or plan.start_date
    end = s.end_date or plan.end_date
    if not (start <= day <= end):
        return False
    if s.type == "daily":
        return True
    if s.type == "weekly":
        return PY_WEEKDAYS[day.weekday()] in s.days_of_week
    if s.type == "every_n_days":
        return (day - start).days % (s.interval_days or 1) == 0
    return False


def tasks_due_on(plan: Plan, day: date) -> list[PlanTask]:
    return [t for t in plan.tasks if is_due(t, day, plan)]


def describe_schedule(task: PlanTask, lang: Language = "en") -> str:
    s = task.schedule
    he = lang == "he"
    if s.type == "once":
        text = (f"פעם אחת, {s.date:%d/%m/%Y}" if he else f"once on {s.date:%Y-%m-%d}") if s.date else ""
    elif s.type == "daily":
        text = "כל יום" if he else "daily"
    elif s.type == "weekly":
        days = ", ".join(WEEKDAY_NAMES[d][lang] for d in s.days_of_week)
        text = f"כל שבוע: {days}" if he else f"weekly: {days}"
    else:
        text = f"כל {s.interval_days} ימים" if he else f"every {s.interval_days} days"
    extras = []
    if task.duration_minutes:
        extras.append(f"{task.duration_minutes} דק'" if he else f"{task.duration_minutes} min")
    if s.time_of_day != "any":
        extras.append({"morning": "בוקר", "afternoon": "צהריים", "evening": "ערב"}[s.time_of_day] if he else s.time_of_day)
    return f"{text} ({', '.join(extras)})" if extras else text
