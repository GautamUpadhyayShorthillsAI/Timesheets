"""Add is_approved to timesheet_entries

Revision ID: 38a95199638b
Revises: 244a10c91344
Create Date: 2025-05-03 14:22:31.473292
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "38a95199638b"
down_revision = "244a10c91344"
branch_labels = None
depends_on = None


def upgrade():
    # Only add the column if it doesn't already exist
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    cols = [c["name"] for c in inspector.get_columns("timesheet_entries")]
    if "is_approved" not in cols:
        op.add_column(
            "timesheet_entries",
            sa.Column(
                "is_approved",
                sa.Boolean(),
                nullable=False,
                server_default=sa.text("0"),
            ),
        )
        # we leave the server_default in place; SQLite won't let us drop it later


def downgrade():
    # Only drop the column if it exists
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    cols = [c["name"] for c in inspector.get_columns("timesheet_entries")]
    if "is_approved" in cols:
        op.drop_column("timesheet_entries", "is_approved")
