"""Mock planner.generate and planner.revise: domain templates and simple rule-based edits."""

from datetime import timedelta

from planner.lang import WEEKDAY_NAMES, find_weekdays
from planner.llm.contracts import (
    GenerateInput,
    Language,
    Metric,
    Milestone,
    Plan,
    PlanTask,
    ReviseInput,
    ReviseOutput,
    RevisionOp,
    TaskSchedule,
    Weekday,
)
from planner.llm.mock.common import DEFAULT_DAYS, WEEK_ORDER, detect_domain, first_number, t

# (en, he) task templates per domain: (id, title, description, share of active days, share of minutes)
TEMPLATES: dict[str, list[tuple[str, tuple[str, str], tuple[str, str], str, float]]] = {
    "weight": [
        ("t1", ("Workout", "אימון"), ("Cardio + strength at a comfortable intensity.", "אירובי + כוח בעצימות נוחה."), "main", 0.7),
        ("t2", ("Plan the week's meals", "תכנון ארוחות לשבוע"), ("Shop list + simple balanced meals.", "רשימת קניות + ארוחות מאוזנות ופשוטות."), "last", 0.3),
        ("t3", ("Weigh-in", "שקילה"), ("Same time, same scale, after waking up.", "באותה שעה ובאותו משקל, אחרי הקימה."), "first", 0.1),
    ],
    "running": [
        ("t1", ("Easy run", "ריצה קלה"), ("Conversational pace.", "בקצב שמאפשר לדבר."), "main_but_last", 0.75),
        ("t2", ("Long run", "ריצה ארוכה"), ("Slow pace, add distance gradually.", "קצב איטי, מוסיפים מרחק בהדרגה."), "last", 1.0),
        ("t3", ("Strength & mobility", "כוח וגמישות"), ("Legs, core, stretching.", "רגליים, בטן, מתיחות."), "first", 0.25),
    ],
    "fitness": [
        ("t1", ("Strength workout", "אימון כוח"), ("Full-body, progressive load.", "כל הגוף, עלייה הדרגתית בעומס."), "main_but_last", 0.9),
        ("t2", ("Mobility & stretching", "גמישות ומתיחות"), ("Short recovery session.", "סשן התאוששות קצר."), "last", 0.6),
    ],
    "study": [
        ("t1", ("Study new material", "לימוד חומר חדש"), ("One topic per session, active notes.", "נושא אחד בכל פעם, סיכום פעיל."), "main_but_last", 0.7),
        ("t2", ("Practice questions", "תרגול שאלות"), ("Past exam questions on recent topics.", "שאלות ממבחנים קודמים על הנושאים האחרונים."), "main_but_last", 0.3),
        ("t3", ("Weekly review", "חזרה שבועית"), ("Review mistakes and plan next week.", "עוברים על טעויות ומתכננים את השבוע הבא."), "last", 0.8),
    ],
    "language": [
        ("t1", ("Vocabulary (spaced repetition)", "אוצר מילים (חזרה מרווחת)"), ("New words + review.", "מילים חדשות + חזרה."), "main", 0.4),
        ("t2", ("Listening or reading", "האזנה או קריאה"), ("Podcast, video or a short text.", "פודקאסט, סרטון או טקסט קצר."), "main_but_last", 0.6),
        ("t3", ("Speaking practice", "תרגול דיבור"), ("Talk with a partner or record yourself.", "שיחה עם חבר/ה או הקלטה עצמית."), "last", 0.6),
    ],
    "finance": [
        ("t1", ("Log expenses", "רישום הוצאות"), ("Write down every expense of the day.", "לרשום כל הוצאה של היום."), "main", 0.2),
        ("t2", ("Weekly budget review", "סקירת תקציב שבועית"), ("Compare spending to budget, adjust.", "השוואת ההוצאות לתקציב ותיקון."), "last", 0.8),
    ],
    "skill": [
        ("t1", ("Learning session", "סשן לימוד"), ("Follow the course / book, take notes.", "ממשיכים בקורס/ספר, עם סיכום."), "main_but_last", 0.8),
        ("t2", ("Build something", "לבנות משהו"), ("Apply what you learned in a small project.", "מיישמים את מה שלמדת בפרויקט קטן."), "last", 1.0),
    ],
    "habit": [
        ("t1", ("Do the habit", "לבצע את ההרגל"), ("Small and consistent beats big and rare.", "קטן ועקבי עדיף על גדול ונדיר."), "main", 0.6),
        ("t2", ("Weekly reflection", "רפלקציה שבועית"), ("What worked, what to change.", "מה עבד ומה לשנות."), "last", 0.3),
    ],
    "general": [
        ("t1", ("Focused work session", "סשן עבודה ממוקד"), ("Work on the next concrete step.", "עבודה על הצעד הקונקרטי הבא."), "main_but_last", 0.9),
        ("t2", ("Weekly review & planning", "סיכום ותכנון שבועי"), ("Check progress, choose next week's steps.", "בודקים התקדמות ובוחרים צעדים לשבוע הבא."), "last", 0.5),
    ],
}

METRICS: dict[str, tuple[str, tuple[str, str], str, str]] = {
    # domain: (key, (en, he), unit, direction)
    "weight": ("weight_kg", ("Weight", "משקל"), "kg", "decrease"),
    "running": ("longest_run_km", ("Longest run", "הריצה הארוכה ביותר"), "km", "increase"),
    "study": ("practice_score", ("Practice score", "ציון בתרגול"), "%", "increase"),
    "language": ("words_learned", ("Words learned", "מילים שנלמדו"), "words", "increase"),
    "finance": ("savings_amount", ("Saved so far", "נחסך עד כה"), "", "increase"),
}

METRIC_TASK = {"weight": "t3", "running": "t2", "study": "t3", "language": "t1", "finance": "t2"}

PHASES = [
    ("Foundations", "בניית בסיס"),
    ("Build consistency", "בניית עקביות"),
    ("Level up", "העלאת רמה"),
    ("Push forward", "דחיפה קדימה"),
    ("Final stretch", "הישורת האחרונה"),
]


def _active_days(inp: GenerateInput) -> list[Weekday]:
    at = inp.goal.available_time
    days = [d for d in WEEK_ORDER if d in at.preferred_days] or DEFAULT_DAYS[at.days_per_week]
    return days[: at.days_per_week]


def _days_for(kind: str, days: list[Weekday]) -> list[Weekday]:
    if kind == "first":
        return days[:1]
    if kind == "last":
        return days[-1:]
    if kind == "main_but_last" and len(days) > 1:
        return days[:-1]
    return days


def _metric(domain: str, inp: GenerateInput, lang: Language, weeks: float) -> tuple[Metric | None, list[str]]:
    if domain not in METRICS:
        return None, []
    key, names, unit, direction = METRICS[domain]
    p = inp.profile
    notes: list[str] = []
    baseline = target = None
    if domain == "weight":
        baseline = first_number(str(p.get("weight_kg", "")))
        target = first_number(str(p.get("target_weight_kg", "")))
        if baseline is not None and target is not None and target < baseline:
            safest = round(baseline - 0.75 * weeks, 1)  # at most ~0.75 kg/week
            if target < safest:
                notes.append(t(lang, f"To stay safe, the target by the deadline is {safest} kg (about 0.75 kg/week). "
                                     f"You can keep going toward {target} kg afterwards.",
                               f"כדי לשמור על בטיחות, היעד עד תאריך הסיום הוא {safest} ק\"ג (כ-0.75 ק\"ג בשבוע). "
                               f"אפשר להמשיך אחר כך לכיוון {target} ק\"ג."))
                target = safest
    elif domain == "running":
        baseline = first_number(str(p.get("longest_run_km", ""))) or 0.0
        target = first_number(str(p.get("target", ""))) or 5.0
    elif domain == "finance":
        baseline = first_number(str(p.get("current_savings", ""))) or 0.0
        target = first_number(str(p.get("target_amount", "")))
        unit = str(p.get("currency", "")).split(" ")[0]
    elif domain == "study":
        target = first_number(str(p.get("target_score", ""))) or 85.0
    elif domain == "language":
        baseline, target = 0.0, float(int(weeks * 50))
    metric = Metric(key=key, name=t(lang, *names), unit=unit, baseline=baseline, target=target, direction=direction)  # type: ignore[arg-type]
    return metric, notes


def generate(inp: GenerateInput) -> Plan:
    lang = inp.style.language
    domain = str(inp.profile.get("domain") or detect_domain(inp.goal))
    start, end = inp.today, max(inp.goal.deadline, inp.today + timedelta(days=7))
    total_days = (end - start).days
    weeks = total_days / 7
    days = _active_days(inp)
    minutes = inp.goal.available_time.minutes_per_day
    tod = inp.goal.available_time.preferred_time_of_day

    n_ms = max(2, min(5, total_days // 21))
    milestones = []
    for i in range(n_ms):
        target_date = start + timedelta(days=round(total_days * (i + 1) / n_ms))
        en, he = PHASES[min(i, len(PHASES) - 1)] if i < n_ms - 1 else PHASES[-1]
        milestones.append(Milestone(
            id=f"m{i + 1}", title=t(lang, en, he), target_date=min(target_date, end),
            success_criteria=t(lang, f"At least 80% of planned sessions done by {target_date:%d/%m}.",
                               f"לפחות 80% מהמפגשים המתוכננים בוצעו עד {target_date:%d/%m}."),
        ))

    metric, notes = _metric(domain, inp, lang, weeks)
    tasks = []
    for task_id, title, desc, kind, share in TEMPLATES[domain]:
        tasks.append(PlanTask(
            id=task_id, title=t(lang, *title), description=t(lang, *desc),
            schedule=TaskSchedule(type="weekly", days_of_week=_days_for(kind, days), time_of_day=tod),
            duration_minutes=max(5, int(minutes * share) // 5 * 5),
            metric_key=metric.key if metric and METRIC_TASK.get(domain) == task_id else None,
        ))
    if domain == "study":
        mock_date = max(start, end - timedelta(days=5))
        tasks.append(PlanTask(id="t4", title=t(lang, "Full mock exam", "מבחן הדמיה מלא"),
                              description=t(lang, "Real exam conditions, then review.", "בתנאי מבחן אמיתיים, ואחר כך ניתוח."),
                              schedule=TaskSchedule(type="once", date=mock_date), duration_minutes=max(minutes, 90)))

    safety = list(notes)
    if domain in ("weight", "running", "fitness"):
        safety.append(t(lang, "Stop and rest if you feel pain, dizziness or chest discomfort; consult a doctor if it persists.",
                        "אם מופיעים כאב, סחרחורת או לחץ בחזה — לעצור ולנוח, ואם זה נמשך — לפנות לרופא/ה."))
    for flag in inp.safety_flags:
        if flag.severity != "info":
            safety.append(t(lang, "This plan was kept extra gentle because of your answers. Please check it with a professional.",
                            "התוכנית נבנתה עדינה במיוחד בגלל התשובות שלך. מומלץ לעבור עליה עם איש/אשת מקצוע."))
            break

    return Plan(
        title=inp.goal.title,
        summary=t(lang, f"{len(days)} active days a week, about {minutes} minutes a day, in {n_ms} phases until {end:%d/%m/%Y}.",
                  f"{len(days)} ימים פעילים בשבוע, כ-{minutes} דקות ביום, ב-{n_ms} שלבים עד {end:%d/%m/%Y}."),
        start_date=start, end_date=end, milestones=milestones, tasks=tasks,
        metrics=[metric] if metric else [],
        tips=[t(lang, "Missing one day is fine — just don't miss two in a row.", "לפספס יום אחד זה בסדר — רק לא שניים ברצף."),
              t(lang, "Tell the coach how it went; your plan adapts to you.", "ספר/י למאמן איך הלך; התוכנית מתאימה את עצמה אליך.")],
        safety_notes=safety,
        assumptions=[t(lang, f"Active days: {', '.join(WEEKDAY_NAMES[d][lang] for d in days)}.",
                       f"ימים פעילים: {', '.join(WEEKDAY_NAMES[d][lang] for d in days)}.")],
    )


# ---------------------------------------------------------------------------------------------
# planner.revise
# ---------------------------------------------------------------------------------------------

_EASIER = ["too hard", "too much", "easier", "less", "tired", "overwhelm", "קשה מדי", "קשים מדי", "קשות מדי", "קשה לי",
           "יותר מדי", "פחות", "קל יותר", "להקל", "תקל", "עייף", "עמוס"]
_HARDER = ["too easy", "harder", "more", "challenge", "קל מדי", "יותר", "אתגר", "להגביר"]


def _scale_durations(inp: ReviseInput, factor: float, only: set[str] | None, reason: str) -> list[RevisionOp]:
    ops = []
    for task in inp.plan.tasks:
        if task.duration_minutes and (only is None or task.id in only):
            new = max(5, int(task.duration_minutes * factor) // 5 * 5)
            if new != task.duration_minutes:
                ops.append(RevisionOp(op="update_task", target_id=task.id, data={"duration_minutes": new}, reason=reason))
    return ops


def _move_off_days(inp: ReviseInput, blocked: list[Weekday], reason: str) -> list[RevisionOp]:
    ops = []
    used = {d for task in inp.plan.tasks for d in task.schedule.days_of_week}
    free = [d for d in WEEK_ORDER if d not in used and d not in blocked]
    for task in inp.plan.tasks:
        days = task.schedule.days_of_week
        if task.schedule.type != "weekly" or not set(days) & set(blocked):
            continue
        new_days = [d for d in days if d not in blocked]
        for _ in range(len(days) - len(new_days)):
            if free:
                new_days.append(free.pop(0))
        new_days = sorted(set(new_days), key=WEEK_ORDER.index) or [next(d for d in WEEK_ORDER if d not in blocked)]
        schedule = task.schedule.model_dump(mode="json") | {"days_of_week": new_days}
        ops.append(RevisionOp(op="update_task", target_id=task.id, data={"schedule": schedule}, reason=reason))
    return ops


def revise(inp: ReviseInput) -> ReviseOutput:
    lang = inp.style.language
    details = inp.trigger_details.lower()
    ops: list[RevisionOp] = []
    explanation = ""

    if inp.trigger in ("user_request", "constraint_change"):
        blocked = find_weekdays(details)
        if blocked:
            ops = _move_off_days(inp, blocked, "user is not available on these days")
            names = ", ".join(WEEKDAY_NAMES[d][lang] for d in blocked)
            explanation = t(lang, f"I moved your sessions off {names} so the plan fits your week.",
                            f"הזזתי את המפגשים מימי {names} כדי שהתוכנית תתאים לשבוע שלך.")
        elif (n := first_number(details)) and ("min" in details or "דק" in details):
            ops = [RevisionOp(op="update_task", target_id=task.id, data={"duration_minutes": int(n)}, reason="user asked for this session length")
                   for task in inp.plan.tasks if task.duration_minutes and task.duration_minutes > n]
            explanation = t(lang, f"Sessions now take at most {int(n)} minutes.", f"המפגשים יימשכו עכשיו עד {int(n)} דקות.")
        elif any(w in details for w in _EASIER):
            ops = _scale_durations(inp, 0.75, None, "user asked for an easier plan")
            explanation = t(lang, "I made the sessions about 25% shorter so it's easier to keep going. We can build up again later.",
                            "קיצרתי את המפגשים בכ-25% כדי שיהיה קל יותר להתמיד. נוכל להעלות שוב בהמשך.")
        elif any(w in details for w in _HARDER):
            ops = _scale_durations(inp, 1.2, None, "user asked for more challenge")
            explanation = t(lang, "I made the sessions about 20% longer for a bit more challenge.",
                            "האמנתי את המפגשים בכ-20% כדי להוסיף קצת אתגר.")
    elif inp.trigger in ("low_adherence", "behind_schedule") or (
        inp.trigger == "weekly_review" and inp.progress.adherence_7d is not None and inp.progress.adherence_7d < 0.5
    ):
        struggling = {tp.task_id for tp in inp.progress.tasks if tp.adherence is not None and tp.adherence < 0.6}
        ops = _scale_durations(inp, 0.75, struggling or None, "low adherence: make it easier to follow")
        explanation = t(lang, "This week was harder to keep up with, and that's okay. I shortened the sessions that were "
                              "toughest to fit in, so the plan matches your real week.",
                        "השבוע היה קשה יותר להתמיד, וזה בסדר. קיצרתי את המפגשים שהכי קשה היה להכניס, "
                        "כדי שהתוכנית תתאים לשבוע האמיתי שלך.")
    elif inp.trigger == "ahead_of_schedule":
        main = inp.plan.tasks[0].id
        ops = _scale_durations(inp, 1.15, {main}, "ahead of schedule: modest increase")
        explanation = t(lang, "You're ahead of schedule — great work! I added a little to your main session.",
                        "את/ה מקדים/ה את הלו\"ז — כל הכבוד! הוספתי קצת למפגש המרכזי.")

    if not ops:
        return ReviseOutput(
            should_revise=False,
            explanation=t(lang, "Your plan still fits well, so I'm keeping it as is.",
                          "התוכנית עדיין מתאימה, אז אני משאיר/ה אותה כמו שהיא."),
        )
    return ReviseOutput(should_revise=True, explanation=explanation, operations=ops)
