from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.security import current_user, officer, admin
from app.models import Tender, TenderRule, Bid, uid
from app.schemas import TenderRequest, RulesUpdate
from app.engines.scoring_engine import DEFAULT_WEIGHTS
from app.repositories.review_repository import serialize, bid_summary
from app.services.audit_service import append_event
from app.seed import RULES

router = APIRouter(prefix='/api/tenders', tags=['tenders'])


def get_tender(db, tender_id):
    tender = db.get(Tender, tender_id)
    if not tender:
        raise HTTPException(404, 'Tender not found')
    return tender


@router.get('')
def tenders(db: Session = Depends(get_db), user=Depends(current_user)):
    results = []
    for tender in db.scalars(select(Tender).order_by(Tender.reference)):
        bids = [bid_summary(db, b) for b in db.scalars(select(Bid).where(Bid.tender_id == tender.id))]
        scores = [b['compliance_score'] for b in bids if b['compliance_score'] is not None]
        levels = ['UNASSESSED', 'LOW', 'MEDIUM', 'HIGH', 'CRITICAL']
        results.append({**serialize(tender), 'bidder_count': len(bids), 'pending': sum(not b['final_decision'] for b in bids),
                        'average_compliance': round(sum(scores)/len(scores), 1) if scores else None,
                        'highest_risk': max((b['risk_level'] for b in bids), key=levels.index, default='UNASSESSED'),
                        'review_status': 'COMPLETED' if bids and all(b['final_decision'] for b in bids) else 'IN REVIEW'})
    return results


@router.post('', status_code=201)
def create_tender(body: TenderRequest, db: Session = Depends(get_db), user=Depends(officer)):
    if db.scalar(select(Tender).where(Tender.reference == body.reference)):
        raise HTTPException(409, 'Tender reference already exists')
    tender = Tender(id=uid(), **body.model_dump(), scoring_weights=DEFAULT_WEIGHTS)
    db.add(tender)
    db.flush()
    for code, name, category, expression, severity in RULES:
        expression = dict(expression)
        if expression['op'] == 'minimum_field':
            expression['value'] = body.local_content_threshold
        db.add(TenderRule(tender_id=tender.id, rule_id=code, name=name, category=category, expression=expression, severity=severity))
    append_event(db, action='TENDER_CREATED', object_id=tender.id, object_type='tender', actor=user.email, role=user.role,
                 metadata={'reference': tender.reference})
    return serialize(tender)


@router.get('/{tender_id}')
def detail(tender_id: str, db: Session = Depends(get_db), user=Depends(current_user)):
    tender = get_tender(db, tender_id)
    return {**serialize(tender), 'bids': [bid_summary(db, b) for b in db.scalars(select(Bid).where(Bid.tender_id == tender_id))],
            'rules': [serialize(r) for r in db.scalars(select(TenderRule).where(TenderRule.tender_id == tender_id).order_by(TenderRule.rule_id))]}


@router.put('/{tender_id}/rules')
def update_rules(tender_id: str, body: RulesUpdate, db: Session = Depends(get_db), user=Depends(admin)):
    tender = get_tender(db, tender_id)
    existing = {r.id: r for r in db.scalars(select(TenderRule).where(TenderRule.tender_id == tender_id))}
    if {r.id for r in body.rules} != set(existing) or len(body.rules) != len(existing):
        raise HTTPException(422, 'The editor must include each existing rule exactly once')
    previous = {'rules': [serialize(r) for r in existing.values()], 'weights': tender.scoring_weights}
    for value in body.rules:
        rule = existing[value.id]
        for key, item in value.model_dump(exclude={'id', 'rule_id'}).items():
            setattr(rule, key, item)
    tender.scoring_weights = body.scoring_weights
    threshold = next((r.expression['value'] for r in body.rules if r.expression['op'] == 'minimum_field'), tender.local_content_threshold)
    tender.local_content_threshold = threshold
    append_event(db, action='TENDER_RULES_UPDATED', object_type='tender', object_id=tender_id, actor=user.email, role=user.role,
                 metadata={'previous': previous, 'new': body.model_dump(), 'note': 'Existing results remain versioned; rerun to apply these rules'})
    return {'status': 'saved', 'message': 'Rules saved. Run a new review to apply the updated rules.'}
