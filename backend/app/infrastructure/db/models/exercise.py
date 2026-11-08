from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, String, Table, Text, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.db.base import Base

exercise_muscle_groups = Table(
    "exercise_muscle_groups",
    Base.metadata,
    Column("exercise_id", Uuid(as_uuid=True), ForeignKey("exercises.id"), primary_key=True),
    Column("muscle_group_id", Uuid(as_uuid=True), ForeignKey("muscle_groups.id"), primary_key=True),
)

exercise_equipment = Table(
    "exercise_equipment",
    Base.metadata,
    Column("exercise_id", Uuid(as_uuid=True), ForeignKey("exercises.id"), primary_key=True),
    Column("equipment_id", Uuid(as_uuid=True), ForeignKey("equipment.id"), primary_key=True),
)


class MuscleGroup(Base):
    __tablename__ = "muscle_groups"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(80), unique=True, index=True, nullable=False)

    exercises: Mapped[list["Exercise"]] = relationship(
        secondary=exercise_muscle_groups,
        back_populates="muscle_groups",
    )


class Equipment(Base):
    __tablename__ = "equipment"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(80), unique=True, index=True, nullable=False)

    exercises: Mapped[list["Exercise"]] = relationship(
        secondary=exercise_equipment,
        back_populates="equipment",
    )


class Exercise(Base):
    __tablename__ = "exercises"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text)
    difficulty: Mapped[str | None] = mapped_column(String(30))
    technique_notes: Mapped[str | None] = mapped_column(Text)
    is_global: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    created_by_user_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id"),
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    muscle_groups: Mapped[list[MuscleGroup]] = relationship(
        secondary=exercise_muscle_groups,
        back_populates="exercises",
    )
    equipment: Mapped[list[Equipment]] = relationship(
        secondary=exercise_equipment,
        back_populates="exercises",
    )
