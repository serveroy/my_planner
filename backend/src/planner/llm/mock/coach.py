"""Mock coach.chat, coach.checkin, coach.extract and coach.summarize."""

import re
from datetime import timedelta

from planner.lang import find_weekdays
from planner.llm.contracts import (
    CheckinInput,
    CoachChatInput,
    CoachContext,
    ExtractedEvent,
    ExtractInput,
    ExtractOutput,
    Language,
    SummarizeInput,
)
from planner.llm.mock.common import first_number, t

# ---------------------------------------------------------------------------------------------
# coach.extract
# ---------------------------------------------------------------------------------------------

DONE_WORDS = ["did", "done", "finished", "completed", "went", "ran ", "worked out", "studied", "practiced", "managed",
              "עשיתי", "סיימתי", "הלכתי", "רצתי", "התאמנתי", "למדתי", "תרגלתי", "ביצעתי", "הספקתי", "השלמתי"]
NOT_DONE_WORDS = ["didn't", "did not", "skipped", "missed", "couldn't", "could not", "haven't", "no time",
                  "לא עשיתי", "לא הספקתי", "דילגתי", "פספסתי", "לא הלכתי", "לא התאמנתי", "לא למדתי", "לא יצא", "לא היה לי זמן"]
PARTIAL_WORDS = ["half", "part of", "partially", "some of", "חצי", "חלק מ", "באופן חלקי"]
YES_WORDS = {"yes", "yep", "yeah", "yup", "sure", "of course", "כן", "בטח", "ברור", "כמובן", "יש"}
NO_WORDS = {"no", "nope", "not yet", "לא", "עדיין לא", "לא היום"}
CONSTRAINT_WORDS = ["can't", "cannot", "not available", "no longer", "busy on", "new job", "moved", "injured",
                    "לא יכול", "לא יכולה", "אין לי זמן ב", "לא פנוי", "לא פנויה", "עבודה חדשה", "עברתי", "נפצעתי"]
CHANGE_WORDS = ["change the plan", "change my plan", "update the plan", "update my plan", "adjust", "too hard", "too easy",
                "too much", "make it easier", "make it harder", "לשנות את התוכנית", "שנה את התוכנית", "תשנה", "לעדכן את התוכנית",
                "תעדכן", "קשה מדי", "קשים מדי", "קשות מדי", "קל מדי", "יותר מדי", "תקל", "להקל"]
MOODS = {
    "tired": ["tired", "exhausted", "sleepy", "עייף", "עייפה", "גמור", "גמורה"],
    "stressed": ["stressed", "anxious", "pressure", "לחוץ", "לחוצה", "לחץ", "חרד"],
    "frustrated": ["frustrated", "annoyed", "angry", "מתוסכל", "מתוסכלת", "מעצבן"],
    "demotivated": ["no motivation", "unmotivated", "give up", "pointless", "אין לי מוטיבציה", "לוותר", "אין טעם"],
    "positive": ["great", "awesome", "amazing", "happy", "proud", "feel good", "מעולה", "מדהים", "שמח", "שמחה", "גאה", "מרגיש טוב", "מרגישה טוב"],
}
SAFETY_WORDS = ["starv", "not eating", "stop eating", "purge", "throw up", "chest pain", "faint", "hurt myself",
                "להרעיב", "לא אוכל כלום", "להקיא", "כאב בחזה", "התעלפתי", "לפגוע בעצמי"]
_HE_PREFIXES = "והבלמשכ"


def _tokens(text: str) -> set[str]:
    out = set()
    for w in re.findall(r"[\w֐-׿]+", text.lower()):
        if len(w) >= 3:
            out.add(w)
            if w[0] in _HE_PREFIXES and len(w) >= 4:
                out.add(w[1:])
        if w.endswith("ing") and len(w) > 5:
            out.add(w[:-3])
    return out


def _has(text: str, words: list[str] | set[str]) -> bool:
    return any(w in text for w in words)


def _matching_tasks(text: str, inp: ExtractInput) -> list[str]:
    msg = _tokens(text)
    synonyms = {"run": {"ran", "running", "jog", "רצתי", "ריצה"}, "workout": {"worked", "gym", "trained", "התאמנתי", "אימון"},
                "study": {"studied", "learned", "למדתי"}, "practice": {"practiced", "תרגלתי"}}
    hits = []
    for task in inp.tasks:
        title = _tokens(task.title)
        expanded = set(title)
        for key, syn in synonyms.items():
            if any(key in w for w in title) or title & syn:
                expanded |= syn | {key}
        if msg & expanded:
            hits.append(task.id)
    return hits


def extract(inp: ExtractInput) -> ExtractOutput:
    msg = inp.message.strip()
    low = msg.lower()
    events: list[ExtractedEvent] = []
    day = inp.today - timedelta(days=1) if _has(low, ["yesterday", "אתמול"]) else inp.today

    negative = _has(low, NOT_DONE_WORDS)
    done = _has(low, DONE_WORDS) or re.search(r"\bran\b", low) is not None
    short_yes = low.strip("!. ") in YES_WORDS or re.match(r"^(yes|yeah|yep|yup|כן)\b", low) is not None
    short_no = low.strip("!. ") in NO_WORDS
    last_assistant = next((m.content for m in reversed(inp.recent_messages) if m.role == "assistant"), "")

    task_ids = _matching_tasks(msg, inp)
    if not task_ids and (short_yes or short_no or done or negative):
        # "Yes!" answering "did you do your workout today?" -> tasks named in the question.
        task_ids = _matching_tasks(last_assistant, inp) if last_assistant else []
        if not task_ids:
            due = [task.id for task in inp.tasks if task.due_today]
            task_ids = due if (len(due) == 1 or short_yes or short_no) else []
    if task_ids and (done or negative or short_yes or short_no):
        if negative or short_no:
            kind = "task_skipped"
        elif _has(low, PARTIAL_WORDS):
            kind = "task_partial"
        else:
            kind = "task_done"
        events += [ExtractedEvent(type=kind, task_id=tid, date=day) for tid in task_ids]

    number = first_number(msg)
    if number is not None:
        for metric in inp.metrics:
            unit_hit = metric.unit and metric.unit.lower() in low
            name_hit = metric.name.lower() in low or (metric.key == "weight_kg" and _has(low, ["weigh", "שוקל", "שוקלת", "משקל", "קילו", 'ק"ג']))
            if unit_hit or name_hit:
                events.append(ExtractedEvent(type="metric_value", metric_key=metric.key, value=number, date=day))
                break

    if _has(low, CONSTRAINT_WORDS):
        days = find_weekdays(msg)
        text = f"User is not available on {', '.join(days)}" if days else f"User reported a change in circumstances: {msg[:120]}"
        events.append(ExtractedEvent(type="constraint", text=text))
    if _has(low, CHANGE_WORDS):
        events.append(ExtractedEvent(type="plan_change_request", text=f"User asked to change the plan: {msg[:160]}"))
    for mood, words in MOODS.items():
        if _has(low, words):
            events.append(ExtractedEvent(type="mood", mood=mood))  # type: ignore[arg-type]
            break
    if _has(low, SAFETY_WORDS):
        events.append(ExtractedEvent(type="safety_concern", text=f"Possible health/safety issue: {msg[:120]}"))
    return ExtractOutput(events=events)


# ---------------------------------------------------------------------------------------------
# coach.chat
# ---------------------------------------------------------------------------------------------


def _pending(ctx: CoachContext) -> list[str]:
    return [task.title for task in ctx.today_tasks if task.status == "pending"]


def _join(items: list[str], lang: Language) -> str:
    if len(items) <= 1:
        return "".join(items)
    return ", ".join(items[:-1]) + t(lang, " and ", " ו") + items[-1]


def chat(inp: CoachChatInput) -> str:
    ctx = inp.context
    lang = ctx.style.language
    last = inp.messages[-1].content.lower() if inp.messages else ""
    name = ctx.user_name.split(" ")[0]
    parts: list[str] = []

    if ctx.safety_flags and any(f.severity == "high" for f in ctx.safety_flags):
        parts.append(t(lang, "I care about how you're doing, and your health comes first. It could really help to talk "
                             "with a doctor or someone you trust about this.",
                       "אכפת לי ממך, והבריאות שלך קודמת לכל. יכול מאוד לעזור לדבר על זה עם רופא/ה או עם מישהו/י שסומכים עליו/ה."))

    if ctx.actions_taken:
        parts.append(t(lang, f"Nice, {name}! I updated your progress: {'; '.join(ctx.actions_taken)}.",
                       f"יופי, {name}! עדכנתי את ההתקדמות שלך: {'; '.join(ctx.actions_taken)}."))

    pending = _pending(ctx)
    if _has(last, MOODS["tired"] + MOODS["stressed"] + MOODS["demotivated"] + MOODS["frustrated"]):
        parts.append(t(lang, "That sounds hard, and it's completely normal to have days like this. "
                             "Even a small version of today's task counts.",
                       "נשמע קשה, וזה ממש נורמלי שיש ימים כאלה. גם גרסה קטנה של המשימה של היום נחשבת."))
    asks_about_today = _has(last, ["what should", "what's next", "what do i", "מה לעשות", "מה הבא", "מה יש לי"]) or (
        "?" in last and _has(last, ["today", "היום"]))
    if ctx.revision_in_progress:
        parts.append(t(lang, "Got it — I'm preparing an updated plan for you to review.",
                       "הבנתי — אני מכין/ה לך תוכנית מעודכנת לאישור.") if ctx.plan_update_mode == "ask" else
                     t(lang, "Got it — I'm updating your plan right now.", "הבנתי — אני מעדכן/ת את התוכנית שלך עכשיו."))
    elif ctx.pending_revision:
        parts.append(t(lang, "I've prepared an updated plan for you — take a look and approve it when you're ready.",
                       "הכנתי לך תוכנית מעודכנת — אפשר לעבור עליה ולאשר כשנוח לך."))
    elif asks_about_today:
        if pending:
            parts.append(t(lang, f"Today on your plan: {_join(pending, lang)}.", f"היום בתוכנית: {_join(pending, lang)}."))
        else:
            parts.append(t(lang, "Nothing left for today — enjoy the rest!", "לא נשאר כלום להיום — תהנה/י מהמנוחה!"))

    if not parts:
        parts.append(t(lang, "I'm here with you.", "אני כאן איתך."))
    if pending and not ctx.actions_taken:
        parts.append(t(lang, f"Want to start with {pending[0]}?", f"רוצה להתחיל עם {pending[0]}?"))
    elif ctx.days_left is not None and ctx.adherence_7d is not None:
        pct = round(ctx.adherence_7d * 100)
        parts.append(t(lang, f"You're at {pct}% of this week's plan with {ctx.days_left} days to go. How are you feeling about it?",
                       f"השבוע ביצעת {pct}% מהתוכנית, ונשארו {ctx.days_left} ימים. איך את/ה מרגיש/ה עם זה?"))
    else:
        parts.append(t(lang, "How are you feeling about your progress?", "איך את/ה מרגיש/ה עם ההתקדמות?"))
    return " ".join(parts)


# ---------------------------------------------------------------------------------------------
# coach.checkin
# ---------------------------------------------------------------------------------------------


def checkin(inp: CheckinInput) -> str:
    ctx = inp.context
    lang = ctx.style.language
    name = ctx.user_name.split(" ")[0]
    pending = _join(_pending(ctx), lang)
    first_task = ctx.plan.tasks[0].title if ctx.plan and ctx.plan.tasks else ""
    messages = {
        "plan_ready": (f"Hi {name}! Your plan is ready 🎯 The first step is {first_task}. Want me to remind you in the evening?",
                       f"היי {name}! התוכנית שלך מוכנה 🎯 הצעד הראשון הוא {first_task}. רוצה שאזכיר לך בערב?"),
        "daily_tasks": (f"Hey {name}, how did today go? Did you get to {pending}?",
                        f"היי {name}, איך עבר היום? הספקת {pending}?"),
        "all_done": (f"Everything on today's plan is done — that's {ctx.streak_days} days in a row! Proud of you.",
                     f"כל מה שתוכנן להיום בוצע — זה {ctx.streak_days} ימים ברצף! גאה בך."),
        "missed_yesterday": (f"Yesterday didn't go as planned, and that's okay. What got in the way? We can adjust together.",
                             f"אתמול לא הלך לפי התוכנית, וזה בסדר. מה הפריע? נוכל להתאים יחד."),
        "inactivity": (f"Hi {name}, I haven't heard from you in a few days. Even 10 minutes today would be a great restart — shall we?",
                       f"היי {name}, לא שמעתי ממך כמה ימים. גם 10 דקות היום יהיו התחלה מחדש מעולה — ננסה?"),
        "milestone_upcoming": (f"Your next milestone is coming up: {inp.trigger_details}. You're close — what's left to get there?",
                               f"אבן הדרך הבאה מתקרבת: {inp.trigger_details}. את/ה קרוב/ה — מה נשאר כדי להגיע?"),
        "metric_reminder": (f"Quick one: could you log your latest {inp.trigger_details}? It helps me keep the plan accurate.",
                            f"שאלה קצרה: תוכל/י לעדכן את ה{inp.trigger_details} האחרון? זה עוזר לי לדייק את התוכנית."),
        "deadline_near": (f"Only {ctx.days_left} days left until your deadline! Let's make them count — what's your focus this week?",
                          f"נשארו רק {ctx.days_left} ימים עד היעד! בוא/י ננצל אותם — על מה מתמקדים השבוע?"),
    }
    en, he = messages[inp.trigger]
    text = t(lang, en, he)
    if not ctx.style.use_emojis:
        text = text.replace(" 🎯", "")
    return text


# ---------------------------------------------------------------------------------------------
# coach.summarize
# ---------------------------------------------------------------------------------------------


def summarize(inp: SummarizeInput) -> str:
    user_lines = [m.content.strip().replace("\n", " ") for m in inp.messages if m.role == "user"]
    new = " | ".join(line[:80] for line in user_lines[-6:])
    summary = f"{inp.previous_summary} Recent: {new}".strip() if new else inp.previous_summary
    words = summary.split()
    return " ".join(words[-150:]) or f"Conversation about the goal '{inp.goal_title}'."
