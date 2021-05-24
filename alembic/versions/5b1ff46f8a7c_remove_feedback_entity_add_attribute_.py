"""remove feedback entity, add attribute rate to pairs

Revision ID: 5b1ff46f8a7c
Revises: d32e7b7c5969
Create Date: 2021-05-24 03:14:54.879140

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '5b1ff46f8a7c'
down_revision = 'd32e7b7c5969'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_index('ix_feedbacks_id', table_name='feedbacks')
    op.drop_table('feedbacks')
    op.add_column('pairs', sa.Column('rate', sa.Integer(), nullable=True))
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('pairs', 'rate')
    op.create_table('feedbacks',
    sa.Column('id', sa.INTEGER(), autoincrement=True, nullable=False),
    sa.Column('user_id', sa.INTEGER(), autoincrement=False, nullable=True),
    sa.Column('rate', sa.INTEGER(), autoincrement=False, nullable=True),
    sa.Column('created_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), autoincrement=False, nullable=True),
    sa.Column('updated_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), autoincrement=False, nullable=True),
    sa.ForeignKeyConstraint(['user_id'], ['users.tg_id'], name='feedbacks_user_id_fkey'),
    sa.PrimaryKeyConstraint('id', name='feedbacks_pkey')
    )
    op.create_index('ix_feedbacks_id', 'feedbacks', ['id'], unique=True)
    # ### end Alembic commands ###