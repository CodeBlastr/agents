"""bot configs

Revision ID: 0002_bot_configs
Revises: 0001_init
Create Date: 2026-02-14

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0002_bot_configs"
down_revision = "0001_init"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "bot_configs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("bot_id", sa.Integer(), nullable=False),
        sa.Column("key", sa.String(length=255), nullable=False),
        sa.Column("config_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["bot_id"], ["bots.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("bot_id", "key", name="uq_bot_configs_bot_id_key"),
    )
    op.create_index(op.f("ix_bot_configs_bot_id"), "bot_configs", ["bot_id"], unique=False)

    op.alter_column("tax_snapshots", "paid_status", existing_type=sa.String(length=64), nullable=True)
    op.alter_column("tax_snapshots", "due_date", existing_type=sa.String(length=64), nullable=True)


def downgrade() -> None:
    op.alter_column("tax_snapshots", "due_date", existing_type=sa.String(length=64), nullable=False)
    op.alter_column("tax_snapshots", "paid_status", existing_type=sa.String(length=64), nullable=False)

    op.drop_index(op.f("ix_bot_configs_bot_id"), table_name="bot_configs")
    op.drop_table("bot_configs")
