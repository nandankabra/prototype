"""Bind bidder submissions to the authenticated bidder account."""
from alembic import op
import sqlalchemy as sa

revision = '0004'
down_revision = '0003'
branch_labels = None
depends_on = None


def upgrade():
    columns = {column['name'] for column in sa.inspect(op.get_bind()).get_columns('bids')}
    if 'submitted_by_user_id' not in columns:
        op.add_column('bids', sa.Column('submitted_by_user_id', sa.String(36), sa.ForeignKey('users.id'), nullable=True))
        op.create_index('ix_bids_submitted_by_user_id', 'bids', ['submitted_by_user_id'])


def downgrade():
    op.drop_index('ix_bids_submitted_by_user_id', table_name='bids')
    op.drop_column('bids', 'submitted_by_user_id')
