"""Request/response bodies of the REST API (the Expo app mirrors these in src/api/types.ts)."""

import datetime as dt
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from planner.llm.contracts import (
    AnswerFormat,
    AvailableTime,
    CheckinSettings,
    Plan,
    ProgressReport,
    SafetyFlag,
    TodayTask,
)


class Out(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# ---- auth / user ------------------------------------------------------------------------------


class RegisterIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    display_name: str = Field(min_length=1, max_length=100)
    language: Literal["en", "he"] = "en"
    timezone: str = "Asia/Jerusalem"


class LoginIn(BaseModel):
    email: EmailStr
    password: str


class UserOut(Out):
    id: int
    email: str
    display_name: str
    language: str
    timezone: str


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


class UserPatch(BaseModel):
    display_name: str | None = Field(None, min_length=1, max_length=100)
    language: Literal["en", "he"] | None = None
    timezone: str | None = None


class PushTokenIn(BaseModel):
    token: str = Field(min_length=10, max_length=255)
    platform: str = "unknown"


# ---- goals ------------------------------------------------------------------------------------

UpdateMode = Literal["auto", "ask"]


class GoalCreate(BaseModel):
    title: str = Field(min_length=2, max_length=200)
    description: str = ""
    current_state: str = ""
    deadline: dt.date
    available_time: AvailableTime = AvailableTime()
    answer_format: AnswerFormat = AnswerFormat()
    extra_context: str = ""
    update_mode: UpdateMode = "ask"
    checkin_settings: CheckinSettings = CheckinSettings()


class GoalPatch(BaseModel):
    title: str | None = Field(None, min_length=2, max_length=200)
    deadline: dt.date | None = None
    available_time: AvailableTime | None = None
    answer_format: AnswerFormat | None = None
    update_mode: UpdateMode | None = None
    checkin_settings: CheckinSettings | None = None
    status: Literal["active", "paused", "completed", "archived"] | None = None


class GoalOut(Out):
    id: int
    title: str
    description: str
    current_state: str
    deadline: dt.date
    available_time: AvailableTime
    answer_format: AnswerFormat
    extra_context: str
    update_mode: UpdateMode
    checkin_settings: CheckinSettings
    status: str
    intake_summary: str
    profile: dict[str, Any]
    safety_flags: list[SafetyFlag]
    constraints: list[dict[str, Any]]
    current_plan_version: int | None
    created_at: dt.datetime
    has_pending_revision: bool = False
    unread_notifications: int = 0


# ---- intake -----------------------------------------------------------------------------------


class IntakeTurnOut(Out):
    id: int
    index: int
    question: str
    field: str
    answer_type: str
    options: list[str]
    unit: str | None
    reason: str | None
    answer: str | None
    skipped: bool


class IntakeStateOut(BaseModel):
    status: Literal["in_progress", "finished"]
    current: IntakeTurnOut | None
    history: list[IntakeTurnOut]
    summary: str
    max_questions: int


class AnswerIn(BaseModel):
    turn_id: int
    answer: str | None = None
    skip: bool = False


# ---- plan & progress --------------------------------------------------------------------------


class PlanOut(BaseModel):
    version: int
    source: str
    created_at: dt.datetime
    plan: Plan
    warnings: list[str] = []


class PlanVersionOut(Out):
    version: int
    source: str
    revision_id: int | None
    created_at: dt.datetime


class TodayOut(BaseModel):
    date: dt.date
    tasks: list[TodayTask]


class TaskLogIn(BaseModel):
    date: dt.date
    status: Literal["done", "partial", "skipped", "pending"]  # "pending" clears the log
    note: str = ""


class MetricLogIn(BaseModel):
    value: float
    date: dt.date | None = None
    note: str = ""


class MetricPoint(BaseModel):
    date: dt.date
    value: float


class ProgressOut(BaseModel):
    report: ProgressReport
    metric_history: dict[str, list[MetricPoint]]


class RevisionOut(Out):
    id: int
    trigger: str
    trigger_details: str
    explanation: str
    operations: list[dict[str, Any]]
    changes: list[str] = []
    status: str
    base_version: int
    new_version: int | None
    created_at: dt.datetime
    decided_at: dt.datetime | None


class RevisionRequestIn(BaseModel):
    message: str = Field(min_length=2, max_length=2000)


# ---- chat & notifications ---------------------------------------------------------------------


class ChatMessageOut(Out):
    id: int
    role: str
    kind: str
    content: str
    meta: dict[str, Any]
    created_at: dt.datetime


class ChatIn(BaseModel):
    content: str = Field(min_length=1, max_length=4000)


class ChatOut(BaseModel):
    user_message: ChatMessageOut
    reply: ChatMessageOut
    actions: list[str]
    revision_in_progress: bool


class NotificationOut(Out):
    id: int
    goal_id: int | None
    type: str
    title: str
    body: str
    data: dict[str, Any]
    read_at: dt.datetime | None
    created_at: dt.datetime


class TickIn(BaseModel):
    now: dt.datetime | None = None  # simulate a moment in time (UTC); default: real now
