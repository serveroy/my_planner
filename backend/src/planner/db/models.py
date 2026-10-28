"""SQLAlchemy ORM models.

Plans are stored as JSON documents (validated by ``planner.llm.contracts.Plan``) and versioned:
every applied revision writes a new ``PlanVersion``. Task progress is stored as ``TaskLog`` rows
keyed by the plan's stable task ids, so logs survive revisions.
"""

from datetime import date, datetime, timezone
from typing import Any

from sqlalchemy import JSON, Boolean, Date, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Base(DeclarativeBase):
    type_annotation_map = {dict[str, Any]: JSON, list[Any]: JSON}


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    display_name: Mapped[str] = mapped_column(String(100))
    language: Mapped[str] = mapped_column(String(5), default="en")  # UI language: "en" | "he"
    timezone: Mapped[str] = mapped_column(String(64), default="Asia/Jerusalem")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    goals: Mapped[list["Goal"]] = relationship(back_populates="user", cascade="all, delete-orphan")


class PushToken(Base):
    __tablename__ = "push_tokens"
    __table_args__ = (UniqueConstraint("user_id", "token"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    token: Mapped[str] = mapped_column(String(255))
    platform: Mapped[str] = mapped_column(String(20), default="unknown")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class Goal(Base):
    __tablename__ = "goals"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)

    # What the user typed when creating the goal.
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text, default="")
    current_state: Mapped[str] = mapped_column(Text, default="")
    deadline: Mapped[date] = mapped_column(Date)
    available_time: Mapped[dict[str, Any]] = mapped_column(default=dict)  # AvailableTime
    answer_format: Mapped[dict[str, Any]] = mapped_column(default=dict)  # AnswerFormat
    extra_context: Mapped[str] = mapped_column(Text, default="")

    # Behaviour settings.
    update_mode: Mapped[str] = mapped_column(String(10), default="ask")  # "auto" | "ask"
    checkin_settings: Mapped[dict[str, Any]] = mapped_column(default=dict)  # CheckinSettings

    # intake -> planning -> active -> (paused | completed | archived)
    status: Mapped[str] = mapped_column(String(20), default="intake")

    # Filled by the intake interview.
    profile: Mapped[dict[str, Any]] = mapped_column(default=dict)  # normalized facts, e.g. {"age": 31}
    intake_summary: Mapped[str] = mapped_column(Text, default="")
    safety_flags: Mapped[list[Any]] = mapped_column(default=list)  # SafetyFlag dicts
    constraints: Mapped[list[Any]] = mapped_column(default=list)  # constraints learned from chat

    current_plan_version: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Rolling conversation memory (coach.summarize).
    memory_summary: Mapped[str] = mapped_column(Text, default="")
    memory_cursor: Mapped[int] = mapped_column(Integer, default=0)  # last ChatMessage.id summarized

    last_user_activity_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)

    user: Mapped[User] = relationship(back_populates="goals")
    intake_turns: Mapped[list["IntakeTurn"]] = relationship(
        back_populates="goal", cascade="all, delete-orphan", order_by="IntakeTurn.index"
    )


class IntakeTurn(Base):
    """One question asked by planner.interview and the user's answer."""

    __tablename__ = "intake_turns"

    id: Mapped[int] = mapped_column(primary_key=True)
    goal_id: Mapped[int] = mapped_column(ForeignKey("goals.id", ondelete="CASCADE"), index=True)
    index: Mapped[int] = mapped_column(Integer)
    question: Mapped[str] = mapped_column(Text)
    field: Mapped[str] = mapped_column(String(64))
    answer_type: Mapped[str] = mapped_column(String(20), default="text")
    options: Mapped[list[Any]] = mapped_column(default=list)
    unit: Mapped[str | None] = mapped_column(String(20), nullable=True)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    answer: Mapped[str | None] = mapped_column(Text, nullable=True)
    skipped: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    answered_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    goal: Mapped[Goal] = relationship(back_populates="intake_turns")


class PlanVersion(Base):
    __tablename__ = "plan_versions"
    __table_args__ = (UniqueConstraint("goal_id", "version"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    goal_id: Mapped[int] = mapped_column(ForeignKey("goals.id", ondelete="CASCADE"), index=True)
    version: Mapped[int] = mapped_column(Integer)
    content: Mapped[dict[str, Any]] = mapped_column()  # Plan
    source: Mapped[str] = mapped_column(String(20))  # "generated" | "revision"
    revision_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class PlanRevision(Base):
    """A proposed change to the plan, produced by planner.revise."""

    __tablename__ = "plan_revisions"

    id: Mapped[int] = mapped_column(primary_key=True)
    goal_id: Mapped[int] = mapped_column(ForeignKey("goals.id", ondelete="CASCADE"), index=True)
    base_version: Mapped[int] = mapped_column(Integer)
    new_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    trigger: Mapped[str] = mapped_column(String(30))
    trigger_details: Mapped[str] = mapped_column(Text, default="")
    explanation: Mapped[str] = mapped_column(Text, default="")
    operations: Mapped[list[Any]] = mapped_column(default=list)  # RevisionOp dicts
    status: Mapped[str] = mapped_column(String(20), default="pending")  # pending|applied|rejected|superseded|no_change
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class TaskLog(Base):
    __tablename__ = "task_logs"
    __table_args__ = (UniqueConstraint("goal_id", "task_id", "date"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    goal_id: Mapped[int] = mapped_column(ForeignKey("goals.id", ondelete="CASCADE"), index=True)
    task_id: Mapped[str] = mapped_column(String(32))
    date: Mapped[date] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(10))  # done | partial | skipped
    note: Mapped[str] = mapped_column(Text, default="")
    source: Mapped[str] = mapped_column(String(10), default="user")  # user | chat
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class MetricLog(Base):
    __tablename__ = "metric_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    goal_id: Mapped[int] = mapped_column(ForeignKey("goals.id", ondelete="CASCADE"), index=True)
    metric_key: Mapped[str] = mapped_column(String(64))
    value: Mapped[float] = mapped_column(Float)
    date: Mapped[date] = mapped_column(Date)
    note: Mapped[str] = mapped_column(Text, default="")
    source: Mapped[str] = mapped_column(String(10), default="user")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id: Mapped[int] = mapped_column(primary_key=True)
    goal_id: Mapped[int] = mapped_column(ForeignKey("goals.id", ondelete="CASCADE"), index=True)
    role: Mapped[str] = mapped_column(String(10))  # user | assistant
    # chat | checkin | plan_ready | revision_proposal | revision_applied | safety
    kind: Mapped[str] = mapped_column(String(20), default="chat")
    content: Mapped[str] = mapped_column(Text)
    meta: Mapped[dict[str, Any]] = mapped_column(default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class CheckinLog(Base):
    """Remembers which proactive check-ins were sent, for de-duplication and rate limits."""

    __tablename__ = "checkin_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    goal_id: Mapped[int] = mapped_column(ForeignKey("goals.id", ondelete="CASCADE"), index=True)
    trigger: Mapped[str] = mapped_column(String(30))
    local_date: Mapped[date] = mapped_column(Date)
    dedupe_key: Mapped[str] = mapped_column(String(100), index=True)
    message_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    goal_id: Mapped[int | None] = mapped_column(ForeignKey("goals.id", ondelete="CASCADE"), nullable=True)
    type: Mapped[str] = mapped_column(String(30))  # checkin | revision_proposal | revision_applied | plan_ready
    title: Mapped[str] = mapped_column(String(200))
    body: Mapped[str] = mapped_column(Text)
    data: Mapped[dict[str, Any]] = mapped_column(default=dict)
    read_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
