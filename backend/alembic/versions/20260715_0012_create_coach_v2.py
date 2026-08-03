"""create coach v2

Revision ID: 20260715_0012
Revises: 20260713_0011
Create Date: 2026-07-15

"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "20260715_0012"
down_revision: str | None = "20260713_0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "coach_profiles",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("goal", sa.String(length=40), nullable=True),
        sa.Column("secondary_goal", sa.String(length=40), nullable=True),
        sa.Column("plan_horizon_weeks", sa.Integer(), nullable=True),
        sa.Column("biological_sex", sa.String(length=10), nullable=True),
        sa.Column("age", sa.Integer(), nullable=True),
        sa.Column("height_cm", sa.Integer(), nullable=True),
        sa.Column("weight_kg", sa.Integer(), nullable=True),
        sa.Column("experience_level", sa.String(length=40), nullable=True),
        sa.Column("training_age_months", sa.Integer(), nullable=True),
        sa.Column("days_per_week", sa.Integer(), nullable=True),
        sa.Column("session_duration_minutes", sa.Integer(), nullable=True),
        sa.Column("equipment", sa.JSON(), nullable=False),
        sa.Column("priorities", sa.JSON(), nullable=False),
        sa.Column("preferred_exercises", sa.JSON(), nullable=False),
        sa.Column("avoided_exercises", sa.JSON(), nullable=False),
        sa.Column("physical_limitations", sa.Text(), nullable=True),
        sa.Column("sleep_quality", sa.String(length=20), nullable=True),
        sa.Column("stress_level", sa.String(length=20), nullable=True),
        sa.Column("current_fatigue", sa.String(length=20), nullable=True),
        sa.Column("personal_data_acknowledged", sa.Boolean(), nullable=False),
        sa.Column("sensitive_data_acknowledged", sa.Boolean(), nullable=False),
        sa.Column("memory_summary", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", name="uq_coach_profiles_user_id"),
    )
    op.create_index(op.f("ix_coach_profiles_user_id"), "coach_profiles", ["user_id"], unique=False)
    op.create_table(
        "coach_conversations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("phase", sa.String(length=40), nullable=False),
        sa.Column("last_question", sa.String(length=80), nullable=True),
        sa.Column("recent_messages", sa.JSON(), nullable=False),
        sa.Column("conversation_summary", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", name="uq_coach_conversations_user_id"),
    )
    op.create_index(op.f("ix_coach_conversations_phase"), "coach_conversations", ["phase"], unique=False)
    op.create_index(op.f("ix_coach_conversations_user_id"), "coach_conversations", ["user_id"], unique=False)
    op.create_table(
        "coach_memory_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("event_type", sa.String(length=40), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_coach_memory_events_event_type"), "coach_memory_events", ["event_type"], unique=False)
    op.create_index(op.f("ix_coach_memory_events_user_id"), "coach_memory_events", ["user_id"], unique=False)
    op.create_table(
        "coach_proposals",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("type", sa.String(length=40), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("recommendation", sa.Text(), nullable=False),
        sa.Column("explanation", sa.Text(), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_coach_proposals_status"), "coach_proposals", ["status"], unique=False)
    op.create_index(op.f("ix_coach_proposals_type"), "coach_proposals", ["type"], unique=False)
    op.create_index(op.f("ix_coach_proposals_user_id"), "coach_proposals", ["user_id"], unique=False)
    op.create_table(
        "coach_planned_sessions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("title", sa.String(length=120), nullable=False),
        sa.Column("session_payload", sa.JSON(), nullable=False),
        sa.Column("rationale", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_coach_planned_sessions_status"), "coach_planned_sessions", ["status"], unique=False)
    op.create_index(op.f("ix_coach_planned_sessions_user_id"), "coach_planned_sessions", ["user_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_coach_planned_sessions_user_id"), table_name="coach_planned_sessions")
    op.drop_index(op.f("ix_coach_planned_sessions_status"), table_name="coach_planned_sessions")
    op.drop_table("coach_planned_sessions")
    op.drop_index(op.f("ix_coach_proposals_user_id"), table_name="coach_proposals")
    op.drop_index(op.f("ix_coach_proposals_type"), table_name="coach_proposals")
    op.drop_index(op.f("ix_coach_proposals_status"), table_name="coach_proposals")
    op.drop_table("coach_proposals")
    op.drop_index(op.f("ix_coach_memory_events_user_id"), table_name="coach_memory_events")
    op.drop_index(op.f("ix_coach_memory_events_event_type"), table_name="coach_memory_events")
    op.drop_table("coach_memory_events")
    op.drop_index(op.f("ix_coach_conversations_user_id"), table_name="coach_conversations")
    op.drop_index(op.f("ix_coach_conversations_phase"), table_name="coach_conversations")
    op.drop_table("coach_conversations")
    op.drop_index(op.f("ix_coach_profiles_user_id"), table_name="coach_profiles")
    op.drop_table("coach_profiles")
