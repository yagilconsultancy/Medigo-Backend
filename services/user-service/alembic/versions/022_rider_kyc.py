"""rider_kyc

Revision ID: 022
Revises: 021
Create Date: 2026-07-30 00:00:00.000000

Adds identity verification for riders.

Riders previously had no KYC concept at all: no ID document details, no
verification state, and only a single free-text home_address line while drivers
already carried structured city/province/postal fields. This adds the rider_kyc
table plus the structured address and expanded insurance columns on users.

Existing riders get kyc_status 'not_started' implicitly — they simply have no
rider_kyc row until one is created.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID


# revision identifiers, used by Alembic.
revision: str = '022'
down_revision: Union[str, None] = '021'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'rider_kyc',
        sa.Column(
            'user_id',
            UUID(as_uuid=True),
            sa.ForeignKey('users.id'),
            primary_key=True,
        ),
        sa.Column('id_type', sa.String(40), nullable=True),
        sa.Column('id_number', sa.String(100), nullable=True),
        sa.Column('id_issuing_country', sa.String(100), nullable=True),
        sa.Column('id_issuing_authority', sa.String(255), nullable=True),
        sa.Column('id_expiry', sa.Date(), nullable=True),
        sa.Column(
            'kyc_status',
            sa.String(20),
            nullable=False,
            server_default='not_started',
        ),
        sa.Column('submitted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('verified_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('verified_by', UUID(as_uuid=True), nullable=True),
        sa.Column('rejection_reason', sa.Text(), nullable=True),
        sa.Column(
            'dob_verified',
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
        sa.Column(
            'created_at',
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
        sa.Column(
            'updated_at',
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
    )
    op.create_index('ix_rider_kyc_kyc_status', 'rider_kyc', ['kyc_status'])

    # Structured address for riders (drivers already have these on their profile).
    op.add_column('users', sa.Column('city', sa.String(100), nullable=True))
    op.add_column('users', sa.Column('province', sa.String(50), nullable=True))
    op.add_column('users', sa.Column('postal_code', sa.String(20), nullable=True))
    op.add_column('users', sa.Column('country', sa.String(100), nullable=True))

    # Expanded insurance details.
    op.add_column(
        'users', sa.Column('insurance_group_number', sa.String(100), nullable=True)
    )
    op.add_column(
        'users', sa.Column('insurance_member_id', sa.String(100), nullable=True)
    )
    op.add_column('users', sa.Column('insurance_expiry', sa.Date(), nullable=True))


def downgrade() -> None:
    op.drop_column('users', 'insurance_expiry')
    op.drop_column('users', 'insurance_member_id')
    op.drop_column('users', 'insurance_group_number')
    op.drop_column('users', 'country')
    op.drop_column('users', 'postal_code')
    op.drop_column('users', 'province')
    op.drop_column('users', 'city')
    op.drop_index('ix_rider_kyc_kyc_status', table_name='rider_kyc')
    op.drop_table('rider_kyc')
