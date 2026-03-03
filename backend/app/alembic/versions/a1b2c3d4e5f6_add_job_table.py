"""add job table

Revision ID: a1b2c3d4e5f6
Revises: 146945cf3865
Create Date: 2026-02-27 00:10:00.000000

"""
from alembic import op
import sqlalchemy as sa
import sqlmodel.sql.sqltypes


# revision identifiers, used by Alembic.
revision = 'a1b2c3d4e5f6'
down_revision = '146945cf3865'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('job',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('chat_message_id', sa.Integer(), nullable=False),
    sa.Column('langflow_job_id', sqlmodel.sql.sqltypes.AutoString(length=255), nullable=True),
    sa.Column('flow_id', sqlmodel.sql.sqltypes.AutoString(length=255), nullable=True),
    sa.Column('status', sqlmodel.sql.sqltypes.AutoString(length=50), nullable=False),
    sa.Column('error_message', sa.Text(), nullable=True),
    sa.Column('result_content', sa.Text(), nullable=True),
    sa.Column('started_at', sa.DateTime(), nullable=True),
    sa.Column('completed_at', sa.DateTime(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['chat_message_id'], ['chat_message.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_job_chat_message_id'), 'job', ['chat_message_id'], unique=False)
    op.create_index(op.f('ix_job_langflow_job_id'), 'job', ['langflow_job_id'], unique=False)
    op.create_index(op.f('ix_job_status'), 'job', ['status'], unique=False)


def downgrade():
    op.drop_index(op.f('ix_job_status'), table_name='job')
    op.drop_index(op.f('ix_job_langflow_job_id'), table_name='job')
    op.drop_index(op.f('ix_job_chat_message_id'), table_name='job')
    op.drop_table('job')
