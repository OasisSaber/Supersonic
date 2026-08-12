"""Create the platform persistence foundation.

Revision ID: 20260809_0001
Revises:
Create Date: 2026-08-09

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260809_0001"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("username_norm", sa.String(length=128), nullable=False),
        sa.Column("display_name", sa.String(length=128), nullable=False),
        sa.Column("password_hash", sa.Text(), nullable=False),
        sa.Column("role", sa.String(length=16), nullable=False),
        sa.Column("disabled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "char_length(username_norm) BETWEEN 1 AND 128",
            name=op.f("ck_users_username_norm_length"),
        ),
        sa.CheckConstraint(
            "char_length(display_name) BETWEEN 1 AND 128",
            name=op.f("ck_users_display_name_length"),
        ),
        sa.CheckConstraint(
            "role IN ('admin', 'operator', 'viewer')",
            name=op.f("ck_users_role_allowed"),
        ),
        sa.PrimaryKeyConstraint("id", name="pk_users"),
        sa.UniqueConstraint("username_norm", name="uq_users_username_norm"),
    )

    op.create_table(
        "platform_sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("token_digest", sa.CHAR(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoke_reason", sa.String(length=128), nullable=True),
        sa.CheckConstraint(
            "token_digest ~ '^[0-9a-f]{64}$'",
            name=op.f("ck_platform_sessions_token_digest_format"),
        ),
        sa.CheckConstraint(
            "expires_at > created_at",
            name=op.f("ck_platform_sessions_expires_after_created"),
        ),
        sa.CheckConstraint(
            "revoke_reason IS NULL OR char_length(revoke_reason) <= 128",
            name=op.f("ck_platform_sessions_revoke_reason_length"),
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name="fk_platform_sessions_user_id_users",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_platform_sessions"),
        sa.UniqueConstraint(
            "token_digest",
            name="uq_platform_sessions_token_digest",
        ),
    )

    op.create_table(
        "audit_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("action", sa.String(length=128), nullable=False),
        sa.Column("result", sa.String(length=16), nullable=False),
        sa.Column("delivery", sa.String(length=16), nullable=False),
        sa.Column("actor_role", sa.String(length=16), nullable=True),
        sa.Column("actor_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "actor_platform_session_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
        sa.Column("endpoint", sa.String(length=32), nullable=True),
        sa.Column("source_type", sa.String(length=32), nullable=False),
        sa.Column("cockpit_session_id", sa.String(length=80), nullable=True),
        sa.Column("command_name", sa.String(length=64), nullable=True),
        sa.Column("error_code", sa.String(length=64), nullable=True),
        sa.Column("target_type", sa.String(length=64), nullable=True),
        sa.Column("correlation_id", sa.String(length=64), nullable=True),
        sa.Column("target_id", sa.String(length=128), nullable=True),
        sa.Column("parameters", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.CheckConstraint(
            "result IN ('attempted', 'succeeded', 'rejected', 'error')",
            name=op.f("ck_audit_events_result_allowed"),
        ),
        sa.CheckConstraint(
            "delivery IN ('primary', 'fallback')",
            name=op.f("ck_audit_events_delivery_allowed"),
        ),
        sa.CheckConstraint(
            "actor_role IS NULL OR actor_role IN ('admin', 'operator', 'viewer')",
            name=op.f("ck_audit_events_actor_role_allowed"),
        ),
        sa.CheckConstraint(
            "char_length(source_type) >= 1",
            name=op.f("ck_audit_events_source_type_nonempty"),
        ),
        sa.ForeignKeyConstraint(
            ["actor_user_id"],
            ["users.id"],
            name="fk_audit_events_actor_user_id_users",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_audit_events"),
    )
    op.create_index(
        "ix_audit_events_occurred_at_id_desc",
        "audit_events",
        [sa.text("occurred_at DESC"), sa.text("id DESC")],
        unique=False,
    )


def downgrade() -> None:
    op.drop_table("audit_events")
    op.drop_table("platform_sessions")
    op.drop_table("users")
