"""Add users, server-side sessions, and append-only security audit events.

Revision ID: 0008
Revises: 0007
Create Date: 2026-11-01
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0008"
down_revision: str | None = "0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("email", sa.String(length=254), nullable=False),
        sa.Column("display_name", sa.String(length=80), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("role", sa.String(length=16), server_default="USER", nullable=False),
        sa.Column("state", sa.String(length=16), server_default="ACTIVE", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "password_changed_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "email = lower(trim(email))", name="ck_users_email_normalized"
        ),
        sa.CheckConstraint("role in ('USER', 'ADMIN')", name="ck_users_role"),
        sa.CheckConstraint(
            "state in ('ACTIVE', 'DISABLED')", name="ck_users_state"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email", name="uq_users_email"),
    )
    op.create_index("ix_users_role_state", "users", ["role", "state"])

    op.create_table(
        "sessions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("token_verifier", sa.LargeBinary(length=32), nullable=False),
        sa.Column("csrf_verifier", sa.LargeBinary(length=32), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column("last_activity_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("idle_expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("absolute_expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revocation_reason", sa.String(length=64), nullable=True),
        sa.Column("rotation_predecessor_id", sa.Uuid(), nullable=True),
        sa.CheckConstraint(
            "last_activity_at >= created_at and last_activity_at <= absolute_expires_at",
            name="ck_sessions_activity_window",
        ),
        sa.CheckConstraint(
            "idle_expires_at <= absolute_expires_at",
            name="ck_sessions_expiration_order",
        ),
        sa.CheckConstraint(
            "(revoked_at is null and revocation_reason is null) or "
            "(revoked_at is not null and revocation_reason is not null)",
            name="ck_sessions_revocation_pair",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["rotation_predecessor_id"], ["sessions.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_verifier", name="uq_sessions_token_verifier"),
        sa.UniqueConstraint(
            "rotation_predecessor_id", name="uq_sessions_rotation_predecessor"
        ),
    )
    op.create_index(
        "ix_sessions_user_active",
        "sessions",
        ["user_id", "absolute_expires_at"],
        postgresql_where=sa.text("revoked_at is null"),
    )
    op.create_index(
        "ix_sessions_idle_expires_at", "sessions", ["idle_expires_at"]
    )

    op.create_table(
        "security_audit_events",
        sa.Column("id", sa.BigInteger(), sa.Identity(), nullable=False),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("outcome", sa.String(length=16), nullable=False),
        sa.Column("actor_user_id", sa.Uuid(), nullable=True),
        sa.Column("target_user_id", sa.Uuid(), nullable=True),
        sa.Column("session_id", sa.Uuid(), nullable=True),
        sa.Column("request_id", sa.Uuid(), nullable=False),
        sa.Column(
            "metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "outcome in ('SUCCESS', 'FAILURE', 'DENIED')",
            name="ck_security_audit_events_outcome",
        ),
        sa.ForeignKeyConstraint(
            ["actor_user_id"], ["users.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["target_user_id"], ["users.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_security_audit_events_created_at",
        "security_audit_events",
        ["created_at"],
    )
    op.create_index(
        "ix_security_audit_events_actor",
        "security_audit_events",
        ["actor_user_id", "created_at"],
    )
    op.create_index(
        "ix_security_audit_events_target",
        "security_audit_events",
        ["target_user_id", "created_at"],
    )
    op.create_index(
        "ix_security_audit_events_request_id",
        "security_audit_events",
        ["request_id"],
    )

    op.execute(
        """
        CREATE FUNCTION reject_security_audit_event_mutation()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        BEGIN
            RAISE EXCEPTION 'security_audit_events is append-only';
        END;
        $$
        """
    )
    op.execute(
        """
        CREATE TRIGGER security_audit_events_append_only
        BEFORE UPDATE OR DELETE ON security_audit_events
        FOR EACH ROW EXECUTE FUNCTION reject_security_audit_event_mutation()
        """
    )


def downgrade() -> None:
    op.execute(
        "DROP TRIGGER IF EXISTS security_audit_events_append_only "
        "ON security_audit_events"
    )
    op.execute("DROP FUNCTION IF EXISTS reject_security_audit_event_mutation()")
    op.drop_index(
        "ix_security_audit_events_request_id",
        table_name="security_audit_events",
    )
    op.drop_index(
        "ix_security_audit_events_target", table_name="security_audit_events"
    )
    op.drop_index(
        "ix_security_audit_events_actor", table_name="security_audit_events"
    )
    op.drop_index(
        "ix_security_audit_events_created_at", table_name="security_audit_events"
    )
    op.drop_table("security_audit_events")
    op.drop_index("ix_sessions_idle_expires_at", table_name="sessions")
    op.drop_index("ix_sessions_user_active", table_name="sessions")
    op.drop_table("sessions")
    op.drop_index("ix_users_role_state", table_name="users")
    op.drop_table("users")
