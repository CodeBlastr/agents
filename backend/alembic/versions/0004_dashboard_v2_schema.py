"""dashboard v2 schema reset

Revision ID: 0004_dashboard_v2_schema
Revises: 0003_tax_property_details
Create Date: 2026-02-14

"""

from alembic import op
import sqlalchemy as sa


revision = "0004_dashboard_v2_schema"
down_revision = "0003_tax_property_details"
branch_labels = None
depends_on = None


def _create_schema() -> None:
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
        "bot_configs",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("bot_id", sa.Integer(), nullable=False),
        sa.Column("key", sa.String(length=255), nullable=False),
        sa.Column("config_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["bot_id"], ["bots.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("bot_id", "key", name="uq_bot_configs_bot_id_key"),
    )
    op.create_index(op.f("ix_bot_configs_bot_id"), "bot_configs", ["bot_id"], unique=False)

    op.create_table(
        "bot_runs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("bot_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_summary", sa.Text(), nullable=True),
        sa.Column("details_json", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(["bot_id"], ["bots.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_bot_runs_id"), "bot_runs", ["id"], unique=False)
    op.create_index(op.f("ix_bot_runs_bot_id"), "bot_runs", ["bot_id"], unique=False)
    op.create_index(op.f("ix_bot_runs_status"), "bot_runs", ["status"], unique=False)

    op.create_table(
        "tax_property_snapshots",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("run_id", sa.Integer(), nullable=False),
        sa.Column("bot_id", sa.Integer(), nullable=False),
        sa.Column("source_url", sa.String(length=1024), nullable=False),
        sa.Column("source_account_number", sa.String(length=64), nullable=True),
        sa.Column("final_url", sa.String(length=1024), nullable=False),
        sa.Column("property_address", sa.String(length=1024), nullable=False),
        sa.Column("total_due", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("tables_json", sa.JSON(), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("scraped_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["bot_id"], ["bots.id"]),
        sa.ForeignKeyConstraint(["run_id"], ["bot_runs.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_tax_property_snapshots_id"), "tax_property_snapshots", ["id"], unique=False)
    op.create_index(op.f("ix_tax_property_snapshots_run_id"), "tax_property_snapshots", ["run_id"], unique=False)
    op.create_index(op.f("ix_tax_property_snapshots_bot_id"), "tax_property_snapshots", ["bot_id"], unique=False)
    op.create_index(
        op.f("ix_tax_property_snapshots_source_account_number"),
        "tax_property_snapshots",
        ["source_account_number"],
        unique=False,
    )
    op.create_index(
        op.f("ix_tax_property_snapshots_property_address"),
        "tax_property_snapshots",
        ["property_address"],
        unique=False,
    )
    op.create_index(op.f("ix_tax_property_snapshots_scraped_at"), "tax_property_snapshots", ["scraped_at"], unique=False)


def upgrade() -> None:
    # Reset schema so existing environments from older revisions converge to v2.
    op.execute("DROP TABLE IF EXISTS tax_property_snapshots CASCADE")
    op.execute("DROP TABLE IF EXISTS tax_property_details CASCADE")
    op.execute("DROP TABLE IF EXISTS tax_snapshots CASCADE")
    op.execute("DROP TABLE IF EXISTS notifications CASCADE")
    op.execute("DROP TABLE IF EXISTS bot_configs CASCADE")
    op.execute("DROP TABLE IF EXISTS bot_runs CASCADE")
    op.execute("DROP TABLE IF EXISTS bots CASCADE")

    _create_schema()


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS tax_property_snapshots CASCADE")
    op.execute("DROP TABLE IF EXISTS bot_runs CASCADE")
    op.execute("DROP TABLE IF EXISTS bot_configs CASCADE")
    op.execute("DROP TABLE IF EXISTS bots CASCADE")
