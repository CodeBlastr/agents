"""tax property details

Revision ID: 0003_tax_property_details
Revises: 0002_bot_configs
Create Date: 2026-02-14

"""

from alembic import op
import sqlalchemy as sa


revision = "0003_tax_property_details"
down_revision = "0002_bot_configs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "tax_property_details",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("run_id", sa.Integer(), nullable=False),
        sa.Column("bot_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("property_number", sa.String(length=255), nullable=True),
        sa.Column("tax_map", sa.String(length=255), nullable=True),
        sa.Column("property_address", sa.String(length=1024), nullable=False),
        sa.Column("total_due", sa.Numeric(12, 2), nullable=False),
        sa.Column("detail_json", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(["bot_id"], ["bots.id"]),
        sa.ForeignKeyConstraint(["run_id"], ["bot_runs.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_tax_property_details_id"), "tax_property_details", ["id"], unique=False)
    op.create_index(op.f("ix_tax_property_details_run_id"), "tax_property_details", ["run_id"], unique=False)
    op.create_index(op.f("ix_tax_property_details_bot_id"), "tax_property_details", ["bot_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_tax_property_details_bot_id"), table_name="tax_property_details")
    op.drop_index(op.f("ix_tax_property_details_run_id"), table_name="tax_property_details")
    op.drop_index(op.f("ix_tax_property_details_id"), table_name="tax_property_details")
    op.drop_table("tax_property_details")
