"""Rule-based guardrails that run around the models.

The models are instructed (and will be fine-tuned) to behave safely, but these checks do not
depend on them: crisis language gets a fixed response with real resources, and risky profiles or
plans get flags that are passed to every later model call.
"""

import re

from planner.llm.contracts import Language, Plan, SafetyFlag
from planner.textutil import first_number

_CRISIS_PATTERNS = [
    r"\bkill myself\b", r"\bsuicid", r"\bend my life\b", r"\bwant to die\b", r"\bhurt myself\b", r"\bself[- ]harm",
    r"להתאבד", r"התאבדות", r"לשים קץ", r"רוצה למות", r"לפגוע בעצמי", r"אין לי בשביל מה לחיות",
]
_CRISIS_RE = re.compile("|".join(_CRISIS_PATTERNS), re.IGNORECASE)

_ED_PATTERNS = [r"\bstarv", r"\bpurg", r"\bthrow(ing)? up after", r"\banorexi", r"\bbulimi", r"\bnot eat(ing)? at all",
                r"להרעיב", r"להקיא אחרי", r"אנורקסיה", r"בולימיה", r"לא לאכול בכלל"]
_ED_RE = re.compile("|".join(_ED_PATTERNS), re.IGNORECASE)


def detect_crisis(text: str) -> bool:
    return bool(_CRISIS_RE.search(text or ""))


def crisis_response(lang: Language) -> str:
    if lang == "he":
        return (
            "אני ממש שמח/ה שסיפרת לי, ואני לוקח/ת את זה ברצינות. את/ה לא לבד.\n"
            "אם את/ה בסכנה מיידית — חייג/י 101 (מד\"א) או 100 (משטרה).\n"
            "אפשר לדבר עכשיו, בחינם ובאנונימיות, עם ער\"ן בטלפון 1201 (24/7), או עם סה\"ר בצ'אט באתר sahar.org.il.\n"
            "אני כאן איתך, ואשמח להמשיך לדבר — אבל חשוב לי שתדבר/י גם עם אדם שיכול לעזור עכשיו."
        )
    return (
        "I'm really glad you told me, and I'm taking it seriously. You're not alone.\n"
        "If you're in immediate danger, please call your local emergency number (911 in the US, 101 in Israel).\n"
        "You can talk to someone right now: call or text 988 (US Suicide & Crisis Lifeline), or ERAN at 1201 in Israel. "
        "Elsewhere, findahelpline.com lists free local lines.\n"
        "I'm here and happy to keep talking, but please also reach out to someone who can help right now."
    )


def crisis_flag() -> SafetyFlag:
    return SafetyFlag(
        code="crisis_language", severity="high",
        guidance="The user expressed thoughts of self-harm. Prioritize their wellbeing over the plan, be gentle, and "
                 "encourage contacting a crisis line or emergency services. Do not push tasks.",
    )


def _num(profile: dict, *keys: str) -> float | None:
    for k in keys:
        if k in profile and (v := first_number(str(profile[k]))) is not None:
            return v
    return None


def check_profile(domain: str, profile: dict, goal_text: str) -> list[SafetyFlag]:
    flags: list[SafetyFlag] = []
    physical = domain in ("weight", "running", "fitness")
    age = _num(profile, "age")
    if age is not None and age < 18 and physical:
        flags.append(SafetyFlag(
            code="minor_physical_goal", severity="caution",
            guidance="The user is under 18. Focus on healthy habits, enjoyment and performance, never on calorie "
                     "restriction or rapid weight change. Recommend involving a parent and a doctor.",
        ))
    height, weight = _num(profile, "height_cm"), _num(profile, "weight_kg")
    target = _num(profile, "target_weight_kg")
    if height and target and 100 < height < 250:
        bmi_target = target / (height / 100) ** 2
        if bmi_target < 18.5:
            flags.append(SafetyFlag(
                code="underweight_target", severity="high",
                guidance=f"The target weight corresponds to BMI {bmi_target:.1f} (underweight). Do not plan toward it; "
                         "propose a healthy range and recommend a doctor or dietitian.",
            ))
    if height and weight and 100 < height < 250 and weight / (height / 100) ** 2 < 18.5 and domain == "weight":
        flags.append(SafetyFlag(
            code="underweight_now", severity="high",
            guidance="The user is already underweight. Do not create a weight-loss plan; focus on health and "
                     "recommend professional support.",
        ))
    health = str(profile.get("health_conditions", "")).strip().lower()
    if physical and health and health not in {"no", "none", "nope", "לא", "אין", "-"}:
        flags.append(SafetyFlag(
            code="health_condition", severity="caution",
            guidance=f"The user reported a health condition: '{health[:120]}'. Keep intensity moderate, avoid "
                     "contraindicated activities and recommend checking the plan with a doctor.",
        ))
    if _ED_RE.search(goal_text + " " + " ".join(str(v) for v in profile.values())):
        flags.append(SafetyFlag(
            code="disordered_eating", severity="high",
            guidance="Signs of disordered eating. Do not give calorie targets or weight-loss tasks; respond with care "
                     "and recommend professional help.",
        ))
    return flags


def check_plan(plan: Plan, minutes_per_day: int) -> list[str]:
    """Warnings about a generated plan (logged and returned to the client; not shown as errors)."""
    from datetime import timedelta

    from planner.services.schedule import tasks_due_on

    warnings = []
    day = plan.start_date
    for _ in range(min(14, (plan.end_date - plan.start_date).days + 1)):
        total = sum(t.duration_minutes or 0 for t in tasks_due_on(plan, day))
        if total > minutes_per_day * 1.25:
            warnings.append(f"{day}: {total} min scheduled, available {minutes_per_day}")
        day += timedelta(days=1)
    for m in plan.metrics:
        if m.key == "weight_kg" and m.baseline and m.target:
            weeks = max((plan.end_date - plan.start_date).days / 7, 1)
            rate = (m.baseline - m.target) / weeks
            if rate > 1.0:
                warnings.append(f"weight change of {rate:.2f} kg/week exceeds 1 kg/week")
    return warnings


def merge_flags(existing: list[dict], new: list[SafetyFlag]) -> list[dict]:
    codes = {f["code"] for f in existing}
    return existing + [f.model_dump() for f in new if f.code not in codes]
