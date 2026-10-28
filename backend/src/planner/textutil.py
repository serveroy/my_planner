"""Small text heuristics used by the app's rule-based parts (safety checks) and by the mock models."""

import re

from planner.llm.contracts import GoalBrief

Domain = str  # weight | running | fitness | study | language | finance | skill | habit | general

_DOMAIN_KEYWORDS: list[tuple[Domain, list[str]]] = [
    ("weight", ["weight", "lose", "kg", "kilo", "fat", "diet", "slim", "משקל", "לרדת", "קילו", "דיאטה", "שומן", "להוריד", "להרזות"]),
    ("running", ["run", "marathon", "5k", "10k", "jog", "ריצה", "לרוץ", "מרתון", "ק\"מ", "קמ"]),
    ("fitness", ["gym", "muscle", "strength", "workout", "fit", "push-up", "pull-up", "כושר", "שריר", "אימון", "מתח", "שכיבות"]),
    ("study", ["exam", "test", "study", "course", "grade", "bagrut", "psychometric", "university", "מבחן", "בחינה", "ללמוד", "בגרות", "פסיכומטרי", "קורס", "ציון", "סמסטר"]),
    ("language", ["spanish", "french", "german", "arabic", "english", "japanese", "language", "fluent", "שפה", "אנגלית", "ספרדית", "צרפתית", "ערבית", "גרמנית", "יפנית"]),
    ("finance", ["save", "saving", "money", "budget", "debt", "invest", "$", "₪", "לחסוך", "כסף", "תקציב", "חוב", "חיסכון", "שקל"]),
    ("skill", ["code", "coding", "programming", "python", "javascript", "develop", "guitar", "piano", "draw", "תכנות", "לתכנת", "פייתון", "גיטרה", "פסנתר", "לצייר"]),
    ("habit", ["read", "book", "sleep", "meditat", "habit", "journal", "לקרוא", "ספר", "שינה", "לישון", "מדיטציה", "הרגל", "יומן"]),
]


def detect_domain(goal: GoalBrief) -> Domain:
    text = f"{goal.title} {goal.description}".lower()
    best, best_hits = "general", 0
    for domain, words in _DOMAIN_KEYWORDS:
        hits = sum(1 for w in words if w in text)
        if hits > best_hits:
            best, best_hits = domain, hits
    return best


def first_number(text: str | None) -> float | None:
    if not text:
        return None
    m = re.search(r"-?\d+(?:[.,]\d+)?", text)
    return float(m.group(0).replace(",", ".")) if m else None
