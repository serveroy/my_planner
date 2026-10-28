"""Mock planner.interview: domain question banks with a few adaptive follow-ups."""

from dataclasses import dataclass, field

from planner.llm.contracts import InterviewInput, InterviewOutput, Language
from planner.llm.mock.common import detect_domain, first_number, is_negative_answer, t


HE_UNITS = {"years": "שנים", "cm": "ס\"מ", "kg": "ק\"ג", "km": "ק\"מ"}


@dataclass
class Q:
    field: str
    en: str
    he: str
    answer_type: str = "text"
    options_en: list[str] = field(default_factory=list)
    options_he: list[str] = field(default_factory=list)
    unit: str | None = None
    why_en: str = ""
    why_he: str = ""

    def render(self, lang: Language) -> InterviewOutput:
        return InterviewOutput(
            action="ask",
            question=t(lang, self.en, self.he),
            field=self.field,
            answer_type=self.answer_type,  # type: ignore[arg-type]
            options=self.options_he if lang == "he" else self.options_en,
            unit=HE_UNITS.get(self.unit or "", self.unit) if lang == "he" else self.unit,
            reason=t(lang, self.why_en, self.why_he) or None,
        )


AGE = Q("age", "How old are you?", "מה הגיל שלך?", "number", unit="years",
        why_en="Safe intensity depends on age.", why_he="העומס הבטוח תלוי בגיל.")
HEALTH = Q("health_conditions", "Any health conditions, injuries or medications I should know about?",
           "יש מצב בריאותי, פציעה או תרופות שכדאי שאדע עליהם?",
           why_en="So the plan stays safe for you.", why_he="כדי שהתוכנית תהיה בטוחה עבורך.")
MOTIVATION = Q("motivation", "Why is this goal important to you right now?", "למה המטרה הזו חשובה לך דווקא עכשיו?",
               why_en="I'll use it to keep you motivated.", why_he="אשתמש בזה כדי לשמור על המוטיבציה שלך.")
OBSTACLES = Q("obstacles", "What usually gets in the way when you try things like this?",
              "מה בדרך כלל מפריע לך כשאת/ה מנסה דברים כאלה?",
              why_en="We'll plan around it.", why_he="נתכנן מראש סביב זה.")

BANKS: dict[str, list[Q]] = {
    "weight": [
        AGE,
        Q("height_cm", "What is your height?", "מה הגובה שלך?", "number", unit="cm",
          why_en="Needed to estimate a healthy target.", why_he="נדרש כדי להעריך יעד בריא."),
        Q("weight_kg", "What is your current weight?", "מה המשקל הנוכחי שלך?", "number", unit="kg",
          why_en="This is your starting point.", why_he="זו נקודת ההתחלה שלך."),
        Q("target_weight_kg", "What weight would you like to reach?", "לאיזה משקל היית רוצה להגיע?", "number", unit="kg",
          why_en="So we can set a safe pace.", why_he="כדי לקבוע קצב בטוח."),
        Q("activity_level", "How active are you today?", "כמה את/ה פעיל/ה היום?", "choice",
          ["Mostly sitting", "Light activity", "Moderately active", "Very active"],
          ["בעיקר יושב/ת", "פעילות קלה", "פעילות בינונית", "פעיל/ה מאוד"],
          why_en="Sets the starting workload.", why_he="קובע את עומס ההתחלה."),
        Q("exercise_preferences", "Which kinds of exercise do you enjoy (or could tolerate)?",
          "אילו סוגי פעילות את/ה אוהב/ת (או מוכן/ה לנסות)?", "multi_choice",
          ["Walking", "Running", "Gym", "Home workouts", "Swimming", "Cycling", "Classes"],
          ["הליכה", "ריצה", "חדר כושר", "אימונים בבית", "שחייה", "אופניים", "שיעורים"],
          why_en="You'll stick to what you enjoy.", why_he="קל יותר להתמיד במה שנהנים ממנו."),
        Q("diet", "Any dietary preferences or restrictions?", "יש העדפות או מגבלות תזונה?", "multi_choice",
          ["No restrictions", "Vegetarian", "Vegan", "Kosher", "Gluten-free", "Lactose-free"],
          ["אין מגבלות", "צמחוני", "טבעוני", "כשר", "ללא גלוטן", "ללא לקטוז"]),
        HEALTH,
        OBSTACLES,
    ],
    "running": [
        AGE,
        Q("running_experience", "How often do you run today?", "כמה את/ה רץ/ה היום?", "choice",
          ["Never", "Occasionally", "1-2 times a week", "3+ times a week"],
          ["בכלל לא", "לפעמים", "1-2 פעמים בשבוע", "3 פעמים בשבוע ומעלה"],
          why_en="Sets where we start.", why_he="קובע מאיפה מתחילים."),
        Q("longest_run_km", "What's the longest distance you can run comfortably right now?",
          "מה המרחק הארוך ביותר שאת/ה יכול/ה לרוץ בנוחות כרגע?", "number", unit="km"),
        Q("target", "What exactly is the target (distance and, if any, time)?", "מה בדיוק היעד (מרחק, ואם יש - זמן)?",
          why_en="Defines the training load.", why_he="מגדיר את עומס האימונים."),
        HEALTH,
        MOTIVATION,
    ],
    "fitness": [
        AGE,
        Q("fitness_level", "How would you describe your current fitness?", "איך היית מתאר/ת את הכושר שלך היום?", "choice",
          ["Beginner", "Some experience", "Trains regularly", "Advanced"],
          ["מתחיל/ה", "קצת ניסיון", "מתאמן/ת באופן קבוע", "מתקדם/ת"]),
        Q("equipment", "Where will you train?", "איפה תתאמן/י?", "choice",
          ["Gym", "Home with equipment", "Home, no equipment", "Outdoors"],
          ["חדר כושר", "בבית עם ציוד", "בבית בלי ציוד", "בחוץ"]),
        Q("specific_target", "What's a concrete result you want (e.g. 10 pull-ups)?", "מה תוצאה מוחשית שהיית רוצה (למשל 10 עליות מתח)?"),
        HEALTH,
        OBSTACLES,
    ],
    "study": [
        Q("subject", "Which subject or exam is it, exactly?", "על איזה מקצוע או מבחן מדובר בדיוק?",
          why_en="Different exams need different strategies.", why_he="למבחנים שונים יש אסטרטגיות שונות."),
        Q("current_level", "How well do you know the material today?", "כמה טוב את/ה מכיר/ה את החומר היום?", "choice",
          ["Starting from zero", "Know a little", "Know most of it", "Just need practice"],
          ["מתחיל/ה מאפס", "יודע/ת קצת", "יודע/ת את רובו", "צריך/ה רק תרגול"]),
        Q("material_scope", "How much material is there (chapters, topics, pages)?", "כמה חומר יש (פרקים, נושאים, עמודים)?",
          why_en="So the schedule covers everything.", why_he="כדי שהלו\"ז יכסה הכל."),
        Q("resources", "What do you have to study from?", "ממה יש לך ללמוד?", "multi_choice",
          ["Textbook", "Past exams", "Online course", "Tutor", "Lecture notes"],
          ["ספר לימוד", "מבחנים קודמים", "קורס אונליין", "מורה פרטי", "סיכומים"]),
        Q("weak_topics", "Which topics feel hardest?", "אילו נושאים מרגישים הכי קשים?"),
        Q("target_score", "What score are you aiming for?", "לאיזה ציון את/ה מכוון/ת?", "number"),
        OBSTACLES,
    ],
    "language": [
        Q("target_language", "Which language are you learning?", "איזו שפה את/ה לומד/ת?"),
        Q("current_level", "What's your level today?", "מה הרמה שלך היום?", "choice",
          ["Complete beginner", "Basic phrases", "Can hold a simple conversation", "Intermediate", "Advanced"],
          ["מתחיל/ה לגמרי", "משפטים בסיסיים", "מסוגל/ת לשיחה פשוטה", "בינוני", "מתקדם"]),
        Q("purpose", "What do you need the language for?", "למה את/ה צריך/ה את השפה?", "multi_choice",
          ["Travel", "Work", "An exam", "Conversation", "Reading and media"],
          ["טיולים", "עבודה", "מבחן", "שיחה", "קריאה ותוכן"]),
        Q("learning_style", "How do you like to learn?", "איך את/ה אוהב/ת ללמוד?", "multi_choice",
          ["Apps", "Reading", "Speaking with people", "Videos and podcasts", "Classes"],
          ["אפליקציות", "קריאה", "דיבור עם אנשים", "סרטונים ופודקאסטים", "שיעורים"]),
        MOTIVATION,
    ],
    "finance": [
        Q("currency", "Which currency do you use?", "באיזה מטבע מדובר?", "choice", ["ILS (₪)", "USD ($)", "EUR (€)"],
          ["שקל (₪)", "דולר ($)", "יורו (€)"]),
        Q("target_amount", "How much do you want to save in total?", "כמה את/ה רוצה לחסוך בסך הכל?", "number"),
        Q("current_savings", "How much have you already saved for this?", "כמה כבר חסכת למטרה הזו?", "number"),
        Q("monthly_income", "What is your monthly net income (roughly)?", "מה ההכנסה החודשית נטו (בערך)?", "number",
          why_en="To set a realistic monthly amount.", why_he="כדי לקבוע סכום חודשי ריאלי."),
        Q("monthly_expenses", "And your monthly expenses (roughly)?", "וההוצאות החודשיות (בערך)?", "number"),
        Q("debts", "Do you have debts or loans with interest?", "יש לך חובות או הלוואות עם ריבית?", "boolean",
          why_en="High-interest debt usually comes first.", why_he="בדרך כלל עדיף לסגור קודם חוב עם ריבית גבוהה."),
        OBSTACLES,
    ],
    "skill": [
        Q("experience", "What's your experience with this so far?", "מה הניסיון שלך בתחום עד עכשיו?", "choice",
          ["None", "Tried a little", "Some real practice", "Experienced"],
          ["אין", "ניסיתי קצת", "תרגלתי לא מעט", "מנוסה"]),
        Q("target_outcome", "What do you want to be able to do by the deadline?", "מה תרצה/י לדעת לעשות עד תאריך היעד?"),
        Q("resources", "Which resources do you have or prefer?", "באילו משאבים יש לך או את/ה מעדיף/ה?", "multi_choice",
          ["Online course", "Books", "YouTube", "A teacher/mentor", "Building projects"],
          ["קורס אונליין", "ספרים", "יוטיוב", "מורה/מנטור", "בניית פרויקטים"]),
        MOTIVATION,
        OBSTACLES,
    ],
    "habit": [
        Q("current_frequency", "How often do you do it today?", "כמה פעמים את/ה עושה את זה היום?"),
        Q("best_time", "When in the day would it fit best?", "מתי ביום זה הכי יתאים לך?", "choice",
          ["Morning", "Afternoon", "Evening", "Before bed"], ["בוקר", "צהריים", "ערב", "לפני השינה"]),
        OBSTACLES,
        MOTIVATION,
    ],
    "general": [
        Q("experience", "Have you worked on a goal like this before?", "עבדת בעבר על מטרה דומה?", "choice",
          ["Never", "Once or twice", "Many times"], ["אף פעם", "פעם-פעמיים", "הרבה פעמים"]),
        Q("success_definition", "How will you know you've succeeded?", "איך תדע/י שהצלחת?",
          why_en="Gives us a measurable finish line.", why_he="נותן לנו קו סיום מדיד."),
        Q("resources", "What support or resources do you have?", "איזו תמיכה או משאבים יש לך?"),
        MOTIVATION,
        OBSTACLES,
    ],
}

MINOR_FOLLOWUP = Q("adult_involved", "Is a parent or doctor involved in this goal?", "האם הורה או רופא/ה מעורבים במטרה הזו?",
                   "boolean", why_en="For under-18s we keep the plan extra safe.", why_he="מתחת לגיל 18 נשמור על תוכנית בטוחה במיוחד.")
DOCTOR_FOLLOWUP = Q("doctor_approved", "Has a doctor approved this kind of activity for you?",
                    "האם רופא/ה אישר/ה לך פעילות מהסוג הזה?", "boolean",
                    why_en="Because you mentioned a health condition.", why_he="כי ציינת מצב בריאותי.")


def _adaptive_next(inp: InterviewInput, domain: str, answers: dict[str, str | None]) -> Q | None:
    """Follow-ups that depend on earlier answers."""
    age = first_number(answers.get("age"))
    if age is not None and age < 18 and domain in ("weight", "fitness", "running") and "adult_involved" not in answers:
        return MINOR_FOLLOWUP
    if not is_negative_answer(answers.get("health_conditions", "none")) and "doctor_approved" not in answers:
        return DOCTOR_FOLLOWUP
    return None


def _irrelevant(q: Q, answers: dict[str, str | None]) -> bool:
    return q.field == "longest_run_km" and answers.get("running_experience") in ("Never", "בכלל לא")


def _normalize(q_type: str, answer: str | None):
    if answer is None:
        return None
    if q_type == "number":
        return first_number(answer)
    if q_type == "boolean":
        return answer.strip().lower() in {"yes", "y", "true", "כן", "נכון", "בטח"}
    if q_type == "multi_choice":
        return [a.strip() for a in answer.split(",") if a.strip()]
    return answer.strip()


def _fmt(v) -> str:
    if isinstance(v, float) and v.is_integer():
        return str(int(v))
    if isinstance(v, list):
        return ", ".join(map(str, v))
    return str(v)


def interview(inp: InterviewInput) -> InterviewOutput:
    lang = inp.style.language
    domain = detect_domain(inp.goal)
    bank = BANKS[domain]
    answers = {qa.field: (None if qa.skipped else qa.answer) for qa in inp.qa_history}
    asked = set(answers)

    nxt = None
    if inp.questions_remaining > 0:
        nxt = _adaptive_next(inp, domain, answers)
        if nxt is None:
            nxt = next((q for q in bank if q.field not in asked and not _irrelevant(q, answers)), None)
    if nxt is not None:
        return nxt.render(lang)

    types = {q.field: q.answer_type for q in [*bank, MINOR_FOLLOWUP, DOCTOR_FOLLOWUP]}
    profile = {
        qa.field: _normalize(types.get(qa.field, "text"), qa.answer)
        for qa in inp.qa_history
        if not qa.skipped and qa.answer
    }
    profile["domain"] = domain
    facts = "; ".join(f"{k.replace('_', ' ')}: {_fmt(v)}" for k, v in profile.items() if k != "domain")
    summary = t(
        lang,
        f"Goal: {inp.goal.title}. What I learned — {facts or 'no extra details'}. I'll build your plan around this.",
        f"המטרה: {inp.goal.title}. מה שלמדתי — {facts or 'אין פרטים נוספים'}. אבנה את התוכנית סביב זה.",
    )
    return InterviewOutput(action="finish", profile=profile, summary=summary)
