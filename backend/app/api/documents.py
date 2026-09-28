from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.security import current_user, bidder
from app.core.config import settings
from app.models import Document, ExtractedEntity
from app.api.bids import get_bid
from app.services.document_service import save_upload, document_path
from app.services.audit_service import append_event
from app.repositories.review_repository import serialize

router = APIRouter(prefix='/api/documents', tags=['documents'])


@router.post('/upload', status_code=201)
async def upload(bid_id: str = Form(...), file: UploadFile = File(...), db: Session = Depends(get_db), user=Depends(bidder)):
    bid = get_bid(db, bid_id, lock=True, user=user)
    if bid.status == 'PROCESSING':
        raise HTTPException(409, 'Wait for the current review to finish before uploading')
    contents = await file.read(settings.upload_max_mb * 1024 * 1024 + 1)
    document = save_upload(db, bid_id, file.filename or 'document', contents)
    previous = {'status': bid.status, 'decision': bid.final_decision}
    bid.status = 'READY_FOR_REVIEW'
    bid.final_decision = None
    # Clear current result: previous run and its decision remain queryable in history.
    bid.current_run_id = None
    append_event(db, action='DOCUMENT_UPLOADED', object_id=document.id, object_type='document', bid_id=bid_id,
                 actor=user.email, role=user.role, previous_state=previous,
                 metadata={'filename': document.filename, 'sha256': document.sha256, 'requires_new_review': True})
    return serialize(document, ('path',))


@router.post('/attach-samples/{bid_id}', status_code=201)
def attach_samples(bid_id: str, db: Session = Depends(get_db), user=Depends(bidder)):
    from app.models import Bidder
    from app.services.sample_service import make_sample
    bid = get_bid(db, bid_id, lock=True, user=user)
    if bid.status == 'PROCESSING':
        raise HTTPException(409, 'Wait for the current review to finish before uploading')
    bidder_obj = db.get(Bidder, bid.bidder_id)
    name = bidder_obj.name if bidder_obj else 'Sample Bidder Pvt Ltd'
    pan = bidder_obj.pan if bidder_obj and bidder_obj.pan else 'ABCDE1234F'
    gstin = bidder_obj.gstin if bidder_obj and bidder_obj.gstin else '33ABCDE1234F1Z5'
    udyam = bidder_obj.udyam if bidder_obj and bidder_obj.udyam else 'UDYAM-TN-02-1234567'

    samples = [
        ('pan.pdf', 'pan', {'PAN': pan, 'Valid Until': '2030-12-31'}),
        ('gst_certificate.pdf', 'gst_certificate', {'GSTIN': gstin, 'Status': 'ACTIVE', 'Tax Period': '2025-2026'}),
        ('udyam.pdf', 'udyam', {'Udyam Registration Number': udyam, 'Enterprise Type': 'Small'}),
        ('oem_authorization.pdf', 'oem_authorization', {'Authorization Code': 'OEM-AUTH-2026-99', 'Valid Until': '2027-03-31'}),
        ('experience_certificate.pdf', 'experience_certificate', {'Project Reference': 'EXP-2024-887', 'Completion Date': '2024-05-15', 'Value': 'INR 45,00,000'}),
        ('tax_compliance.pdf', 'tax_compliance', {'Assessment Year': '2025-2026', 'Filing Status': 'Compliant', 'Local Content': '65%'})
    ]
    added = []
    for filename, kind, fields in samples:
        content = make_sample(name, kind, fields)
        doc = save_upload(db, bid_id, filename, content)
        added.append(serialize(doc, ('path',)))

    previous = {'status': bid.status, 'decision': bid.final_decision}
    bid.status = 'READY_FOR_REVIEW'
    bid.final_decision = None
    bid.current_run_id = None
    append_event(db, action='SAMPLE_DOCUMENTS_ATTACHED', object_id=bid.id, object_type='bid', bid_id=bid_id,
                 actor=user.email, role=user.role, previous_state=previous,
                 metadata={'count': len(added), 'requires_new_review': True})
    return {'status': 'attached', 'documents': added}


@router.get('/{document_id}')
def document(document_id: str, db: Session = Depends(get_db), user=Depends(current_user)):
    doc = db.get(Document, document_id)
    if not doc:
        raise HTTPException(404, 'Document not found')
    bid = get_bid(db, doc.bid_id, user=user)
    return {**serialize(doc, ('path',)), 'entities': [serialize(e) for e in db.scalars(select(ExtractedEntity).where(
        ExtractedEntity.document_id == doc.id, ExtractedEntity.run_id == bid.current_run_id))]}


@router.get('/{document_id}/file')
def original(document_id: str, db: Session = Depends(get_db), user=Depends(current_user)):
    from pathlib import Path
    doc = db.get(Document, document_id)
    if not doc or not document_path(doc).is_file():
        raise HTTPException(404, 'Original document not available')
    get_bid(db, doc.bid_id, user=user)
    return FileResponse(document_path(doc), media_type=doc.mime_type, filename=doc.filename, content_disposition_type='inline')
