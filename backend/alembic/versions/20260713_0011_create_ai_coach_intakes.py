"""create ai coach intakes

Revision ID: 20260713_0011
Revises: 20260708_0010
Create Date: 2026-07-13

"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "20260713_0011"
down_revision: str | None = "20260708_0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "ai_coach_intakes",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("intake_summary", sa.JSON(), nullable=False),
        sa.Column("recent_messages", sa.JSON(), nullable=False),
        sa.Column("missing_required_fields", sa.JSON(), nullable=False),
        sa.Column("ready_for_plan", sa.Boolean(), nullable=False),
        sa.Column("sensitive_data_acknowledged", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", name="uq_ai_coach_intakes_user_id"),
    )
    op.create_index(op.f("ix_ai_coach_intakes_status"), "ai_coach_intakes", ["status"], unique=False)
    op.create_index(op.f("ix_ai_coach_intakes_user_id"), "ai_coach_intakes", ["user_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_ai_coach_intakes_user_id"), table_name="ai_coach_intakes")
    op.drop_index(op.f("ix_ai_coach_intakes_status"), table_name="ai_coach_intakes")
    op.drop_table("ai_coach_intakes")
