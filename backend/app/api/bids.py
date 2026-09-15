from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.security import current_user, officer
from app.core.config import settings
from app.models import Bid, Bidder, Tender, ProcessingRun, OfficerDecision, AIRecommendation, uid
from app.schemas import BidRequest, ProcessRequest, DecisionRequest
from app.repositories.review_repository import bid_summary, review, serialize
from app.services.processing_service import queue_run, process_bid
from app.services.audit_service import append_event

router = APIRouter(prefix='/api/bids', tags=['bids'])


def get_bid(db, bid_id, lock=False):
    query = select(Bid).where(Bid.id == bid_id)
    bid = db.scalar(query.with_for_update() if lock else query)
    if not bid:
        raise HTTPException(404, 'Bid not found')
    return bid


@router.get('')
def bids(db: Session = Depends(get_db), user=Depends(current_user)):
    return [bid_summary(db, b) for b in db.scalars(select(Bid).order_by(Bid.created_at))]


@router.post('', status_code=201)
def create_bid(body: BidRequest, db: Session = Depends(get_db), user=Depends(officer)):
    if not db.get(Tender, body.tender_id):
        raise HTTPException(404, 'Tender not found')
    bidder = Bidder(id=uid(), **body.model_dump(exclude={'tender_id'}), profile={'is_fictional': False})
    db.add(bidder)
    db.flush()
    bid = Bid(id=uid(), tender_id=body.tender_id, bidder_id=bidder.id, scenario='CUSTOM')
    db.add(bid)
    db.flush()
    append_event(db, action='BID_CREATED', object_id=bid.id, bid_id=bid.id, actor=user.email, role=user.role,
                 metadata={'bidder_name': bidder.name})
    return bid_summary(db, bid)


@router.get('/{bid_id}')
def detail(bid_id: str, db: Session = Depends(get_db), user=Depends(current_user)):
    return review(db, get_bid(db, bid_id))


@router.post('/{bid_id}/process', status_code=202)
def process(bid_id: str, body: ProcessRequest, tasks: BackgroundTasks, db: Session = Depends(get_db), user=Depends(officer)):
    bid = get_bid(db, bid_id, lock=True)
    if bid.status == 'PROCESSING':
        raise HTTPException(409, 'A verification run is already in progress')
    if body.unavailable_sources and not settings.demo_mode:
        raise HTTPException(403, 'Outage simulation is only available in demo mode')
    run = queue_run(db, bid, user.email, user.role)
    tasks.add_task(process_bid, run.id, body.unavailable_sources)
    return serialize(run)


@router.get('/{bid_id}/status')
def status(bid_id: str, db: Session = Depends(get_db), user=Depends(current_user)):
    bid = get_bid(db, bid_id)
    return {'bid_status': bid.status, 'run': serialize(db.get(ProcessingRun, bid.current_run_id)) if bid.current_run_id else None}


@router.get('/{bid_id}/verification')
@router.get('/{bid_id}/compliance')
@router.get('/{bid_id}/risk')
@router.get('/{bid_id}/ai-summary')
def findings(bid_id: str, db: Session = Depends(get_db), user=Depends(current_user)):
    return review(db, get_bid(db, bid_id))


@router.post('/{bid_id}/decision')
def decide(bid_id: str, body: DecisionRequest, db: Session = Depends(get_db), user=Depends(officer)):
    bid = get_bid(db, bid_id, lock=True)
    run = db.get(ProcessingRun, bid.current_run_id) if bid.current_run_id else None
    if not run or run.status != 'COMPLETED' or body.run_id != run.id:
        raise HTTPException(409, 'Review the latest completed verification run before deciding')
    ai = db.scalar(select(AIRecommendation).where(AIRecommendation.run_id == run.id))
    suggested = {'RECOMMEND COMPLIANT': 'QUALIFIED', 'RECOMMEND NON-COMPLIANT': 'DISQUALIFIED',
                 'MANUAL REVIEW REQUIRED': 'NEEDS CLARIFICATION'}[ai.result['recommended_action']]
    previous = {'decision': bid.final_decision, 'status': bid.status}
    decision = OfficerDecision(id=uid(), bid_id=bid.id, run_id=run.id, reviewer=user.email, **body.model_dump(exclude={'run_id'}),
                               ai_recommendation=ai.result['recommended_action'], is_override=body.decision != suggested)
    db.add(decision)
    bid.final_decision = body.decision
    bid.status = body.decision.replace(' ', '_')
    append_event(db, action='OFFICER_OVERRIDDEN' if decision.is_override else 'OFFICER_REVIEWED', object_id=decision.id,
                 object_type='officer_decision', bid_id=bid.id, actor=user.email, role=user.role,
                 previous_state=previous, new_state={'decision': body.decision},
                 metadata={'reason': body.reason, 'comments': body.comments, 'run_id': run.id, 'ai_recommendation_id': ai.id,
                           'ai_recommendation': ai.result['recommended_action'], 'is_override': decision.is_override})
    append_event(db, action='FINAL_DECISION_RECORDED', object_id=decision.id, object_type='officer_decision', bid_id=bid.id,
                 actor=user.email, role=user.role, metadata={'officer_decision_id': decision.id, 'run_id': run.id, 'decision': body.decision, 'reason': body.reason})
    return serialize(decision)
