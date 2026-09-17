"""Tender ingestion, requirement evidence, source registry, and audit support."""
from alembic import op
import sqlalchemy as sa

revision = '0003'
down_revision = '0002'
branch_labels = None
depends_on = None


def upgrade():
    # 0001 historically creates the current SQLAlchemy metadata for a new
    # database. In that fresh-install path these tables already exist.
    if 'tender_requirements' in sa.inspect(op.get_bind()).get_table_names():
        return
    for name, column in [
        ('external_bid_id', sa.Column('external_bid_id', sa.String(120), nullable=True)),
        ('source', sa.Column('source', sa.String(40), nullable=False, server_default='GEM')),
        ('source_url', sa.Column('source_url', sa.Text(), nullable=True)),
        ('category', sa.Column('category', sa.String(255), nullable=True)),
        ('ministry', sa.Column('ministry', sa.String(255), nullable=True)),
        ('organisation', sa.Column('organisation', sa.String(255), nullable=True)),
        ('buyer', sa.Column('buyer', sa.String(255), nullable=True)),
        ('bid_type', sa.Column('bid_type', sa.String(60), nullable=True)),
        ('estimated_value', sa.Column('estimated_value', sa.Float(), nullable=True)),
        ('status', sa.Column('status', sa.String(40), nullable=False, server_default='IMPORTED')),
        ('last_synced_at', sa.Column('last_synced_at', sa.DateTime(timezone=True), nullable=True)),
        ('raw_metadata', sa.Column('raw_metadata', sa.JSON(), nullable=False, server_default='{}')),
        ('content_hash', sa.Column('content_hash', sa.String(64), nullable=True)),
    ]:
        op.add_column('tenders', column)
    op.execute("UPDATE tenders SET source = 'LEGACY_ARCHIVED' WHERE external_bid_id IS NULL")
    op.create_index('ix_tenders_external_bid_id', 'tenders', ['external_bid_id'])
    op.create_table('tender_versions', sa.Column('id', sa.String(36), primary_key=True), sa.Column('created_at', sa.DateTime(timezone=True)), sa.Column('tender_id', sa.String(36), sa.ForeignKey('tenders.id'), nullable=False), sa.Column('version_number', sa.Integer(), nullable=False), sa.Column('content_hash', sa.String(64), nullable=False), sa.Column('metadata', sa.JSON(), nullable=False), sa.Column('change_summary', sa.JSON(), nullable=False))
    op.create_table('tender_documents', sa.Column('id', sa.String(36), primary_key=True), sa.Column('created_at', sa.DateTime(timezone=True)), sa.Column('tender_id', sa.String(36), sa.ForeignKey('tenders.id'), nullable=False), sa.Column('url', sa.Text(), nullable=False), sa.Column('document_type', sa.String(60), nullable=False), sa.Column('sha256', sa.String(64), nullable=False), sa.Column('extracted_text', sa.Text(), nullable=False), sa.Column('pages', sa.JSON(), nullable=False), sa.Column('fetch_status', sa.String(40), nullable=False))
    op.create_table('tender_requirements', sa.Column('id', sa.String(36), primary_key=True), sa.Column('created_at', sa.DateTime(timezone=True)), sa.Column('tender_id', sa.String(36), sa.ForeignKey('tenders.id'), nullable=False), sa.Column('requirement_code', sa.String(80), nullable=False), sa.Column('type', sa.String(80), nullable=False), sa.Column('label', sa.String(255), nullable=False), sa.Column('mandatory', sa.Boolean(), nullable=False), sa.Column('requirement_value', sa.JSON(), nullable=False), sa.Column('accepted_evidence', sa.JSON(), nullable=False), sa.Column('exemptions', sa.JSON(), nullable=False), sa.Column('source_document_id', sa.String(36), sa.ForeignKey('tender_documents.id')), sa.Column('source_page', sa.Integer()), sa.Column('source_clause', sa.String(160)), sa.Column('source_text', sa.Text(), nullable=False), sa.Column('confidence', sa.Float(), nullable=False), sa.Column('status', sa.String(40), nullable=False))
    op.create_table('tender_corrigenda', sa.Column('id', sa.String(36), primary_key=True), sa.Column('created_at', sa.DateTime(timezone=True)), sa.Column('tender_id', sa.String(36), sa.ForeignKey('tenders.id'), nullable=False), sa.Column('source_url', sa.Text(), nullable=False), sa.Column('published_at', sa.DateTime(timezone=True)), sa.Column('content_hash', sa.String(64), nullable=False), sa.Column('changed_clauses', sa.JSON(), nullable=False))
    op.create_table('verification_sources', sa.Column('id', sa.String(36), primary_key=True), sa.Column('created_at', sa.DateTime(timezone=True)), sa.Column('source_code', sa.String(40), unique=True, nullable=False), sa.Column('document_type', sa.String(80), nullable=False), sa.Column('source_name', sa.String(255), nullable=False), sa.Column('authority', sa.String(255), nullable=False), sa.Column('base_url', sa.Text(), nullable=False), sa.Column('verification_method', sa.String(60), nullable=False), sa.Column('api_available', sa.Boolean(), nullable=False), sa.Column('api_requires_approval', sa.Boolean(), nullable=False), sa.Column('manual_fallback', sa.Boolean(), nullable=False), sa.Column('enabled', sa.Boolean(), nullable=False), sa.Column('last_health_check', sa.DateTime(timezone=True)), sa.Column('priority', sa.Integer(), nullable=False))
    op.create_table('cross_document_checks', sa.Column('id', sa.String(36), primary_key=True), sa.Column('created_at', sa.DateTime(timezone=True)), sa.Column('run_id', sa.String(36), sa.ForeignKey('processing_runs.id'), nullable=False), sa.Column('field', sa.String(80), nullable=False), sa.Column('status', sa.String(32), nullable=False), sa.Column('reason', sa.Text(), nullable=False), sa.Column('evidence', sa.JSON(), nullable=False))
    op.create_table('clarification_requests', sa.Column('id', sa.String(36), primary_key=True), sa.Column('created_at', sa.DateTime(timezone=True)), sa.Column('bid_id', sa.String(36), sa.ForeignKey('bids.id'), nullable=False), sa.Column('requirement_id', sa.String(36), sa.ForeignKey('tender_requirements.id')), sa.Column('requested_by', sa.String(255), nullable=False), sa.Column('message', sa.Text(), nullable=False), sa.Column('status', sa.String(32), nullable=False))


def downgrade():
    for table in ['clarification_requests', 'cross_document_checks', 'verification_sources', 'tender_corrigenda', 'tender_requirements', 'tender_documents', 'tender_versions']:
        op.drop_table(table)
    op.drop_index('ix_tenders_external_bid_id', table_name='tenders')
    for name in ['content_hash','raw_metadata','last_synced_at','status','estimated_value','bid_type','buyer','organisation','ministry','category','source_url','source','external_bid_id']:
        op.drop_column('tenders', name)
