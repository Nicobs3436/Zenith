from datetime import datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, Numeric, String, Text, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.db.base import Base


class Routine(Base):
    __tablename__ = "routines"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("users.id"), index=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    goal: Mapped[str | None] = mapped_column(String(120))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    exercises: Mapped[list["RoutineExercise"]] = relationship(
        back_populates="routine",
        cascade="all, delete-orphan",
        order_by="RoutineExercise.position",
    )


class RoutineExercise(Base):
    __tablename__ = "routine_exercises"
    __table_args__ = (
        CheckConstraint("position >= 1", name="ck_routine_exercises_position_positive"),
        CheckConstraint("target_sets IS NULL OR target_sets >= 1", name="ck_routine_exercises_sets_positive"),
        CheckConstraint(
            "target_reps_min IS NULL OR target_reps_min >= 0",
            name="ck_routine_exercises_reps_min_non_negative",
        ),
        CheckConstraint(
            "target_reps_max IS NULL OR target_reps_max >= 0",
            name="ck_routine_exercises_reps_max_non_negative",
        ),
        CheckConstraint(
            "target_weight_value IS NULL OR target_weight_value >= 0",
            name="ck_routine_exercises_weight_non_negative",
        ),
        CheckConstraint(
            "target_rpe IS NULL OR (target_rpe >= 1 AND target_rpe <= 10)",
            name="ck_routine_exercises_rpe_range",
        ),
        CheckConstraint(
            "target_rir IS NULL OR target_rir >= 0",
            name="ck_routine_exercises_rir_non_negative",
        ),
        CheckConstraint(
            "rest_seconds IS NULL OR rest_seconds >= 0",
            name="ck_routine_exercises_rest_non_negative",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    routine_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("routines.id"), index=True)
    exercise_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("exercises.id"), index=True)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    target_sets: Mapped[int | None] = mapped_column(Integer)
    target_reps_min: Mapped[int | None] = mapped_column(Integer)
    target_reps_max: Mapped[int | None] = mapped_column(Integer)
    target_weight_value: Mapped[Decimal | None] = mapped_column(Numeric(8, 2))
    target_weight_unit: Mapped[str | None] = mapped_column(String(2))
    target_rpe: Mapped[Decimal | None] = mapped_column(Numeric(3, 1))
    target_rir: Mapped[int | None] = mapped_column(Integer)
    rest_seconds: Mapped[int | None] = mapped_column(Integer)
    notes: Mapped[str | None] = mapped_column(Text)

    routine: Mapped[Routine] = relationship(back_populates="exercises")
