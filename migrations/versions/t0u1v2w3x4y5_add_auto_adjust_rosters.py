"""add auto_adjust_rosters to fantasy_leagues

Revision ID: t0u1v2w3x4y5
Revises: f1a2b3c4d5e6
Create Date: 2026-04-29
"""
from alembic import op
import sqlalchemy as sa

revision = 't0u1v2w3x4y5'
down_revision = 'f1a2b3c4d5e6'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        'fantasy_leagues',
        sa.Column('auto_adjust_rosters', sa.Boolean(), nullable=False, server_default='false'),
    )


def downgrade():
    op.drop_column('fantasy_leagues', 'auto_adjust_rosters')
