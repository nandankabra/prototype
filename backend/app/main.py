from contextlib import asynccontextmanager
import logging
from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select, text
from app.core.database import SessionLocal
from app.core.config import settings
from app.core.security import current_user
from app.api import auth, tenders, bids, documents, audit, dashboard, evidence, sources
from app.models import Bid, ProcessingRun
from app.services.source_registry import ensure_sources

logging.basicConfig(level=logging.INFO, format='%(message)s')


@asynccontextmanager
async def lifespan(app):
    settings.signing_key()
    # A process restart must not leave an abandoned job displayed as running forever.
    with SessionLocal() as db:
        abandoned = select(ProcessingRun).where(ProcessingRun.status.in_(['RUNNING', 'QUEUED']))
        if settings.hosted_mode:
            # A different instance may still be working; only expire stale jobs.
            from datetime import datetime, timedelta, timezone
            abandoned = abandoned.where(ProcessingRun.created_at < datetime.now(timezone.utc) - timedelta(minutes=15))
        for run in db.scalars(abandoned):
            run.status = 'FAILED'
            run.error = 'Service restarted during this run. Start a new review; saved evidence is retained.'
            bid = db.get(Bid, run.bid_id)
            if bid.current_run_id == run.id:
                bid.status = 'PROCESSING_FAILED'
        db.commit()
        ensure_sources(db)
    yield


app = FastAPI(title='ByteCode Verify API', version='1.0.0', lifespan=lifespan,
              description='Evidence-backed procurement verification and decision support. Officers retain final authority.')
app.add_middleware(CORSMiddleware, allow_origins=['http://localhost:3000', 'http://127.0.0.1:3000'],
                   allow_credentials=True, allow_methods=['GET', 'POST', 'PUT'], allow_headers=['Authorization', 'Content-Type'])
for router in [auth.router, tenders.router, bids.router, documents.router, audit.router, dashboard.router, evidence.router, sources.router]:
    app.include_router(router)


@app.get('/health', tags=['health'])
def health():
    with SessionLocal() as db:
        db.execute(text('SELECT 1'))
    return {'status': 'ok', 'app': 'ByteCode Verify'}


@app.get('/api/system', tags=['health'])
def system(user=Depends(current_user)):
    return {'database': 'PostgreSQL' if settings.database_url.startswith('postgres') else 'SQLite local fallback',
            'source_label': 'Authoritative source registry', 'source_count': 11,
            'ocr': 'PaddleOCR → Tesseract → readable PDF text; unreadable content requires manual review',
            'heavy_ml_enabled': settings.enable_heavy_ml, 'vector': 'Qdrant → FAISS → in-memory',
            'llm': 'External provider with evidence validation' if settings.llm_api_key and settings.llm_provider != 'mock' else 'Evidence-based MockLLMProvider',
            'upload_max_mb': settings.upload_max_mb,
            'scope': 'Government integrations require authorised credentials, consent, and provider onboarding'}
