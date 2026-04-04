"""add in_equities table

Revision ID: a1b2c3d4e5f6
Revises: 64ae4f17dddd
Create Date: 2025-12-17 00:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, None] = "64ae4f17dddd"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "in_equities",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("symbol", sa.Text(), nullable=False),
        sa.Column("company_name", sa.Text(), nullable=False),
        sa.Column("series", sa.Text(), nullable=True),
        sa.Column("date_of_listing", sa.Date(), nullable=True),
        sa.Column("paid_up_value", sa.Numeric(precision=20, scale=4), nullable=True),
        sa.Column("market_lot", sa.Integer(), nullable=True),
        sa.Column("isin_number", sa.Text(), nullable=False),
        sa.Column("face_value", sa.Numeric(precision=20, scale=4), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_in_equities")),
        sa.UniqueConstraint("symbol", name=op.f("uq_in_equities_symbol")),
        sa.UniqueConstraint("isin_number", name=op.f("uq_in_equities_isin_number")),
    )
    op.create_index(op.f("ix_in_equities_symbol"), "in_equities", ["symbol"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_in_equities_symbol"), table_name="in_equities")
    op.drop_table("in_equities")
