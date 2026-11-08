from datetime import datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.db.base import Base


class WorkoutSession(Base):
    __tablename__ = "workout_sessions"
    __table_args__ = (
        # Idempotencia: la app reintenta envios hechos sin conexion con el mismo id de cliente.
        UniqueConstraint("user_id", "client_request_id", name="uq_workout_sessions_user_client_request"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("users.id"), index=True)
    routine_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("routines.id"), index=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    timezone: Mapped[str] = mapped_column(String(80), nullable=False)
    client_request_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True))
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    sets: Mapped[list["WorkoutSet"]] = relationship(
        back_populates="session",
        cascade="all, delete-orphan",
        order_by="WorkoutSet.set_number",
    )


class WorkoutSet(Base):
    __tablename__ = "workout_sets"
    __table_args__ = (
        CheckConstraint("set_number >= 1", name="ck_workout_sets_number_positive"),
        CheckConstraint("reps >= 0", name="ck_workout_sets_reps_non_negative"),
        CheckConstraint(
            "weight_value IS NULL OR weight_value >= 0",
            name="ck_workout_sets_weight_non_negative",
        ),
        CheckConstraint("rpe IS NULL OR (rpe >= 1 AND rpe <= 10)", name="ck_workout_sets_rpe_range"),
        CheckConstraint("rir IS NULL OR rir >= 0", name="ck_workout_sets_rir_non_negative"),
        CheckConstraint(
            "rest_seconds IS NULL OR rest_seconds >= 0",
            name="ck_workout_sets_rest_non_negative",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    session_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("workout_sessions.id"), index=True)
    exercise_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("exercises.id"), index=True)
    set_number: Mapped[int] = mapped_column(Integer, nullable=False)
    reps: Mapped[int] = mapped_column(Integer, nullable=False)
    weight_value: Mapped[Decimal | None] = mapped_column(Numeric(8, 2))
    weight_unit: Mapped[str | None] = mapped_column(String(2))
    rpe: Mapped[Decimal | None] = mapped_column(Numeric(3, 1))
    rir: Mapped[int | None] = mapped_column(Integer)
    rest_seconds: Mapped[int | None] = mapped_column(Integer)
    notes: Mapped[str | None] = mapped_column(Text)

    session: Mapped[WorkoutSession] = relationship(back_populates="sets")
