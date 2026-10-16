"""add cover_letters.latex_path / pdf_path

Revision ID: 9d3e7a1c5f22
Revises: 7c2a4f9e1b3d
Create Date: 2026-09-02 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '9d3e7a1c5f22'
down_revision: Union[str, None] = '7c2a4f9e1b3d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('cover_letters') as batch_op:
        batch_op.add_column(sa.Column('latex_path', sa.Text(), nullable=True))
        batch_op.add_column(sa.Column('pdf_path', sa.Text(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('cover_letters') as batch_op:
        batch_op.drop_column('pdf_path')
        batch_op.drop_column('latex_path')
