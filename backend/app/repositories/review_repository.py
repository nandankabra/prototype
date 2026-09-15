from sqlalchemy import select
from app.models import (Bid, Bidder, Tender, Document, ProcessingRun, SourceVerification,
                        ComplianceResult, RiskResult, AIRecommendation, ExtractedEntity, OfficerDecision)


def serialize(model, exclude=()):
    return {column.name: getattr(model, column.name) for column in model.__table__.columns if column.name not in exclude}


def bid_summary(db, bid):
    bidder, tender = db.get(Bidder, bid.bidder_id), db.get(Tender, bid.tender_id)
    risk = db.scalar(select(RiskResult).where(RiskResult.run_id == bid.current_run_id)) if bid.current_run_id else None
    return {**serialize(bid), 'bidder': serialize(bidder), 'tender': serialize(tender),
            'compliance_score': risk.result['compliance']['score'] if risk else None,
            'risk_level': risk.result['risk_level'] if risk else 'UNASSESSED',
            'risk_score': risk.result['risk_score'] if risk else None,
            'issues': len(risk.result['contributing_factors']) if risk else 0}


def review(db, bid):
    result = bid_summary(db, bid)
    result['documents'] = [serialize(d, ('path',)) for d in db.scalars(select(Document).where(Document.bid_id == bid.id))]
    result['run'] = serialize(db.get(ProcessingRun, bid.current_run_id)) if bid.current_run_id else None
    def rows(model):
        return list(db.scalars(select(model).where(model.run_id == bid.current_run_id))) if bid.current_run_id else []
    result['entities'] = [serialize(e) for e in rows(ExtractedEntity)]
    result['verifications'] = [serialize(v) for v in rows(SourceVerification)]
    result['compliance'] = sorted([r.result for r in rows(ComplianceResult)], key=lambda item: item['rule_code'])
    risk = rows(RiskResult)
    result['risk'] = risk[0].result if risk else None
    ai = rows(AIRecommendation)
    result['ai'] = {**ai[0].result, 'id': ai[0].id} if ai else None
    result['decisions'] = [serialize(d) for d in db.scalars(select(OfficerDecision).where(OfficerDecision.bid_id == bid.id).order_by(OfficerDecision.created_at.desc()))]
    return result
