"""add equity_holdings_in_metadata table and refactor equity_holdings_in

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2025-12-19 12:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "c3d4e5f6a7b8"
down_revision: Union[str, None] = "b2c3d4e5f6a7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create the enum type for uploaded_via
    uploaded_via_enum = postgresql.ENUM(
        "user_file_upload", "cron_job", name="uploaded_via_enum", create_type=False
    )
    uploaded_via_enum.create(op.get_bind(), checkfirst=True)

    # 2. Create the equity_holdings_in_metadata table
    op.create_table(
        "equity_holdings_in_metadata",
        sa.Column(
            "user_broker_id",
            sa.UUID(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("broker_id", sa.UUID(), nullable=False),
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
        sa.Column(
            "uploaded_via",
            uploaded_via_enum,
            nullable=False,
        ),
        sa.Column(
            "extra_metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=True
        ),
        sa.ForeignKeyConstraint(["user_id"], ["f_users.user_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["broker_id"], ["brokers.broker_id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("user_broker_id"),
    )

    # 3. Migrate existing user_id/broker_id combinations from equity_holdings_in to metadata table
    # This creates a metadata record for each unique user_id/broker_id pair
    op.execute(
        """
        INSERT INTO equity_holdings_in_metadata (user_broker_id, user_id, broker_id, uploaded_via)
        SELECT gen_random_uuid(), user_id, broker_id, 'user_file_upload'
        FROM equity_holdings_in
        GROUP BY user_id, broker_id
        """
    )

    # 4. Add user_broker_id column to equity_holdings_in (nullable initially for migration)
    op.add_column(
        "equity_holdings_in",
        sa.Column("user_broker_id", sa.UUID(), nullable=True),
    )

    # 5. Update user_broker_id values in equity_holdings_in to reference correct metadata records
    op.execute(
        """
        UPDATE equity_holdings_in eh
        SET user_broker_id = m.user_broker_id
        FROM equity_holdings_in_metadata m
        WHERE eh.user_id = m.user_id AND eh.broker_id = m.broker_id
        """
    )

    # 6. Make user_broker_id NOT NULL after data migration
    op.alter_column("equity_holdings_in", "user_broker_id", nullable=False)

    # 7. Add foreign key constraint
    op.create_foreign_key(
        "fk_equity_holdings_in_metadata",
        "equity_holdings_in",
        "equity_holdings_in_metadata",
        ["user_broker_id"],
        ["user_broker_id"],
        ondelete="CASCADE",
    )

    # 8. Drop the old foreign key constraints on user_id and broker_id
    op.drop_constraint(
        "equity_holdings_in_user_id_fkey", "equity_holdings_in", type_="foreignkey"
    )
    op.drop_constraint(
        "equity_holdings_in_broker_id_fkey", "equity_holdings_in", type_="foreignkey"
    )

    # 9. Drop user_id and broker_id columns from equity_holdings_in
    op.drop_column("equity_holdings_in", "user_id")
    op.drop_column("equity_holdings_in", "broker_id")


def downgrade() -> None:
    # 1. Add back user_id and broker_id columns (nullable for migration)
    op.add_column(
        "equity_holdings_in",
        sa.Column("user_id", sa.UUID(), nullable=True),
    )
    op.add_column(
        "equity_holdings_in",
        sa.Column("broker_id", sa.UUID(), nullable=True),
    )

    # 2. Restore user_id and broker_id values from metadata table
    op.execute(
        """
        UPDATE equity_holdings_in eh
        SET user_id = m.user_id, broker_id = m.broker_id
        FROM equity_holdings_in_metadata m
        WHERE eh.user_broker_id = m.user_broker_id
        """
    )

    # 3. Make columns NOT NULL
    op.alter_column("equity_holdings_in", "user_id", nullable=False)
    op.alter_column("equity_holdings_in", "broker_id", nullable=False)

    # 4. Add back foreign key constraints
    op.create_foreign_key(
        "equity_holdings_in_user_id_fkey",
        "equity_holdings_in",
        "f_users",
        ["user_id"],
        ["user_id"],
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        "equity_holdings_in_broker_id_fkey",
        "equity_holdings_in",
        "brokers",
        ["broker_id"],
        ["broker_id"],
        ondelete="CASCADE",
    )

    # 5. Drop the new foreign key constraint
    op.drop_constraint(
        "fk_equity_holdings_in_metadata", "equity_holdings_in", type_="foreignkey"
    )

    # 6. Drop user_broker_id column
    op.drop_column("equity_holdings_in", "user_broker_id")

    # 7. Drop the metadata table
    op.drop_table("equity_holdings_in_metadata")

    # 8. Drop the enum type
    op.execute("DROP TYPE IF EXISTS uploaded_via_enum")
