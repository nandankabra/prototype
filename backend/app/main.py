from contextlib import asynccontextmanager
from concurrent.futures import ThreadPoolExecutor
import logging
import json
from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select, text
from app.core.database import SessionLocal
from app.core.config import settings
from app.core.security import current_user
from app.api import auth, tenders, bids, documents, audit, dashboard, demo, evidence
from app.models import Bid, Document, ProcessingRun
from app.services.processing_service import queue_run, process_bid

logging.basicConfig(level=logging.INFO, format='%(message)s')


def process_initial_seed():
    """Warm genuine seeded results once, using exactly the same pipeline as uploaded bids."""
    with SessionLocal() as db:
        initial = list(db.scalars(select(Bid).where(Bid.current_run_id.is_(None), Bid.scenario != 'CUSTOM')))
        identifiers = [b.id for b in initial if all(d.is_seed for d in db.scalars(select(Document).where(Document.bid_id == b.id)))]
    for bid_id in identifiers:
        with SessionLocal() as db:
            bid = db.scalar(select(Bid).where(Bid.id == bid_id).with_for_update())
            if bid.current_run_id:
                continue
            run = queue_run(db, bid, 'demo-initialization', 'SYSTEM')
            run_id = run.id
        process_bid(run_id)


@asynccontextmanager
async def lifespan(app):
    settings.signing_key()
    # A process restart must not leave an abandoned job displayed as running forever.
    with SessionLocal() as db:
        for run in db.scalars(select(ProcessingRun).where(ProcessingRun.status.in_(['RUNNING', 'QUEUED']))):
            run.status = 'FAILED'
            run.error = 'Service restarted during this run. Start a new review; saved evidence is retained.'
            bid = db.get(Bid, run.bid_id)
            if bid.current_run_id == run.id:
                bid.status = 'PROCESSING_FAILED'
        db.commit()
    pool = ThreadPoolExecutor(max_workers=1)
    if settings.demo_mode:
        pool.submit(process_initial_seed)
    yield
    pool.shutdown(wait=True, cancel_futures=True)


app = FastAPI(title='ByteCode Verify API', version='1.0.0', lifespan=lifespan,
              description='Evidence-backed procurement decision support. All source checks use MOCK AUTHORISED SOURCE — DEMO records. Officers retain final authority.')
app.add_middleware(CORSMiddleware, allow_origins=['http://localhost:3000', 'http://127.0.0.1:3000'],
                   allow_credentials=True, allow_methods=['GET', 'POST', 'PUT'], allow_headers=['Authorization', 'Content-Type'])
for router in [auth.router, tenders.router, bids.router, documents.router, audit.router, dashboard.router, demo.router, evidence.router]:
    app.include_router(router)


@app.get('/health', tags=['health'])
def health():
    with SessionLocal() as db:
        db.execute(text('SELECT 1'))
    return {'status': 'ok', 'app': 'ByteCode Verify', 'demo_mode': settings.demo_mode}


@app.get('/api/system', tags=['health'])
def system(user=Depends(current_user)):
    return {'demo_mode': settings.demo_mode, 'database': 'PostgreSQL' if settings.database_url.startswith('postgres') else 'SQLite local fallback',
            'source_label': 'MOCK AUTHORISED SOURCE — DEMO', 'source_count': 11,
            'ocr': 'PaddleOCR → Tesseract → readable PDF text; unreadable content requires manual review',
            'heavy_ml_enabled': settings.enable_heavy_ml, 'vector': 'Qdrant → FAISS → in-memory',
            'llm': 'External provider with evidence validation' if settings.llm_api_key and settings.llm_provider != 'mock' else 'Evidence-based MockLLMProvider',
            'scope': 'Local laptop prototype; no production government connectivity'}
