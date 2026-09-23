"""add treasury account uniqueness per owner

Revision ID: 86579472250b
Revises: 7bdd2b550b65
Create Date: 2026-09-23 12:28:38.683700

Concurrent first-ever deposits could each miss the "does the treasury account
exist?" SELECT and each insert their own "__treasury__" account for the system
user, since accounts had no uniqueness constraint at all. This adds a partial
unique index on accounts.user_id, scoped to name = '__treasury__', so that
lazy creation in app/services/transfer_service.py::_treasury_wallet can use
INSERT ... ON CONFLICT DO NOTHING to stay race-safe. It is scoped to that one
name rather than a general (user_id, name) constraint so ordinary users keep
being able to name one of their own accounts "__treasury__" (see the same
module: the treasury lookup matches on owner as well as name, so a user's
account with that name is never mistaken for the real one).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '86579472250b'
down_revision: Union[str, Sequence[str], None] = '7bdd2b550b65'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_index(
        'uq_treasury_account_per_owner',
        'accounts',
        ['user_id'],
        unique=True,
        postgresql_where=sa.text("name = '__treasury__'"),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('uq_treasury_account_per_owner', table_name='accounts')
