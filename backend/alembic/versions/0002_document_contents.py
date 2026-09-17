"""Durable original document storage for hosted instances."""
from alembic import op
from app.models import DocumentContent

revision = '0002'
down_revision = '0001'
branch_labels = None
depends_on = None


def upgrade():
    # 0001 builds current metadata for fresh databases; check_first also supports upgrades.
    DocumentContent.__table__.create(bind=op.get_bind(), checkfirst=True)


def downgrade():
    DocumentContent.__table__.drop(bind=op.get_bind(), checkfirst=True)
