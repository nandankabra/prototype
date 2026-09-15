from fastapi import APIRouter, Depends
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.security import current_user
from app.models import AuditEvent
from app.repositories.review_repository import serialize, review
from app.services.audit_service import verify_chain
from app.services.report_service import audit_pdf
from app.api.bids import get_bid

router = APIRouter(tags=['audit'])


def all_events(db):
    return list(db.scalars(select(AuditEvent).order_by(AuditEvent.sequence)))


@router.get('/api/audit')
def audit(bid_id: str | None = None, action: str | None = None, db: Session = Depends(get_db), user=Depends(current_user)):
    events = all_events(db)
    filtered = [e for e in events if (not bid_id or e.bid_id == bid_id) and (not action or action.upper() in e.action)]
    return {'integrity': verify_chain(events), 'events': [serialize(e, ('payload',)) for e in reversed(filtered)]}


@router.get('/api/bids/{bid_id}/audit')
def bid_audit(bid_id: str, db: Session = Depends(get_db), user=Depends(current_user)):
    get_bid(db, bid_id)
    return audit(bid_id=bid_id, action=None, db=db, user=user)


@router.get('/api/audit/export')
def export(bid_id: str | None = None, db: Session = Depends(get_db), user=Depends(current_user)):
    events = all_events(db)
    data = review(db, get_bid(db, bid_id)) if bid_id else None
    selected = [serialize(e, ('payload',)) for e in events if not bid_id or e.bid_id == bid_id]
    return Response(audit_pdf(selected, verify_chain(events), data), media_type='application/pdf',
                    headers={'Content-Disposition': 'attachment; filename="bytecode-audit-report.pdf"'})
