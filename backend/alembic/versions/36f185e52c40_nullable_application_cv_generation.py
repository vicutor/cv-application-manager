"""make applications.cv_generation_id nullable

Revision ID: 36f185e52c40
Revises: f026f0d6ae64
Create Date: 2026-09-02 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '36f185e52c40'
down_revision: Union[str, None] = 'f026f0d6ae64'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # A user can mark a posting as applied without having generated a CV
    # through this app (e.g. they applied with a CV of their own) -- the FK
    # stays, it's just optional now.
    with op.batch_alter_table('applications') as batch_op:
        batch_op.alter_column('cv_generation_id', existing_type=sa.String(length=36), nullable=True)


def downgrade() -> None:
    with op.batch_alter_table('applications') as batch_op:
        batch_op.alter_column('cv_generation_id', existing_type=sa.String(length=36), nullable=False)
