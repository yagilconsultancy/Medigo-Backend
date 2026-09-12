"""account_deletion_requests

Revision ID: 023
Revises: 022
Create Date: 2026-09-09 00:00:00.000000

Backs the public account-deletion flow at getmedigo.com/medigo-delete-account.

Google Play requires a publicly reachable URL where a user can request deletion
of their account without installing the app or signing in. Until now the only
deletion path was the authenticated DELETE /v1/users/me used by the in-app
Profile screen, which does not satisfy that requirement.

A row is created only once the submitted email matches a live account, so the
BackOffice review queue never fills with unactionable requests. Ownership is
proven with an emailed OTP (stored as an HMAC, never in plaintext); an admin
then approves or rejects, and approval runs the existing soft-delete.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID


# revision identifiers, used by Alembic.
revision: str = '023'
down_revision: Union[str, None] = '022'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'account_deletion_requests',
        sa.Column(
            'id',
            UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text('gen_random_uuid()'),
        ),
        sa.Column('full_name', sa.String(255), nullable=False),
        sa.Column('email', sa.String(255), nullable=False),
        sa.Column('phone', sa.String(20), nullable=True),
        sa.Column('reason', sa.Text(), nullable=True),
        sa.Column(
            'user_id',
            UUID(as_uuid=True),
            sa.ForeignKey('users.id'),
            nullable=False,
        ),
        sa.Column(
            'status',
            sa.String(30),
            nullable=False,
            server_default='pending_verification',
        ),
        sa.Column('otp_code_hash', sa.String(64), nullable=True),
        sa.Column('otp_expires_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('otp_attempts', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('otp_sent_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('otp_last_sent_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('email_verified_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            'reviewed_by',
            UUID(as_uuid=True),
            sa.ForeignKey('users.id'),
            nullable=True,
        ),
        sa.Column('reviewed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('rejection_reason', sa.Text(), nullable=True),
        sa.Column('admin_notes', sa.Text(), nullable=True),
        sa.Column(
            'source', sa.String(30), nullable=False, server_default='public_web'
        ),
        sa.Column('ip_address', sa.String(45), nullable=True),
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
    op.create_index(
        'ix_account_deletion_requests_email', 'account_deletion_requests', ['email']
    )
    op.create_index(
        'ix_account_deletion_requests_user_id',
        'account_deletion_requests',
        ['user_id'],
    )
    op.create_index(
        'ix_account_deletion_requests_status',
        'account_deletion_requests',
        ['status'],
    )


def downgrade() -> None:
    op.drop_index(
        'ix_account_deletion_requests_status', table_name='account_deletion_requests'
    )
    op.drop_index(
        'ix_account_deletion_requests_user_id', table_name='account_deletion_requests'
    )
    op.drop_index(
        'ix_account_deletion_requests_email', table_name='account_deletion_requests'
    )
    op.drop_table('account_deletion_requests')
