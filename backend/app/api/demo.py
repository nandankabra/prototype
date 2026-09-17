from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.security import current_user, officer
from app.core.config import settings
from app.models import Bid
from app.services.processing_service import queue_run, process_bid
from app.repositories.review_repository import serialize

router = APIRouter(prefix='/api/demo', tags=['demo'])
SCENARIOS = [
    ('CLEAN', 'Clean bid', 'All required documents and source identifiers match.'),
    ('GST_MISMATCH', 'GST mismatch', 'ABC Industrial: a submitted GSTIN differs from the source.'),
    ('EXPIRED_DOCUMENT', 'Expired document', 'Experience certificate expires before the submission date.'),
    ('MISSING_OEM', 'Missing OEM', 'Mandatory OEM authorization is absent.'),
    ('MULTI_RISK', 'Multi-risk bid', 'Zenith: GST mismatch, expired experience, and missing OEM.'),
    ('BLACKLIST', 'Blacklist flag', 'A fictional debarment entry requires officer attention.'),
    ('NAME_VARIATION', 'Name variation', 'ABC: abbreviated and expanded company names normalize to a match.')]


@router.get('/scenarios')
def scenarios(db: Session = Depends(get_db), user=Depends(current_user)):
    return [{'id': code, 'name': name, 'description': description,
             'bid_id': db.scalar(select(Bid.id).where(Bid.scenario == code).order_by(Bid.created_at).limit(1))} for code, name, description in SCENARIOS]


@router.post('/initialize')
def initialize(user=Depends(officer)):
    """Warm unprocessed seeded bids while the hosting request remains active."""
    if not settings.demo_mode:
        raise HTTPException(404)
    from app.main import process_initial_seed
    process_initial_seed()
    return {'status': 'ready'}


@router.post('/run/{scenario}', status_code=202)
def run_scenario(scenario: str, tasks: BackgroundTasks, db: Session = Depends(get_db), user=Depends(officer)):
    if not settings.demo_mode:
        raise HTTPException(404)
    if scenario not in {s[0] for s in SCENARIOS}:
        raise HTTPException(404, 'Unknown demo scenario')
    bid = db.scalar(select(Bid).where(Bid.scenario == scenario).order_by(Bid.created_at).limit(1).with_for_update())
    if not bid:
        raise HTTPException(404, 'Seed the demo data first')
    if bid.status == 'PROCESSING':
        raise HTTPException(409, 'This bid is currently processing')
    run = queue_run(db, bid, user.email, user.role)
    if settings.hosted_mode:
        process_bid(run.id)
        db.refresh(run)
    else:
        tasks.add_task(process_bid, run.id)
    return serialize(run)
