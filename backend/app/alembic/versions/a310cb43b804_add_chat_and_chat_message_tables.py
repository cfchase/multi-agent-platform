"""Add chat and chat_message tables

Revision ID: a310cb43b804
Revises: 78f50c51ff51
Create Date: 2026-01-29 14:20:36.608948

"""
from alembic import op
import sqlalchemy as sa
import sqlmodel.sql.sqltypes

# revision identifiers, used by Alembic.
revision = 'a310cb43b804'
down_revision = '78f50c51ff51'
branch_labels = None
depends_on = None


def upgrade():
    # Create chat table
    op.create_table('chat',
        sa.Column('title', sqlmodel.sql.sqltypes.AutoString(length=255), nullable=False),
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['user.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )

    # Create chat_message table
    op.create_table('chat_message',
        sa.Column('content', sqlmodel.sql.sqltypes.AutoString(length=10000), nullable=False),
        sa.Column('role', sqlmodel.sql.sqltypes.AutoString(length=20), nullable=False),
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('chat_id', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['chat_id'], ['chat.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )


def downgrade():
    op.drop_table('chat_message')
    op.drop_table('chat')
