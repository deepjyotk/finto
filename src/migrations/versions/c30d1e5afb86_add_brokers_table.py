"""add brokers table

Revision ID: c30d1e5afb86
Revises: 6ea001377ab4
Create Date: 2025-11-11 11:36:40.403758

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'c30d1e5afb86'
down_revision: Union[str, None] = '6ea001377ab4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create enum types if they don't exist
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE broker_name_enum AS ENUM ('AngelOne', 'Zerodha', 'Grow');
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
    """)
    
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE broker_type_enum AS ENUM ('Equity', 'Crypto');
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
    """)
    
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE country_enum AS ENUM ('India', 'US');
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
    """)
    
    # Create brokers table
    op.create_table(
        'brokers',
        sa.Column('broker_id', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('broker_name', postgresql.ENUM('AngelOne', 'Zerodha', 'Grow', name='broker_name_enum', create_type=False), nullable=False),
        sa.Column('broker_type', postgresql.ENUM('Equity', 'Crypto', name='broker_type_enum', create_type=False), nullable=False),
        sa.Column('country', postgresql.ENUM('India', 'US', name='country_enum', create_type=False), nullable=False),
        sa.PrimaryKeyConstraint('broker_id', name=op.f('pk_brokers'))
    )


def downgrade() -> None:
    # Drop table
    op.drop_table('brokers')
    
    # Drop enum types
    op.execute('DROP TYPE IF EXISTS broker_name_enum')
    op.execute('DROP TYPE IF EXISTS broker_type_enum')
    op.execute('DROP TYPE IF EXISTS country_enum')

