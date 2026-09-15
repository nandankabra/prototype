from collections import Counter
from fastapi import APIRouter, Depends
from sqlalchemy import select, func
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.security import current_user
from app.models import Bid, Tender, AuditEvent, SourceVerification, OfficerDecision, Document
from app.repositories.review_repository import bid_summary, serialize
from app.services.audit_service import verify_chain

router = APIRouter(prefix='/api/dashboard', tags=['dashboard'])


@router.get('/summary')
def summary(db: Session = Depends(get_db), user=Depends(current_user)):
    bids = [bid_summary(db, b) for b in db.scalars(select(Bid).order_by(Bid.created_at))]
    scores = [b['compliance_score'] for b in bids if b['compliance_score'] is not None]
    current_runs = [b['current_run_id'] for b in bids if b['current_run_id']]
    verification = Counter(v.status for v in db.scalars(select(SourceVerification).where(SourceVerification.run_id.in_(current_runs))))
    risk = Counter(b['risk_level'] for b in bids)
    distribution = Counter('90–100' if s >= 90 else '75–89' if s >= 75 else '50–74' if s >= 50 else '0–49' for s in scores)
    throughput = Counter(str(d.created_at.date()) for d in db.scalars(select(OfficerDecision)))
    events = list(db.scalars(select(AuditEvent).order_by(AuditEvent.sequence)))
    return {'total_tenders': db.scalar(select(func.count()).select_from(Tender)), 'total_bids': len(bids),
            'total_documents': db.scalar(select(func.count()).select_from(Document)),
            'active_reviews': sum(b['status'] == 'PROCESSING' for b in bids),
            'high_risk_bids': sum(b['risk_level'] in {'HIGH', 'CRITICAL'} for b in bids),
            'pending_decisions': sum(b['final_decision'] is None for b in bids),
            'average_compliance': round(sum(scores)/len(scores), 1) if scores else None,
            'issues_detected': sum(b['issues'] for b in bids), 'assessed_bids': len(scores),
            'compliance_distribution': [{'name': name, 'value': distribution[name]} for name in ['0–49', '50–74', '75–89', '90–100']],
            'risk_distribution': [{'name': name, 'value': risk[name]} for name in ['LOW', 'MEDIUM', 'HIGH', 'CRITICAL', 'UNASSESSED']],
            'verification_status': [{'name': key, 'value': value} for key, value in verification.items()],
            'review_throughput': [{'name': key, 'value': value} for key, value in sorted(throughput.items())],
            'recent_events': [serialize(e, ('payload',)) for e in reversed(events[-8:])],
            'priority_bids': sorted(bids, key=lambda b: (b['final_decision'] is not None, -(b['risk_score'] or 0)))[:6],
            'integrity': verify_chain(events), 'sources_label': 'MOCK AUTHORISED SOURCE — DEMO'}
