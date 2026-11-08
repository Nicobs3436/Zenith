"""email verification, consents, email tokens and session idempotency

Revision ID: 20261108_0013
Revises: 20260715_0012
Create Date: 2026-11-08

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261108_0013"
down_revision: str | None = "20260715_0012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("users", sa.Column("email_verified_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("users", sa.Column("terms_accepted_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("users", sa.Column("adult_confirmed_at", sa.DateTime(timezone=True), nullable=True))
    # Emails normalizados a minusculas (la app ya los compara sin distinguir mayusculas).
    op.execute("UPDATE users SET email = lower(email) WHERE email <> lower(email)")

    op.create_table(
        "email_tokens",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("purpose", sa.String(length=20), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_email_tokens_token_hash"), "email_tokens", ["token_hash"], unique=True)
    op.create_index(op.f("ix_email_tokens_user_id"), "email_tokens", ["user_id"], unique=False)

    op.add_column("workout_sessions", sa.Column("client_request_id", sa.Uuid(), nullable=True))
    op.create_unique_constraint(
        "uq_workout_sessions_user_client_request", "workout_sessions", ["user_id", "client_request_id"]
    )


def downgrade() -> None:
    op.drop_constraint("uq_workout_sessions_user_client_request", "workout_sessions", type_="unique")
    op.drop_column("workout_sessions", "client_request_id")
    op.drop_index(op.f("ix_email_tokens_user_id"), table_name="email_tokens")
    op.drop_index(op.f("ix_email_tokens_token_hash"), table_name="email_tokens")
    op.drop_table("email_tokens")
    op.drop_column("users", "adult_confirmed_at")
    op.drop_column("users", "terms_accepted_at")
    op.drop_column("users", "email_verified_at")
