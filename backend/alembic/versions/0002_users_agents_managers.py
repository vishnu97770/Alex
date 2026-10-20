"""users, agents, managers, agent payments, call links (additive; existing tables untouched)

Revision ID: 0002
Revises: 0001
"""

import sqlalchemy as sa

from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("uid", sa.Uuid(), nullable=False),
        sa.Column("username", sa.String(length=60), nullable=False),
        sa.Column("email", sa.String(length=254), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=True),
        sa.Column("google_sub", sa.String(length=64), nullable=True),
        sa.Column("avatar_path", sa.String(length=255), nullable=True),
        sa.Column("avatar_updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"]),
        sa.PrimaryKeyConstraint("uid"),
        sa.UniqueConstraint("google_sub"),
        sa.UniqueConstraint("workspace_id"),
    )
    op.create_index(op.f("ix_users_email"), "users", ["email"], unique=True)
    op.create_table(
        "agents",
        sa.Column("aid", sa.Uuid(), nullable=False),
        sa.Column("uid", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=80), nullable=False),
        sa.Column("role_behavior", sa.Text(), nullable=False),
        sa.Column("lifecycle", sa.String(length=10), nullable=False),
        sa.Column("profile_id", sa.Uuid(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["uid"], ["users.uid"]),
        sa.ForeignKeyConstraint(["profile_id"], ["agent_profiles.id"]),
        sa.PrimaryKeyConstraint("aid"),
    )
    op.create_index(op.f("ix_agents_uid"), "agents", ["uid"], unique=False)
    op.create_table(
        "managers",
        sa.Column("mid", sa.Uuid(), nullable=False),
        sa.Column("uid", sa.Uuid(), nullable=False),
        sa.Column("profile_id", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["uid"], ["users.uid"]),
        sa.ForeignKeyConstraint(["profile_id"], ["agent_profiles.id"]),
        sa.PrimaryKeyConstraint("mid"),
        sa.UniqueConstraint("uid"),
    )
    op.create_table(
        "agent_payments",
        sa.Column("aid", sa.Uuid(), nullable=False),
        sa.Column("uid", sa.Uuid(), nullable=False),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("status", sa.String(length=10), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["aid"], ["agents.aid"]),
        sa.ForeignKeyConstraint(["uid"], ["users.uid"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_agent_payments_aid"), "agent_payments", ["aid"], unique=False)
    op.create_index(op.f("ix_agent_payments_uid"), "agent_payments", ["uid"], unique=False)
    op.create_table(
        "call_links",
        sa.Column("call_id", sa.Uuid(), nullable=False),
        sa.Column("uid", sa.Uuid(), nullable=False),
        sa.Column("manager_mid", sa.Uuid(), nullable=True),
        sa.Column("agent_aid", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["call_id"], ["calls.id"]),
        sa.ForeignKeyConstraint(["uid"], ["users.uid"]),
        sa.ForeignKeyConstraint(["manager_mid"], ["managers.mid"]),
        sa.ForeignKeyConstraint(["agent_aid"], ["agents.aid"]),
        sa.PrimaryKeyConstraint("call_id"),
    )
    op.create_index(op.f("ix_call_links_uid"), "call_links", ["uid"], unique=False)
    op.create_index(op.f("ix_call_links_manager_mid"), "call_links", ["manager_mid"], unique=False)
    op.create_index(op.f("ix_call_links_agent_aid"), "call_links", ["agent_aid"], unique=False)


def downgrade() -> None:
    for t in ("call_links", "agent_payments", "managers", "agents", "users"):
        op.drop_table(t)
