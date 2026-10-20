"""screen_time_daily: per-user, per-day foreground seconds (additive; existing tables untouched)

Revision ID: 0003
Revises: 0002
"""

import sqlalchemy as sa

from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "screen_time_daily",
        sa.Column("uid", sa.Uuid(), nullable=False),
        sa.Column("day", sa.Date(), nullable=False),
        sa.Column("seconds", sa.Integer(), nullable=False),
        sa.Column("last_beat_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["uid"], ["users.uid"]),
        sa.PrimaryKeyConstraint("uid", "day"),
    )


def downgrade() -> None:
    op.drop_table("screen_time_daily")
