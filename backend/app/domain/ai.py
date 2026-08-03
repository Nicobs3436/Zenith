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
AiCoachQuestionType = Literal["next_workout", "progression", "fatigue", "routine_review", "stats_explanation"]


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


class AiCoachQuestionRequest(BaseModel):
    question_type: AiCoachQuestionType
    routine_id: UUID | None = None
    exercise_id: UUID | None = None
    session_id: UUID | None = None
    detail: str | None = Field(default=None, max_length=500)

    @model_validator(mode="after")
    def validate_guided_question(self) -> "AiCoachQuestionRequest":
        if self.question_type == "routine_review" and self.routine_id is None:
            raise ValueError("routine_review requires routine_id")
        detail = self.detail.strip() if self.detail else None
        self.detail = detail or None
        return self


class AiCoachQuestionRead(BaseModel):
    question_type: AiCoachQuestionType
    answer: str
    key_points: list[str]
    related_metrics: dict[str, Any]
    suggested_actions: list[str]
    provider: str
    model: str | None
    fallback_used: bool
    input_summary: dict[str, Any]


TrainingPlanGoal = Literal["strength", "hypertrophy", "fat_loss", "general_health", "endurance"]
TrainingPlanLevel = Literal["beginner", "intermediate", "advanced"]
TrainingPlanStatus = Literal["draft", "accepted", "rejected"]
AiCoachIntakeStatus = Literal["collecting", "ready", "plan_generated"]


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


class AiCoachIntakeMessageRequest(BaseModel):
    message: str = Field(min_length=1, max_length=1_000)
    sensitive_data_acknowledged: bool = False

    @model_validator(mode="after")
    def normalize_message(self) -> "AiCoachIntakeMessageRequest":
        self.message = self.message.strip()
        return self


class AiCoachIntakeRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    status: AiCoachIntakeStatus
    intake_summary: dict[str, Any]
    recent_messages: list[dict[str, Any]]
    missing_required_fields: list[str]
    useful_missing_fields: list[str] = Field(default_factory=list)
    ready_for_plan: bool
    sensitive_data_acknowledged: bool
    assistant_message: str | None = None
    safety_warning: str | None = None
    provider: str = "internal"
    model: str | None = None
    fallback_used: bool = False
    updated_at: datetime


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
