"""add generation_events

Revision ID: f026f0d6ae64
Revises: 1a04b1211165
Create Date: 2026-09-01 15:07:27.206056

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'f026f0d6ae64'
down_revision: Union[str, None] = '1a04b1211165'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'generation_events',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('cv_generation_id', sa.String(length=36), nullable=False),
        sa.Column('llm_run_id', sa.String(length=36), nullable=True),
        sa.Column('stage', sa.String(length=32), nullable=False),
        sa.Column('status', sa.String(length=16), nullable=False),
        sa.Column('message', sa.Text(), nullable=True),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['cv_generation_id'], ['cv_generations.id'], ),
        sa.ForeignKeyConstraint(['llm_run_id'], ['llm_runs.id'], ),
        sa.PrimaryKeyConstraint('id'),
    )


def downgrade() -> None:
    op.drop_table('generation_events')
