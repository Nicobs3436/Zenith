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
CoachV2Goal = Literal["strength", "hypertrophy", "fat_loss", "general_health", "endurance"]
CoachV2Sex = Literal["male", "female"]
CoachV2Phase = Literal["onboarding", "plan_ready", "training_active", "progress_review", "fatigue_review", "adjustment_review"]
CoachProposalStatus = Literal["pending", "accepted", "rejected", "expired"]
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


class CoachV2MessageRequest(BaseModel):
    message: str = Field(min_length=1, max_length=1_200)
    personal_data_acknowledged: bool = False
    sensitive_data_acknowledged: bool = False

    @model_validator(mode="after")
    def normalize_message(self) -> "CoachV2MessageRequest":
        self.message = self.message.strip()
        return self


class CoachMessageRequest(BaseModel):
    message: str = Field(min_length=1, max_length=1_500)
    personal_data_acknowledged: bool = False
    sensitive_data_acknowledged: bool = False

    @model_validator(mode="after")
    def normalize_message(self) -> "CoachMessageRequest":
        self.message = self.message.strip()
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
    missing_required_fields: list[str]
    ready_for_plan: bool
    draft_plans: list[AiTrainingPlanRead]
    accepted_plan: AiTrainingPlanRead | None
    privacy_notice: str
    safety_notice: str
    next_action: str | None = None


class CoachV2ProfileRead(BaseModel):
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


class CoachV2MessageRead(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class CoachV2ConversationRead(BaseModel):
    id: UUID
    user_id: UUID
    phase: CoachV2Phase
    last_question: str | None
    recent_messages: list[CoachV2MessageRead]
    conversation_summary: str | None
    updated_at: datetime


class CoachMemoryEventRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    event_type: str
    summary: str
    payload: dict[str, Any]
    created_at: datetime


class CoachProposalRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    type: str
    status: CoachProposalStatus
    recommendation: str
    explanation: str
    payload: dict[str, Any]
    created_at: datetime
    reviewed_at: datetime | None


class CoachPlannedSessionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    status: str
    title: str
    session_payload: dict[str, Any]
    rationale: str
    created_at: datetime
    completed_at: datetime | None


class CoachV2StateRead(BaseModel):
    profile: CoachV2ProfileRead
    conversation: CoachV2ConversationRead
    assistant_message: str
    missing_required_fields: list[str]
    ready_for_plan: bool
    memory_events: list[CoachMemoryEventRead]
    proposals: list[CoachProposalRead]
    planned_sessions: list[CoachPlannedSessionRead]
    privacy_notice: str
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
