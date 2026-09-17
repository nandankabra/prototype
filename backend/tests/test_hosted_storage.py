from pathlib import Path
import pytest
from sqlalchemy import select
from app.core.config import Settings, settings
from app.models import Bid, DocumentContent
from app.services.document_service import save_upload, document_path
from app.services.sample_service import make_sample


def test_original_restored_after_instance_cache_loss(db, monkeypatch):
    monkeypatch.setattr(settings, 'document_storage', 'database')
    bid = db.scalar(select(Bid).where(Bid.scenario == 'CLEAN'))
    content = make_sample('Hosted persistence test', 'pan', {'PAN': 'ABCDE1234F'})
    doc = save_upload(db, bid.id, 'durable.pdf', content)
    db.commit()
    assert db.get(DocumentContent, doc.id).content == content
    cached = document_path(doc)
    cached.unlink()
    assert document_path(doc).read_bytes() == content
    cached.unlink()
    saved = db.get(DocumentContent, doc.id)
    saved.content = b'corrupted original'
    db.commit()
    with pytest.raises(ValueError, match='integrity'):
        document_path(doc)
    saved.content = content
    db.commit()


def test_hosted_settings_require_persistence_and_stable_key():
    with pytest.raises(RuntimeError, match='Hosted deployments require'):
        Settings(hosted_mode=True, jwt_secret='', _env_file=None).signing_key()
    configured = Settings(hosted_mode=True, jwt_secret='stable-test-key',
                          database_url='postgresql://user:password@example.invalid/db',
                          document_storage='database', _env_file=None)
    assert configured.database_url.startswith('postgresql+psycopg://')
    assert configured.signing_key() == 'stable-test-key'


def test_hosted_review_finishes_before_response(client, monkeypatch):
    bid = next(b for b in client.get('/api/bids').json() if b['scenario'] == 'MULTI_RISK')
    # Authentication invokes signing_key too, so preserve the test signing key.
    key = settings.signing_key()
    monkeypatch.setattr(type(settings), 'signing_key', lambda self: key)
    monkeypatch.setattr(settings, 'hosted_mode', True)
    response = client.post('/api/bids/' + bid['id'] + '/process', json={})
    assert response.status_code == 202
    assert response.json()['status'] == 'COMPLETED'
    refreshed = client.get('/api/bids/' + bid['id']).json()
    assert refreshed['risk_score'] == 58
    assert refreshed['compliance_score'] == 74.1
