from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.security import current_user, officer, admin
from app.models import Tender, TenderRule, TenderDocument, TenderRequirement, TenderVersion, Bid, uid, now
from app.schemas import TenderRequest, RulesUpdate, GeMTenderImportRequest
from app.engines.scoring_engine import DEFAULT_WEIGHTS
from app.repositories.review_repository import serialize, bid_summary
from app.services.audit_service import append_event
from app.seed import RULES
from app.providers import GeMTenderProvider
from app.engines.tender_requirement_engine import TenderRequirementEngine
from app.ai.extraction import parse_document
from pathlib import Path
import re
import tempfile
from html.parser import HTMLParser

router = APIRouter(prefix='/api/tenders', tags=['tenders'])


def get_tender(db, tender_id):
    tender = db.get(Tender, tender_id)
    if not tender:
        raise HTTPException(404, 'Tender not found')
    return tender


@router.get('')
def tenders(query: str = '', category: str = '', tender_type: str = '', db: Session = Depends(get_db), user=Depends(current_user)):
    results = []
    statement = select(Tender).where(Tender.source == 'GEM').order_by(Tender.deadline)
    for tender in db.scalars(statement):
        searchable = ' '.join(filter(None, [tender.reference, tender.external_bid_id, tender.title, tender.department, tender.ministry, tender.category])).lower()
        if query and query.lower() not in searchable:
            continue
        if category and (tender.category or '').lower() != category.lower():
            continue
        if tender_type and (tender.bid_type or '').lower() != tender_type.lower():
            continue
        bids = [bid_summary(db, b) for b in db.scalars(select(Bid).where(Bid.tender_id == tender.id))]
        scores = [b['compliance_score'] for b in bids if b['compliance_score'] is not None]
        levels = ['UNASSESSED', 'LOW', 'MEDIUM', 'HIGH', 'CRITICAL']
        results.append({**serialize(tender), 'bidder_count': len(bids), 'pending': sum(not b['final_decision'] for b in bids),
                        'average_compliance': round(sum(scores)/len(scores), 1) if scores else None,
                        'highest_risk': max((b['risk_level'] for b in bids), key=levels.index, default='UNASSESSED'),
                        'review_status': 'COMPLETED' if bids and all(b['final_decision'] for b in bids) else 'IN REVIEW',
                        'requirement_count': len(list(db.scalars(select(TenderRequirement).where(TenderRequirement.tender_id == tender.id))) )})
    return results


@router.post('', status_code=201)
def create_tender(body: TenderRequest, db: Session = Depends(get_db), user=Depends(officer)):
    if db.scalar(select(Tender).where(Tender.reference == body.reference)):
        raise HTTPException(409, 'Tender reference already exists')
    tender = Tender(id=uid(), **body.model_dump(), source='MANUAL_DRAFT', status='DRAFT', scoring_weights=DEFAULT_WEIGHTS)
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


def _metadata(pages, external_bid_id):
    text = '\n'.join(page.get('text', '') for page in pages)
    def labelled(labels):
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        for index, line in enumerate(lines):
            if any(label.lower() in line.lower() for label in labels):
                value = re.split(r'[:：]', line, maxsplit=1)
                if len(value) == 2 and value[1].strip():
                    return value[1].strip()[:255]
                if index + 1 < len(lines):
                    return lines[index + 1][:255]
        return None
    # Standard GeM bid PDFs frequently identify the procurement only through
    # their Item Category rather than a separate "Bid Title" field.
    title = labelled(['Bid Title', 'Tender Title', 'Global Tender Title']) or labelled(['Item Category', 'Items'])
    deadline = labelled(['Bid End Date/Time', 'Bid End Date'])
    if not title or not deadline:
        raise HTTPException(422, 'The official tender document must expose a tender title and bid closing date before import.')
    # GeM dates are retained as source text when the format cannot be safely normalized.
    return {'reference': external_bid_id, 'title': title, 'deadline': deadline, 'department': labelled(['Department Name']) or 'Not stated in source',
            'ministry': labelled(['Ministry/State Name']), 'organisation': labelled(['Organisation Name']), 'buyer': labelled(['Office Name']),
            'category': labelled(['Item Category']), 'bid_type': 'GLOBAL' if 'global tender' in text.lower() else 'GEM_BID', 'raw_text': text}


class _GeMPageText(HTMLParser):
    """Preserves public bid-page table cells as separate text lines for evidence extraction."""
    block_tags = {'tr', 'td', 'th', 'p', 'div', 'br', 'li', 'h1', 'h2', 'h3'}

    def __init__(self):
        super().__init__()
        self.parts: list[str] = []

    def handle_data(self, data: str):
        cleaned = ' '.join(data.split())
        if cleaned:
            self.parts.append(cleaned)

    def handle_endtag(self, tag: str):
        if tag.lower() in self.block_tags:
            self.parts.append('\n')

    def text(self) -> str:
        return ''.join(self.parts)


def _parse_imported_document(content: bytes, content_type: str):
    if 'html' in content_type.lower():
        parser = _GeMPageText()
        parser.feed(content.decode('utf-8', errors='replace'))
        return {'pages': [{'page_number': 1, 'text': parser.text(), 'provider': 'PUBLIC_GEM_PAGE', 'confidence': 1.0}], 'warnings': []}
    with tempfile.NamedTemporaryFile(suffix='.pdf') as handle:
        handle.write(content); handle.flush()
        return parse_document(handle.name)


def _store_gem_tender(external_bid_id: str, source_url: str | None, content: bytes, content_type: str, db: Session, user):
    existing = db.scalar(select(Tender).where(Tender.external_bid_id == external_bid_id, Tender.source == 'GEM'))
    if existing:
        raise HTTPException(409, 'This GeM bid is already imported. Use its existing tender record.')
    parsed = _parse_imported_document(content, content_type)
    metadata = _metadata(parsed['pages'], external_bid_id)
    digest = GeMTenderProvider.digest(content)
    tender = Tender(id=uid(), reference=metadata['reference'], external_bid_id=external_bid_id, source='GEM', source_url=source_url,
                    title=metadata['title'], department=metadata['department'], deadline=metadata['deadline'], description=metadata['raw_text'][:8000],
                    ministry=metadata['ministry'], organisation=metadata['organisation'], buyer=metadata['buyer'], category=metadata['category'], bid_type=metadata['bid_type'],
                    required_documents=[], local_content_threshold=0, scoring_weights=DEFAULT_WEIGHTS, status='IMPORTED', last_synced_at=now(), raw_metadata={'parser_warnings': parsed['warnings']}, content_hash=digest)
    db.add(tender); db.flush()
    document = TenderDocument(id=uid(), tender_id=tender.id, url=source_url or 'uploaded://authorised-gem-document', sha256=digest, extracted_text=metadata['raw_text'], pages=parsed['pages'], fetch_status='IMPORTED')
    db.add(document); db.flush()
    requirements = TenderRequirementEngine().extract(parsed['pages'])
    for value in requirements:
        requirement = TenderRequirement(id=uid(), tender_id=tender.id, source_document_id=document.id, **value)
        db.add(requirement)
    tender.required_documents = sorted({kind.lower() for value in requirements for kind in value['accepted_evidence']})
    db.add(TenderVersion(id=uid(), tender_id=tender.id, version_number=1, content_hash=digest, snapshot_metadata={'source_url': source_url, 'intake_method': 'PUBLIC_URL' if source_url else 'AUTHORISED_UPLOAD'}, change_summary={'imported': True}))
    append_event(db, action='GEM_TENDER_IMPORTED', object_id=tender.id, object_type='tender', actor=user.email, role=user.role,
                 metadata={'external_bid_id': external_bid_id, 'source_url': source_url, 'content_hash': digest, 'requirements': len(requirements)})
    return {**serialize(tender), 'requirements': [serialize(r) for r in db.scalars(select(TenderRequirement).where(TenderRequirement.tender_id == tender.id))]}


@router.post('/import/gem', status_code=201)
def import_gem_tender(body: GeMTenderImportRequest, db: Session = Depends(get_db), user=Depends(officer)):
    try:
        imported = GeMTenderProvider().import_public_document(body.official_document_url)
    except ValueError as exc:
        raise HTTPException(422, str(exc))
    return _store_gem_tender(body.external_bid_id, body.official_document_url, imported.content, imported.content_type, db, user)


@router.post('/import/gem/upload', status_code=201)
def import_uploaded_gem_tender(
    external_bid_id: str = Form(...),
    document: UploadFile = File(...),
    db: Session = Depends(get_db),
    user=Depends(officer),
):
    content = document.file.read()
    if not content.startswith(b'%PDF'):
        raise HTTPException(422, 'Upload the official GeM bid document as a PDF file.')
    if len(content) > 25 * 1024 * 1024:
        raise HTTPException(422, 'Tender document exceeds the 25 MB intake limit.')
    return _store_gem_tender(external_bid_id.strip(), None, content, 'application/pdf', db, user)


@router.get('/{tender_id}')
def detail(tender_id: str, db: Session = Depends(get_db), user=Depends(current_user)):
    tender = get_tender(db, tender_id)
    return {**serialize(tender), 'bids': [bid_summary(db, b) for b in db.scalars(select(Bid).where(Bid.tender_id == tender_id))],
            'rules': [serialize(r) for r in db.scalars(select(TenderRule).where(TenderRule.tender_id == tender_id).order_by(TenderRule.rule_id))],
            'requirements': [serialize(r) for r in db.scalars(select(TenderRequirement).where(TenderRequirement.tender_id == tender_id).order_by(TenderRequirement.requirement_code))],
            'tender_documents': [serialize(d) for d in db.scalars(select(TenderDocument).where(TenderDocument.tender_id == tender_id))]}


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
