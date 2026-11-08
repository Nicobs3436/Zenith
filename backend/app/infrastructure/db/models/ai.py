from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.db.base import Base


class AiSuggestion(Base):
    __tablename__ = "ai_suggestions"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("users.id"), index=True)
    routine_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("routines.id"), index=True)
    routine_exercise_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("routine_exercises.id"), index=True
    )
    exercise_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("exercises.id"), index=True)
    type: Mapped[str] = mapped_column(String(40), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending", index=True)
    input_summary: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    recommendation: Mapped[str] = mapped_column(Text, nullable=False)
    explanation: Mapped[str] = mapped_column(Text, nullable=False)
    risk_notes: Mapped[str | None] = mapped_column(Text)
    confidence: Mapped[str | None] = mapped_column(String(10))
    apply_payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    applied_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AiTrainingPlan(Base):
    __tablename__ = "ai_training_plans"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("users.id"), index=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="draft", index=True)
    goal: Mapped[str] = mapped_column(String(40), nullable=False)
    level: Mapped[str] = mapped_column(String(40), nullable=False)
    days_per_week: Mapped[int] = mapped_column(Integer, nullable=False)
    session_duration_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    available_equipment: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    physical_limitations: Mapped[str | None] = mapped_column(Text)
    sensitive_data_acknowledged: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    priorities: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    plan_payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    explanation: Mapped[str] = mapped_column(Text, nullable=False)
    risk_notes: Mapped[str | None] = mapped_column(Text)
    confidence: Mapped[str | None] = mapped_column(String(10))
    input_summary: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    provider: Mapped[str] = mapped_column(String(40), nullable=False)
    model: Mapped[str | None] = mapped_column(String(80))
    fallback_used: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AiSessionSummary(Base):
    __tablename__ = "ai_session_summaries"
    __table_args__ = (UniqueConstraint("session_id", name="uq_ai_session_summaries_session_id"),)

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("users.id"), index=True)
    session_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("workout_sessions.id"), index=True)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    improvements: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    drops: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    warnings: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    next_recommendation: Mapped[str] = mapped_column(Text, nullable=False)
    input_summary: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    provider: Mapped[str] = mapped_column(String(40), nullable=False)
    model: Mapped[str | None] = mapped_column(String(80))
    fallback_used: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class AiCoachIntake(Base):
    __tablename__ = "ai_coach_intakes"
    __table_args__ = (UniqueConstraint("user_id", name="uq_ai_coach_intakes_user_id"),)

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("users.id"), index=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="collecting", index=True)
    intake_summary: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    recent_messages: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False, default=list)
    missing_required_fields: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    ready_for_plan: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    sensitive_data_acknowledged: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class CoachProfile(Base):
    __tablename__ = "coach_profiles"
    __table_args__ = (UniqueConstraint("user_id", name="uq_coach_profiles_user_id"),)

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("users.id"), index=True)
    goal: Mapped[str | None] = mapped_column(String(40))
    secondary_goal: Mapped[str | None] = mapped_column(String(40))
    plan_horizon_weeks: Mapped[int | None] = mapped_column(Integer)
    biological_sex: Mapped[str | None] = mapped_column(String(10))
    age: Mapped[int | None] = mapped_column(Integer)
    height_cm: Mapped[int | None] = mapped_column(Integer)
    weight_kg: Mapped[int | None] = mapped_column(Integer)
    experience_level: Mapped[str | None] = mapped_column(String(40))
    training_age_months: Mapped[int | None] = mapped_column(Integer)
    days_per_week: Mapped[int | None] = mapped_column(Integer)
    session_duration_minutes: Mapped[int | None] = mapped_column(Integer)
    equipment: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    priorities: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    preferred_exercises: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    avoided_exercises: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    physical_limitations: Mapped[str | None] = mapped_column(Text)
    sleep_quality: Mapped[str | None] = mapped_column(String(20))
    stress_level: Mapped[str | None] = mapped_column(String(20))
    current_fatigue: Mapped[str | None] = mapped_column(String(20))
    personal_data_acknowledged: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    sensitive_data_acknowledged: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    memory_summary: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class CoachConversation(Base):
    __tablename__ = "coach_conversations"
    __table_args__ = (UniqueConstraint("user_id", name="uq_coach_conversations_user_id"),)

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("users.id"), index=True)
    phase: Mapped[str] = mapped_column(String(40), nullable=False, default="onboarding", index=True)
    last_question: Mapped[str | None] = mapped_column(String(80))
    recent_messages: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False, default=list)
    conversation_summary: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class CoachMemoryEvent(Base):
    __tablename__ = "coach_memory_events"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("users.id"), index=True)
    event_type: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class CoachProposal(Base):
    __tablename__ = "coach_proposals"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("users.id"), index=True)
    type: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending", index=True)
    recommendation: Mapped[str] = mapped_column(Text, nullable=False)
    explanation: Mapped[str] = mapped_column(Text, nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class CoachPlannedSession(Base):
    __tablename__ = "coach_planned_sessions"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("users.id"), index=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="planned", index=True)
    title: Mapped[str] = mapped_column(String(120), nullable=False)
    session_payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    rationale: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
