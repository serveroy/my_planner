"""Shared helpers for the heuristic mock models."""

from planner.llm.contracts import Language, Weekday
from planner.textutil import detect_domain, first_number  # noqa: F401  (re-exported)


def t(lang: Language, en: str, he: str) -> str:
    return he if lang == "he" else en


def is_negative_answer(text: str | None) -> bool:
    if not text:
        return True
    norm = text.strip().lower().strip(".!")
    return norm in {"no", "none", "nope", "nothing", "n/a", "-", "לא", "אין", "כלום", "אין לי", "לא ממש"}


# Default training days for N active days per week (Israeli week: Sunday first).
DEFAULT_DAYS: dict[int, list[Weekday]] = {
    1: ["sun"],
    2: ["sun", "wed"],
    3: ["sun", "tue", "thu"],
    4: ["sun", "mon", "wed", "thu"],
    5: ["sun", "mon", "tue", "wed", "thu"],
    6: ["sun", "mon", "tue", "wed", "thu", "fri"],
    7: ["sun", "mon", "tue", "wed", "thu", "fri", "sat"],
}

WEEK_ORDER: list[Weekday] = ["sun", "mon", "tue", "wed", "thu", "fri", "sat"]
