"""Input/output contracts for every model task.

These Pydantic models are the single source of truth for what each fine-tuned model receives and
must produce. The synthetic fine-tuning data has to follow them exactly; run
``uv run planner-export-contracts`` to regenerate the JSON Schemas under ``docs/contracts``.

Tasks (model role . task):
    planner.interview  -> next intake question, or finish with a normalized profile
    planner.generate   -> a full structured Plan
    planner.revise     -> a list of edit operations on the current Plan
    coach.chat         -> a free-text reply in the user's conversation
    coach.checkin      -> a short proactive message (e.g. "did you work out today?")
    coach.extract      -> structured events found in a user message (task done, weight, constraint...)
    coach.summarize    -> rolling conversation memory (free text)
"""

import re
import datetime as dt
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

Language = Literal["he", "en"]
Weekday = Literal["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
WEEKDAYS: list[Weekday] = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
TimeOfDay = Literal["morning", "afternoon", "evening", "any"]

_ID_RE = re.compile(r"^[a-z0-9_-]{1,32}$")
_KEY_RE = re.compile(r"^[a-z][a-z0-9_]{0,63}$")


class Contract(BaseModel):
    # Small models sometimes add stray keys; ignore them instead of failing the whole call.
    model_config = ConfigDict(extra="ignore")


# --------------------------------------------------------------------------------------------
# Settings the user chooses (also passed to the models)
# --------------------------------------------------------------------------------------------


class AvailableTime(Contract):
    minutes_per_day: int = Field(30, ge=5, le=24 * 60)
    days_per_week: int = Field(5, ge=1, le=7)
    preferred_days: list[Weekday] = []
    preferred_time_of_day: TimeOfDay = "any"
    notes: str = ""


class AnswerFormat(Contract):
    """How the user wants to be answered. ``language="auto"`` means: match the user's message."""

    language: Literal["he", "en", "auto"] = "auto"
    verbosity: Literal["concise", "balanced", "detailed"] = "balanced"
    tone: Literal["warm", "direct", "motivational"] = "warm"
    style: Literal["bullets", "paragraphs", "mixed"] = "mixed"
    use_emojis: bool = False
    notes: str = ""

    def resolve(self, language: Language) -> "ResponseStyle":
        lang = self.language if self.language != "auto" else language
        return ResponseStyle(**{**self.model_dump(), "language": lang})


class ResponseStyle(AnswerFormat):
    """``AnswerFormat`` with the language already resolved. This is what the models see."""

    language: Language


class CheckinSettings(Contract):
    enabled: bool = True
    daily_time: str = "20:00"  # local HH:MM for the daily "how did today go?" check-in
    max_per_day: int = Field(2, ge=0, le=10)
    quiet_start: str = "22:30"
    quiet_end: str = "08:00"
    inactivity_days: int = Field(3, ge=1, le=30)

    @field_validator("daily_time", "quiet_start", "quiet_end")
    @classmethod
    def _hhmm(cls, v: str) -> str:
        if not re.fullmatch(r"([01]\d|2[0-3]):[0-5]\d", v):
            raise ValueError("expected HH:MM")
        return v


class SafetyFlag(Contract):
    code: str  # e.g. "minor_weight_loss", "underweight_target", "crisis_language"
    severity: Literal["info", "caution", "high"]
    guidance: str  # instruction for the models, in English


class GoalBrief(Contract):
    title: str
    description: str = ""
    current_state: str = ""
    deadline: dt.date
    available_time: AvailableTime = AvailableTime()
    extra_context: str = ""


# --------------------------------------------------------------------------------------------
# Plan document (output of planner.generate, edited by planner.revise)
# --------------------------------------------------------------------------------------------


class TaskSchedule(Contract):
    type: Literal["once", "daily", "weekly", "every_n_days"]
    date: dt.date | None = None  # for "once"
    days_of_week: list[Weekday] = []  # for "weekly"
    interval_days: int | None = Field(None, ge=2, le=60)  # for "every_n_days"
    start_date: dt.date | None = None  # defaults to plan start
    end_date: dt.date | None = None  # defaults to plan end
    time_of_day: TimeOfDay = "any"

    @model_validator(mode="after")
    def _check(self) -> "TaskSchedule":
        if self.type == "once" and self.date is None:
            raise ValueError("schedule type 'once' requires 'date'")
        if self.type == "weekly" and not self.days_of_week:
            raise ValueError("schedule type 'weekly' requires 'days_of_week'")
        if self.type == "every_n_days" and self.interval_days is None:
            raise ValueError("schedule type 'every_n_days' requires 'interval_days'")
        if self.start_date and self.end_date and self.end_date < self.start_date:
            raise ValueError("schedule end_date is before start_date")
        return self


class PlanTask(Contract):
    id: str
    title: str
    description: str = ""
    milestone_id: str | None = None
    schedule: TaskSchedule
    duration_minutes: int | None = Field(None, ge=1, le=600)
    metric_key: str | None = None  # completing this task is when the user should log this metric

    @field_validator("id")
    @classmethod
    def _id(cls, v: str) -> str:
        if not _ID_RE.match(v):
            raise ValueError("task id must match [a-z0-9_-]{1,32}")
        return v


class Milestone(Contract):
    id: str
    title: str
    description: str = ""
    target_date: dt.date
    success_criteria: str = ""

    @field_validator("id")
    @classmethod
    def _id(cls, v: str) -> str:
        if not _ID_RE.match(v):
            raise ValueError("milestone id must match [a-z0-9_-]{1,32}")
        return v


class Metric(Contract):
    key: str
    name: str
    unit: str = ""
    baseline: float | None = None
    target: float | None = None
    direction: Literal["increase", "decrease", "maintain"] = "increase"

    @field_validator("key")
    @classmethod
    def _key(cls, v: str) -> str:
        if not _KEY_RE.match(v):
            raise ValueError("metric key must be snake_case")
        return v


class Plan(Contract):
    title: str
    summary: str
    start_date: dt.date
    end_date: dt.date
    milestones: list[Milestone] = []
    tasks: list[PlanTask] = Field(min_length=1)
    metrics: list[Metric] = []
    tips: list[str] = []
    safety_notes: list[str] = []
    assumptions: list[str] = []

    @model_validator(mode="after")
    def _references(self) -> "Plan":
        if self.end_date < self.start_date:
            raise ValueError("plan end_date is before start_date")
        for kind, ids in (
            ("task", [t.id for t in self.tasks]),
            ("milestone", [m.id for m in self.milestones]),
            ("metric", [m.key for m in self.metrics]),
        ):
            if len(ids) != len(set(ids)):
                raise ValueError(f"duplicate {kind} ids")
        milestone_ids = {m.id for m in self.milestones}
        metric_keys = {m.key for m in self.metrics}
        for t in self.tasks:
            if t.milestone_id and t.milestone_id not in milestone_ids:
                raise ValueError(f"task {t.id} references unknown milestone {t.milestone_id}")
            if t.metric_key and t.metric_key not in metric_keys:
                raise ValueError(f"task {t.id} references unknown metric {t.metric_key}")
        return self


# --------------------------------------------------------------------------------------------
# planner.interview
# --------------------------------------------------------------------------------------------


class QAItem(Contract):
    question: str
    field: str
    answer: str | None = None
    skipped: bool = False


class InterviewInput(Contract):
    today: dt.date
    goal: GoalBrief
    style: ResponseStyle
    qa_history: list[QAItem] = []
    questions_remaining: int
    safety_flags: list[SafetyFlag] = []


class InterviewOutput(Contract):
    action: Literal["ask", "finish"]
    # action == "ask"
    question: str | None = None
    field: str | None = None  # snake_case key the answer will be stored under, e.g. "weight_kg"
    answer_type: Literal["text", "number", "choice", "multi_choice", "date", "boolean"] = "text"
    options: list[str] = []
    unit: str | None = None
    reason: str | None = None  # one short line: why this matters for the plan (shown to the user)
    # action == "finish"
    profile: dict[str, Any] = {}  # normalized facts collected, e.g. {"age": 31, "weight_kg": 82}
    summary: str | None = None  # what the planner understood, in the user's language

    @model_validator(mode="after")
    def _check(self) -> "InterviewOutput":
        if self.action == "ask":
            if not self.question or not self.field:
                raise ValueError("action 'ask' requires 'question' and 'field'")
            if self.answer_type in ("choice", "multi_choice") and len(self.options) < 2:
                raise ValueError("choice questions need at least two options")
        return self


# --------------------------------------------------------------------------------------------
# planner.generate
# --------------------------------------------------------------------------------------------


class GenerateInput(Contract):
    today: dt.date
    goal: GoalBrief
    style: ResponseStyle
    profile: dict[str, Any] = {}
    intake_summary: str = ""
    qa_history: list[QAItem] = []
    safety_flags: list[SafetyFlag] = []


# --------------------------------------------------------------------------------------------
# Progress (input to planner.revise and the coach)
# --------------------------------------------------------------------------------------------


class TaskProgress(Contract):
    task_id: str
    title: str
    due: int
    done: int
    partial: int = 0
    skipped: int = 0
    adherence: float | None = None  # (done + 0.5 * partial) / due, None when nothing was due


class MetricProgress(Contract):
    key: str
    name: str
    unit: str = ""
    baseline: float | None = None
    target: float | None = None
    direction: Literal["increase", "decrease", "maintain"] = "increase"
    latest: float | None = None
    latest_date: dt.date | None = None
    expected_now: float | None = None  # linear interpolation baseline -> target at today's date


class MilestoneStatus(Contract):
    id: str
    title: str
    target_date: dt.date
    status: Literal["upcoming", "due_soon", "overdue", "passed"]


class ProgressReport(Contract):
    as_of: dt.date
    days_elapsed: int
    days_left: int
    adherence_7d: float | None = None
    adherence_28d: float | None = None
    streak_days: int = 0  # consecutive days (ending yesterday or today) where every due task was done
    tasks: list[TaskProgress] = []
    metrics: list[MetricProgress] = []
    milestones: list[MilestoneStatus] = []


# --------------------------------------------------------------------------------------------
# planner.revise
# --------------------------------------------------------------------------------------------

RevisionTrigger = Literal[
    "user_request",
    "constraint_change",
    "low_adherence",
    "behind_schedule",
    "ahead_of_schedule",
    "weekly_review",
]

RevisionOpType = Literal[
    "add_task",
    "update_task",
    "remove_task",
    "add_milestone",
    "update_milestone",
    "remove_milestone",
    "add_metric",
    "update_metric",
    "update_plan",
]


class ReviseInput(Contract):
    today: dt.date
    goal: GoalBrief
    style: ResponseStyle
    plan: Plan
    progress: ProgressReport
    trigger: RevisionTrigger
    trigger_details: str = ""
    constraints: list[str] = []
    memory_summary: str = ""
    safety_flags: list[SafetyFlag] = []


class RevisionOp(Contract):
    op: RevisionOpType
    target_id: str | None = None  # task id / milestone id / metric key; None for add_* and update_plan
    data: dict[str, Any] = {}  # full object for add_*, changed fields only for update_*
    reason: str = ""


class ReviseOutput(Contract):
    should_revise: bool
    explanation: str  # user-facing, in the user's language: what changes and why
    operations: list[RevisionOp] = []


# --------------------------------------------------------------------------------------------
# coach.* shared context
# --------------------------------------------------------------------------------------------


class ChatTurn(Contract):
    role: Literal["user", "assistant"]
    content: str


class TodayTask(Contract):
    task_id: str
    title: str
    duration_minutes: int | None = None
    time_of_day: TimeOfDay = "any"
    status: Literal["pending", "done", "partial", "skipped"] = "pending"


class PlanOverviewTask(Contract):
    id: str
    title: str
    schedule: str  # human-readable, e.g. "weekly: mon, wed, fri (30 min, evening)"


class PlanOverview(Contract):
    title: str
    summary: str
    end_date: dt.date
    milestones: list[MilestoneStatus] = []
    tasks: list[PlanOverviewTask] = []
    metrics: list[MetricProgress] = []


class CoachContext(Contract):
    now: dt.datetime  # user's local time
    user_name: str
    style: ResponseStyle
    goal: GoalBrief
    plan: PlanOverview | None = None
    today_tasks: list[TodayTask] = []
    days_left: int | None = None
    adherence_7d: float | None = None
    streak_days: int = 0
    memory_summary: str = ""
    constraints: list[str] = []
    actions_taken: list[str] = []  # what the app just did because of the user's last message
    # The user's last message asked for a plan change; the planner is preparing it right now.
    revision_in_progress: bool = False
    plan_update_mode: Literal["auto", "ask"] = "ask"  # "ask": the user approves changes; "auto": applied directly
    pending_revision: str | None = None  # explanation of a plan change waiting for approval
    safety_flags: list[SafetyFlag] = []


# --------------------------------------------------------------------------------------------
# coach.chat / coach.checkin
# --------------------------------------------------------------------------------------------


class CoachChatInput(Contract):
    context: CoachContext
    messages: list[ChatTurn]  # recent conversation, oldest first; the last one is the user's


CheckinTrigger = Literal[
    "plan_ready",  # the plan was just created: welcome + what to do first
    "daily_tasks",  # evening: ask whether today's tasks were done
    "all_done",  # every task due today is logged as done: celebrate
    "missed_yesterday",  # yesterday's tasks were not logged
    "inactivity",  # user has not been active for N days
    "milestone_upcoming",  # a milestone is due within 2 days
    "metric_reminder",  # a tracked metric was not logged for a week
    "deadline_near",  # a week or less until the goal deadline
]


class CheckinInput(Contract):
    context: CoachContext
    trigger: CheckinTrigger
    trigger_details: str = ""
    recent_messages: list[ChatTurn] = []


# --------------------------------------------------------------------------------------------
# coach.extract
# --------------------------------------------------------------------------------------------


class ExtractTask(Contract):
    id: str
    title: str
    due_today: bool = False


class ExtractMetric(Contract):
    key: str
    name: str
    unit: str = ""


class ExtractInput(Contract):
    today: dt.date
    weekday: Weekday
    tasks: list[ExtractTask] = []
    metrics: list[ExtractMetric] = []
    recent_messages: list[ChatTurn] = []  # context only; extract events from `message`
    message: str


EventType = Literal[
    "task_done",
    "task_partial",
    "task_skipped",
    "metric_value",
    "constraint",  # a lasting change in availability/circumstances ("I can't train on Tuesdays")
    "plan_change_request",  # the user explicitly wants the plan changed
    "mood",
    "safety_concern",  # self-harm, disordered eating, injury, medical red flags
]


class ExtractedEvent(Contract):
    type: EventType
    task_id: str | None = None
    date: dt.date | None = None  # resolved absolute date ("yesterday" -> today - 1)
    metric_key: str | None = None
    value: float | None = None
    text: str | None = None  # constraint / change request / concern, paraphrased in English
    mood: Literal["positive", "neutral", "tired", "stressed", "frustrated", "demotivated"] | None = None


class ExtractOutput(Contract):
    events: list[ExtractedEvent] = []


# --------------------------------------------------------------------------------------------
# coach.summarize
# --------------------------------------------------------------------------------------------


class SummarizeInput(Contract):
    goal_title: str
    previous_summary: str = ""
    messages: list[ChatTurn]


# --------------------------------------------------------------------------------------------
# Registry
# --------------------------------------------------------------------------------------------


class TaskSpec(BaseModel):
    input: type[Contract]
    output: type[Contract] | None  # None -> free text


TASKS: dict[str, TaskSpec] = {
    "planner.interview": TaskSpec(input=InterviewInput, output=InterviewOutput),
    "planner.generate": TaskSpec(input=GenerateInput, output=Plan),
    "planner.revise": TaskSpec(input=ReviseInput, output=ReviseOutput),
    "coach.chat": TaskSpec(input=CoachChatInput, output=None),
    "coach.checkin": TaskSpec(input=CheckinInput, output=None),
    "coach.extract": TaskSpec(input=ExtractInput, output=ExtractOutput),
    "coach.summarize": TaskSpec(input=SummarizeInput, output=None),
}
