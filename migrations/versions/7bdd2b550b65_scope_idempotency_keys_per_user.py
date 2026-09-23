"""scope idempotency keys per user

Revision ID: 7bdd2b550b65
Revises: 0045bb75cb4a
Create Date: 2026-09-23 11:48:00.420058

Idempotency keys become per user: the primary key moves from (key) to
(user_id, key), and response_json may be NULL while the claiming transaction is
still in flight (see app/services/idempotency.py).

Existing rows are deleted rather than backfilled. They have no owner, and they
are only a retry cache: losing one means a retry of a request made *before*
this migration would run as a new request. On the live demo the table should be
empty anyway, because keys were only stored after a successful transfer and no
wallet could be funded.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '7bdd2b550b65'
down_revision: Union[str, Sequence[str], None] = '0045bb75cb4a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute("DELETE FROM idempotency_keys")
    op.drop_constraint('idempotency_keys_pkey', 'idempotency_keys', type_='primary')
    op.add_column('idempotency_keys', sa.Column('user_id', sa.Integer(), nullable=False))
    op.create_foreign_key(
        'idempotency_keys_user_id_fkey', 'idempotency_keys', 'users', ['user_id'], ['id']
    )
    op.create_primary_key('idempotency_keys_pkey', 'idempotency_keys', ['user_id', 'key'])
    op.alter_column('idempotency_keys', 'response_json',
               existing_type=postgresql.JSON(astext_type=sa.Text()),
               nullable=True)


def downgrade() -> None:
    """Downgrade schema."""
    # Keys may repeat across users, which a global primary key cannot hold.
    op.execute("DELETE FROM idempotency_keys")
    op.alter_column('idempotency_keys', 'response_json',
               existing_type=postgresql.JSON(astext_type=sa.Text()),
               nullable=False)
    op.drop_constraint('idempotency_keys_pkey', 'idempotency_keys', type_='primary')
    op.drop_constraint('idempotency_keys_user_id_fkey', 'idempotency_keys', type_='foreignkey')
    op.drop_column('idempotency_keys', 'user_id')
    op.create_primary_key('idempotency_keys_pkey', 'idempotency_keys', ['key'])
