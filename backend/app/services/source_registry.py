from sqlalchemy import select
from app.adapters.government.registry import SOURCES
from app.models import VerificationSource, uid


def ensure_sources(db):
    for priority, (code, document_type, authority, url, method) in enumerate(SOURCES, start=1):
        source = db.scalar(select(VerificationSource).where(VerificationSource.source_code == code))
        if source:
            continue
        db.add(VerificationSource(id=uid(), source_code=code, document_type=document_type, source_name=code,
               authority=authority, base_url=url, verification_method=method, api_available=False,
               api_requires_approval=True, manual_fallback=True, enabled=True, priority=priority))
    db.commit()
