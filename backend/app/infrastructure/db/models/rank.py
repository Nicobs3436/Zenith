from datetime import datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String, Text, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.db.base import Base


class Rank(Base):
    __tablename__ = "ranks"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    min_score: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, unique=True, nullable=False)


class UserRankProgress(Base):
    __tablename__ = "user_rank_progress"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("users.id"), index=True)
    rank_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("ranks.id"), index=True)
    score: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    volume_score: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    progression_score: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    breadth_score: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    calculated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
