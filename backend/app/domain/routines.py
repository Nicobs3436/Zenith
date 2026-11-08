from datetime import datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, field_validator, model_validator

WeightUnit = Literal["kg", "lb"]

# Topes realistas: evitan errores 500 por desbordar Numeric(8,2) y datos absurdos que inflan stats/rango.
MAX_WEIGHT = Decimal("2500")  # cubre kg y lb (records de prensa en lb)
MAX_REPS = 1_000
MAX_SETS_PER_SESSION = 300
MAX_EXERCISES_PER_ROUTINE = 50
MAX_TARGET_SETS = 20
MAX_RIR = 20
MAX_REST_SECONDS = 3_600


class RoutineExerciseCreate(BaseModel):
    exercise_id: UUID
    position: int = Field(ge=1, le=MAX_EXERCISES_PER_ROUTINE)
    target_sets: int | None = Field(default=None, ge=1, le=MAX_TARGET_SETS)
    target_reps_min: int | None = Field(default=None, ge=0, le=MAX_REPS)
    target_reps_max: int | None = Field(default=None, ge=0, le=MAX_REPS)
    target_weight_value: Decimal | None = Field(default=None, ge=0, le=MAX_WEIGHT, decimal_places=2)
    target_weight_unit: WeightUnit | None = None
    target_rpe: Decimal | None = Field(default=None, ge=1, le=10, decimal_places=1)
    target_rir: int | None = Field(default=None, ge=0, le=MAX_RIR)
    rest_seconds: int | None = Field(default=None, ge=0, le=MAX_REST_SECONDS)
    notes: str | None = Field(default=None, max_length=2_000)

    @model_validator(mode="after")
    def validate_rep_range(self) -> "RoutineExerciseCreate":
        if (
            self.target_reps_min is not None
            and self.target_reps_max is not None
            and self.target_reps_max < self.target_reps_min
        ):
            raise ValueError("target_reps_max must be greater than or equal to target_reps_min")
        if (self.target_weight_value is None) != (self.target_weight_unit is None):
            raise ValueError("target_weight_value and target_weight_unit must be provided together")
        return self


class RoutineCreate(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    description: str | None = Field(default=None, max_length=2_000)
    goal: str | None = Field(default=None, max_length=120)
    exercises: list[RoutineExerciseCreate] = Field(min_length=1, max_length=MAX_EXERCISES_PER_ROUTINE)


class RoutineExerciseRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    exercise_id: UUID
    position: int
    target_sets: int | None
    target_reps_min: int | None
    target_reps_max: int | None
    target_weight_value: Decimal | None
    target_weight_unit: str | None
    target_rpe: Decimal | None
    target_rir: int | None
    rest_seconds: int | None
    notes: str | None


class RoutineRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    name: str
    description: str | None
    goal: str | None
    exercises: list[RoutineExerciseRead]
    created_at: datetime
    updated_at: datetime


class WorkoutSetCreate(BaseModel):
    exercise_id: UUID
    set_number: int = Field(ge=1, le=MAX_SETS_PER_SESSION)
    reps: int = Field(ge=0, le=MAX_REPS)
    weight_value: Decimal | None = Field(default=None, ge=0, le=MAX_WEIGHT, decimal_places=2)
    weight_unit: WeightUnit | None = None
    rpe: Decimal | None = Field(default=None, ge=1, le=10, decimal_places=1)
    rir: int | None = Field(default=None, ge=0, le=MAX_RIR)
    rest_seconds: int | None = Field(default=None, ge=0, le=MAX_REST_SECONDS)
    notes: str | None = Field(default=None, max_length=2_000)

    @model_validator(mode="after")
    def validate_weight_unit(self) -> "WorkoutSetCreate":
        if (self.weight_value is None) != (self.weight_unit is None):
            raise ValueError("weight_value and weight_unit must be provided together")
        return self


class WorkoutSessionCreate(BaseModel):
    routine_id: UUID | None = None
    # Fechas con zona obligatoria: sin offset no se puede saber el instante real (no asumir UTC en silencio).
    started_at: AwareDatetime
    finished_at: AwareDatetime | None = None
    timezone: str = Field(min_length=1, max_length=80)
    notes: str | None = Field(default=None, max_length=2_000)
    sets: list[WorkoutSetCreate] = Field(default_factory=list, max_length=MAX_SETS_PER_SESSION)

    @field_validator("timezone")
    @classmethod
    def validate_timezone(cls, value: str) -> str:
        value = value.strip()
        try:
            ZoneInfo(value)
        except (ZoneInfoNotFoundError, ValueError) as error:
            raise ValueError("timezone must be a valid IANA time zone, e.g. Europe/Madrid") from error
        return value

    @model_validator(mode="after")
    def validate_finished_at(self) -> "WorkoutSessionCreate":
        if self.finished_at is not None and self.finished_at < self.started_at:
            raise ValueError("finished_at must be greater than or equal to started_at")
        return self


class WorkoutSetRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    exercise_id: UUID
    set_number: int
    reps: int
    weight_value: Decimal | None
    weight_unit: str | None
    rpe: Decimal | None
    rir: int | None
    rest_seconds: int | None
    notes: str | None


class WorkoutSessionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    routine_id: UUID | None
    started_at: datetime
    finished_at: datetime | None
    timezone: str
    notes: str | None
    sets: list[WorkoutSetRead]
    created_at: datetime
