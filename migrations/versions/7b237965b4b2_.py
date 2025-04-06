"""empty message

Revision ID: 7b237965b4b2
Revises: 2e6ce5b4bbf3
Create Date: 2025-04-02 18:20:25.838414

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '7b237965b4b2'
down_revision = '2e6ce5b4bbf3'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('chat_messages',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.Column('updated_at', sa.DateTime(), nullable=True),
    sa.Column('booking_id', sa.Integer(), nullable=False),
    sa.Column('sender_id', sa.Integer(), nullable=False),
    sa.Column('sender_type', sa.String(), nullable=False),
    sa.Column('message', sa.Text(), nullable=False),
    sa.Column('is_read', sa.Boolean(), nullable=True),
    sa.ForeignKeyConstraint(['booking_id'], ['bookings.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.add_column('bookings', sa.Column('has_unread_messages', sa.Boolean(), nullable=True))
    op.add_column('bookings', sa.Column('last_message_at', sa.DateTime(), nullable=True))
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('bookings', 'last_message_at')
    op.drop_column('bookings', 'has_unread_messages')
    op.drop_table('chat_messages')
    # ### end Alembic commands ###
