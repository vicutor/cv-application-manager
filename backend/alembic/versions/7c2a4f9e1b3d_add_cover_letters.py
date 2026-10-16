"""add cover_letters

Revision ID: 7c2a4f9e1b3d
Revises: 36f185e52c40
Create Date: 2026-09-02 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '7c2a4f9e1b3d'
down_revision: Union[str, None] = '36f185e52c40'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'cover_letters',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('job_posting_id', sa.String(length=36), nullable=False),
        sa.Column('candidate_profile_version_id', sa.String(length=36), nullable=False),
        sa.Column('job_analysis_id', sa.String(length=36), nullable=True),
        sa.Column('version_number', sa.Integer(), nullable=False),
        sa.Column('language', sa.String(length=8), nullable=False),
        sa.Column('status', sa.String(length=16), nullable=False),
        sa.Column('content_text', sa.Text(), nullable=True),
        sa.Column('word_count', sa.Integer(), nullable=True),
        sa.Column('sounds_ai_flagged', sa.Boolean(), nullable=False),
        sa.Column('ai_check_notes', sa.Text(), nullable=True),
        sa.Column('model_provider', sa.String(length=64), nullable=True),
        sa.Column('model_name', sa.String(length=64), nullable=True),
        sa.Column('prompt_version', sa.String(length=32), nullable=True),
        sa.Column('error_stage', sa.String(length=32), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['job_posting_id'], ['job_postings.id'], ),
        sa.ForeignKeyConstraint(['candidate_profile_version_id'], ['candidate_profile_versions.id'], ),
        sa.ForeignKeyConstraint(['job_analysis_id'], ['job_analyses.id'], ),
        sa.PrimaryKeyConstraint('id'),
    )
    with op.batch_alter_table('llm_runs') as batch_op:
        batch_op.add_column(sa.Column('cover_letter_id', sa.String(length=36), nullable=True))
        batch_op.create_foreign_key(
            'fk_llm_runs_cover_letter_id', 'cover_letters', ['cover_letter_id'], ['id']
        )


def downgrade() -> None:
    with op.batch_alter_table('llm_runs') as batch_op:
        batch_op.drop_constraint('fk_llm_runs_cover_letter_id', type_='foreignkey')
        batch_op.drop_column('cover_letter_id')
    op.drop_table('cover_letters')
