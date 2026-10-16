"""add job_analyses.responsibilities

Revision ID: 1a04b1211165
Revises: b5d7a8ead2b2
Create Date: 2026-09-01 12:26:44.731854

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '1a04b1211165'
down_revision: Union[str, None] = 'b5d7a8ead2b2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # server_default required: SQLite ADD COLUMN with NOT NULL needs a default to
    # backfill any existing rows; dropped again after so the ORM-level default
    # (Python-side, per new row) is the only one in effect going forward.
    op.add_column(
        'job_analyses',
        sa.Column('responsibilities', sa.JSON(), nullable=False, server_default='[]'),
    )
    with op.batch_alter_table('job_analyses') as batch_op:
        batch_op.alter_column('responsibilities', server_default=None)


def downgrade() -> None:
    op.drop_column('job_analyses', 'responsibilities')
