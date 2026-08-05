from datetime import datetime
from typing import Any, Literal
import unicodedata
from uuid import UUID

from pydantic import BaseModel, ConfigDict
from pydantic import Field, model_validator

AiSuggestionType = Literal[
    "increase_weight",
    "reduce_volume",
    "change_reps",
    "increase_rest",
    "plateau_detected",
    "deload_recommended",
    "exercise_swap",
    "routine_goal_adjustment",
]
AiSuggestionStatus = Literal["pending", "accepted", "rejected", "expired"]


class AiSuggestionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    routine_id: UUID | None
    routine_exercise_id: UUID | None
    exercise_id: UUID | None
    type: AiSuggestionType
    status: AiSuggestionStatus
    input_summary: dict[str, Any]
    recommendation: str
    explanation: str
    risk_notes: str | None
    confidence: str | None
    apply_payload: dict[str, Any]
    created_at: datetime
    reviewed_at: datetime | None
    applied_at: datetime | None


TrainingPlanGoal = Literal["strength", "hypertrophy", "fat_loss", "general_health", "endurance"]
TrainingPlanLevel = Literal["beginner", "intermediate", "advanced"]
TrainingPlanStatus = Literal["draft", "accepted", "rejected"]
CoachPhase = Literal["onboarding", "ready_for_plan", "plan_draft", "training_active"]


class AiTrainingPlanGenerateRequest(BaseModel):
    goal: TrainingPlanGoal
    level: TrainingPlanLevel
    days_per_week: int = Field(ge=1, le=7)
    session_duration_minutes: int = Field(ge=20, le=180)
    available_equipment: list[str] = Field(default_factory=list, max_length=20)
    physical_limitations: str | None = Field(default=None, max_length=1_000)
    sensitive_data_acknowledged: bool = False
    priorities: list[str] = Field(default_factory=list, max_length=10)

    @model_validator(mode="after")
    def validate_sensitive_acknowledgement(self) -> "AiTrainingPlanGenerateRequest":
        if self.physical_limitations and self.physical_limitations.strip() and not self.sensitive_data_acknowledged:
            raise ValueError("Physical limitations require sensitive_data_acknowledged=true")
        return self


class AiTrainingPlanModifyRequest(BaseModel):
    instruction: str = Field(min_length=3, max_length=1_000)
    sensitive_data_acknowledged: bool = False

    @model_validator(mode="after")
    def validate_sensitive_instruction(self) -> "AiTrainingPlanModifyRequest":
        normalized = unicodedata.normalize("NFKD", self.instruction).encode("ascii", "ignore").decode().lower()
        sensitive_markers = ["dolor", "lesion", "molestia", "rodilla", "limitacion"]
        if any(marker in normalized for marker in sensitive_markers) and not self.sensitive_data_acknowledged:
            raise ValueError("Sensitive modification instructions require sensitive_data_acknowledged=true")
        return self


class AiTrainingPlanRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    status: TrainingPlanStatus
    goal: str
    level: str
    days_per_week: int
    session_duration_minutes: int
    available_equipment: list[str]
    physical_limitations: str | None
    sensitive_data_acknowledged: bool
    priorities: list[str]
    plan_payload: dict[str, Any]
    explanation: str
    risk_notes: str | None
    confidence: str | None
    input_summary: dict[str, Any]
    provider: str
    model: str | None
    fallback_used: bool
    created_at: datetime
    reviewed_at: datetime | None


class CoachMessageRequest(BaseModel):
    message: str = Field(min_length=1, max_length=1_500)
    personal_data_acknowledged: bool = False
    sensitive_data_acknowledged: bool = False

    @model_validator(mode="after")
    def normalize_message(self) -> "CoachMessageRequest":
        self.message = self.message.strip()
        return self


class CoachPlanDraftReviseRequest(BaseModel):
    instruction: str = Field(min_length=3, max_length=1_500)
    sensitive_data_acknowledged: bool = False

    @model_validator(mode="after")
    def normalize_instruction(self) -> "CoachPlanDraftReviseRequest":
        self.instruction = self.instruction.strip()
        return self


class CoachProfileRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    goal: str | None
    secondary_goal: str | None
    plan_horizon_weeks: int | None
    biological_sex: str | None
    age: int | None
    height_cm: int | None
    weight_kg: int | None
    experience_level: str | None
    training_age_months: int | None
    days_per_week: int | None
    session_duration_minutes: int | None
    equipment: list[str]
    priorities: list[str]
    preferred_exercises: list[str]
    avoided_exercises: list[str]
    physical_limitations: str | None
    sleep_quality: str | None
    stress_level: str | None
    current_fatigue: str | None
    personal_data_acknowledged: bool
    sensitive_data_acknowledged: bool
    memory_summary: str | None
    updated_at: datetime


class CoachMessageRead(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class CoachStateRead(BaseModel):
    profile: CoachProfileRead
    phase: CoachPhase
    recent_messages: list[CoachMessageRead]
    assistant_message: str
    known_facts: list[str]
    missing_critical: list[str]
    missing_useful: list[str]
    estimated_fields: list[str]
    misunderstanding_corrections: list[str] = Field(default_factory=list)
    safety_flags: list[str]
    ready_for_plan: bool
    draft_plans: list[AiTrainingPlanRead]
    accepted_plan: AiTrainingPlanRead | None
    privacy_notice: str
    safety_notice: str
    next_action: str | None = None


class AiSessionSummaryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    session_id: UUID
    summary: str
    improvements: list[str]
    drops: list[str]
    warnings: list[str]
    next_recommendation: str
    input_summary: dict[str, Any]
    provider: str
    model: str | None
    fallback_used: bool
    created_at: datetime
