"""Language helpers shared by the app and the mock models."""

import re

from planner.llm.contracts import Language, Weekday

_HEBREW = re.compile(r"[֐-׿]")
_LATIN = re.compile(r"[A-Za-z]")


def detect_language(text: str, default: Language = "en") -> Language:
    he = len(_HEBREW.findall(text or ""))
    en = len(_LATIN.findall(text or ""))
    if he == 0 and en == 0:
        return default
    return "he" if he >= en * 0.5 else "en"


WEEKDAY_NAMES: dict[Weekday, dict[str, str]] = {
    "sun": {"en": "Sunday", "he": "ראשון"},
    "mon": {"en": "Monday", "he": "שני"},
    "tue": {"en": "Tuesday", "he": "שלישי"},
    "wed": {"en": "Wednesday", "he": "רביעי"},
    "thu": {"en": "Thursday", "he": "חמישי"},
    "fri": {"en": "Friday", "he": "שישי"},
    "sat": {"en": "Saturday", "he": "שבת"},
}

# Python's date.weekday(): Monday == 0.
PY_WEEKDAYS: list[Weekday] = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]


def find_weekdays(text: str) -> list[Weekday]:
    """Weekdays mentioned in English or Hebrew text, in order of appearance."""
    lowered = text.lower()
    found: list[tuple[int, Weekday]] = []
    for day, names in WEEKDAY_NAMES.items():
        candidates = [names["en"].lower(), names["en"][:3].lower() + " ", f"יום {names['he']}", f"ב{names['he']}"]
        if day == "sat":
            candidates.append("בשבת")
        positions = [lowered.find(c) for c in candidates if lowered.find(c) != -1]
        if positions:
            found.append((min(positions), day))
    return [d for _, d in sorted(found)]
