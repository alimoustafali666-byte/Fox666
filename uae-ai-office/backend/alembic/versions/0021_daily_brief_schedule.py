"""add company daily brief schedule

Revision ID: 0021
Revises: 0020
Create Date: 2026-08-25
"""

import sqlalchemy as sa
from alembic import op

revision = "0021"
down_revision = "0020"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("companies", sa.Column("daily_brief_schedule_enabled", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("companies", sa.Column("daily_brief_schedule_time", sa.Time(), nullable=False, server_default="09:00:00"))
    op.add_column("companies", sa.Column("daily_brief_last_scheduled_date", sa.Date(), nullable=True))


def downgrade() -> None:
    op.drop_column("companies", "daily_brief_last_scheduled_date")
    op.drop_column("companies", "daily_brief_schedule_time")
    op.drop_column("companies", "daily_brief_schedule_enabled")