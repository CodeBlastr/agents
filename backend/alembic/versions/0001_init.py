"""init

Revision ID: 0001_init
Revises:
Create Date: 2026-02-13

"""

from alembic import op
import sqlalchemy as sa


revision = "0001_init"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "bots",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("slug", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_bots_id"), "bots", ["id"], unique=False)
    op.create_index(op.f("ix_bots_slug"), "bots", ["slug"], unique=True)

    op.create_table(
        "bot_runs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("bot_id", sa.Integer(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("error", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["bot_id"], ["bots.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_bot_runs_id"), "bot_runs", ["id"], unique=False)
    op.create_index(op.f("ix_bot_runs_bot_id"), "bot_runs", ["bot_id"], unique=False)

    op.create_table(
        "tax_snapshots",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("bot_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("parcel_id", sa.String(length=255), nullable=False),
        sa.Column("portal_url", sa.String(length=1024), nullable=False),
        sa.Column("balance_due", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("paid_status", sa.String(length=64), nullable=False),
        sa.Column("due_date", sa.String(length=64), nullable=False),
        sa.Column("raw_json", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(["bot_id"], ["bots.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_tax_snapshots_id"), "tax_snapshots", ["id"], unique=False)
    op.create_index(op.f("ix_tax_snapshots_bot_id"), "tax_snapshots", ["bot_id"], unique=False)
    op.create_index(op.f("ix_tax_snapshots_parcel_id"), "tax_snapshots", ["parcel_id"], unique=False)
    op.create_index(op.f("ix_tax_snapshots_portal_url"), "tax_snapshots", ["portal_url"], unique=False)

    op.create_table(
        "notifications",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("bot_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("channel", sa.String(length=64), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["bot_id"], ["bots.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_notifications_id"), "notifications", ["id"], unique=False)
    op.create_index(op.f("ix_notifications_bot_id"), "notifications", ["bot_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_notifications_bot_id"), table_name="notifications")
    op.drop_index(op.f("ix_notifications_id"), table_name="notifications")
    op.drop_table("notifications")
    op.drop_index(op.f("ix_tax_snapshots_portal_url"), table_name="tax_snapshots")
    op.drop_index(op.f("ix_tax_snapshots_parcel_id"), table_name="tax_snapshots")
    op.drop_index(op.f("ix_tax_snapshots_bot_id"), table_name="tax_snapshots")
    op.drop_index(op.f("ix_tax_snapshots_id"), table_name="tax_snapshots")
    op.drop_table("tax_snapshots")
    op.drop_index(op.f("ix_bot_runs_bot_id"), table_name="bot_runs")
    op.drop_index(op.f("ix_bot_runs_id"), table_name="bot_runs")
    op.drop_table("bot_runs")
    op.drop_index(op.f("ix_bots_slug"), table_name="bots")
    op.drop_index(op.f("ix_bots_id"), table_name="bots")
    op.drop_table("bots")
