from types import SimpleNamespace
import copy
import pytest
from app.ai.extraction import RegexEntityExtractor, valid_pan, valid_gstin, parse_document
from app.ai.classification import DemoDocumentClassifier
from app.engines.entity_matching_engine import match_name
from app.engines.rule_engine import RuleEvaluator
from app.engines.scoring_engine import calculate_score, DEFAULT_WEIGHTS
from app.engines.anomaly_engine import IsolationForestDetector
from app.services.audit_service import verify_chain, digest
from app.models import AuditEvent
from sqlalchemy import select


def test_structured_identifiers_are_extracted_with_provenance():
    page={'page_number':2,'text':'GSTIN: 33ABCDE1234F1Z5\nPAN: ABCDE1234F\nUdyam: UDYAM-TN-02-1234567\nCompany Name: Test Industries Pvt Ltd\nValid Until: 2025-12-31','confidence':.96,'blocks':[]}
    values=RegexEntityExtractor().extract([page])
    assert {'PAN','GSTIN','UDYAM','company_name','expiry_date'} <= {e['type'] for e in values}
    assert all(e['source_page']==2 and e['source_text'] and e['confidence']==.96 for e in values)
    assert next(e for e in values if e['type']=='GSTIN')['normalized_value']=='33ABCDE1234F1Z5'


@pytest.mark.parametrize('value,valid',[('ABCDE1234F',True),('abc',False),('ABCDE12345',False)])
def test_pan_structure(value,valid):
    assert valid_pan(value) is valid


@pytest.mark.parametrize('value,valid',[('33ABCDE1234F1Z5',True),('99ABCDE1234F1Z5',False),('33ABCDE1234F',False)])
def test_gstin_structure(value,valid):
    assert valid_gstin(value) is valid


def test_name_variation_and_thresholds():
    matched=match_name('ABC Industrial Solutions Pvt Ltd','ABC Industrial Solutions Private Limited')
    assert matched['status']=='MATCH' and matched['similarity']==1
    assert match_name('ABC Industrial Solution Private Limited','ABC Industrial Solutions Private Limited')['status']=='MATCH'
    assert match_name('Completely Different Supplier','ABC Industrial Solutions Private Limited')['status']=='MISMATCH'
    assert match_name('ABC Industrial Solution Services','ABC Industrial Solutions Private Limited')['status'] in {'REVIEW','MISMATCH'}


def test_classification_uses_text_not_filename():
    assert DemoDocumentClassifier().classify('GST Registration Certificate\nGSTIN: ABC')['type']=='gst_certificate'
    assert DemoDocumentClassifier().classify('Unrelated document')['type']=='miscellaneous'


def test_declarative_rule_does_not_treat_unavailable_as_verified():
    rule=SimpleNamespace(id='rule',rule_id='R01',name='GST verified',category='source',severity='HIGH',required=True,expression={'op':'source_status','source':'GST'})
    verification=SimpleNamespace(id='v',entity_id='e',source='GST',status='SOURCE_UNAVAILABLE',identifier='33ABCDE1234F1Z5',evidence={})
    result=RuleEvaluator().evaluate(rule,documents=[],entities=[],verifications=[verification],deadline='2026-09-30')
    assert result['status']=='FAIL' and result['evidence'][0]['verification_id']=='v'


def test_empty_submission_never_scores_as_complete():
    result=calculate_score(required=['pan'],documents=[],verifications=[],rules=[],expired_ids=set(),identity_checks=[],signals=[],weights=DEFAULT_WEIGHTS)
    assert result['score']==5  # Only the no-anomaly component, never document/identity/source credit.
    assert next(p for p in result['breakdown'] if p['component']=='Document completeness')['earned']==0


def test_score_is_sum_of_visible_contributions():
    result=calculate_score(required=['pan'],documents=[SimpleNamespace(classification='pan',raw_text='PAN')],
        verifications=[SimpleNamespace(source='PAN',status='VERIFIED')],rules=[{'status':'PASS','rule_code':'R02','name':'PAN'}],
        expired_ids=set(),identity_checks=[{'label':'PAN','status':'MATCH'}],signals=[],weights=DEFAULT_WEIGHTS)
    assert result['score']==100
    assert sum(p['earned'] for p in result['breakdown'])==100


def test_isolation_forest_returns_explainable_features():
    result=IsolationForestDetector().detect({'number_of_mismatches':2,'number_of_expired_docs':1,'missing_mandatory_documents':1,
        'identifier_similarity':.7,'duplicate_documents':0,'unusual_document_age':8,'source_conflicts':1})
    assert result['detector']=='IsolationForestDetector'
    assert result['anomaly_score'] is not None and len(result['features'])==7
    assert 'synthetic' in result['explanation']


def test_hash_chain_detects_payload_and_metadata_tampering(db):
    events=list(db.scalars(select(AuditEvent).order_by(AuditEvent.sequence)))
    assert verify_chain(events)['status']=='VERIFIED'
    last=events[-1]
    original=last.payload
    last.payload += 'tampered'
    try:
        # Invalid JSON is itself evidence of tampering; verifier must handle it safely.
        assert verify_chain(events)['status']=='FAILED'
    finally:
        last.payload=original
    old=last.actor
    last.actor='tampered-reviewer'
    assert verify_chain(events)['status']=='FAILED'
    last.actor=old
    db.rollback()


def test_malformed_pdf_returns_manual_review(tmp_path):
    file=tmp_path/'broken.pdf';file.write_bytes(b'%PDF-1.7 broken contents')
    result=parse_document(str(file))
    assert result['raw_text']=='' and result['warnings'] and result['ocr_confidence']==0


@pytest.mark.parametrize('similarity,status',[(.95,'MATCH'),(.949,'REVIEW'),(.8,'REVIEW'),(.799,'MISMATCH')])
def test_similarity_threshold_boundaries(similarity,status):
    from app.engines.entity_matching_engine import classify_similarity
    assert classify_similarity(similarity)==status


def test_scanned_pdf_uses_real_ocr(tmp_path):
    import shutil
    import pymupdf as fitz
    if not shutil.which('tesseract'):
        pytest.skip('Tesseract binary not installed; included in Docker image')
    from app.services.sample_service import make_sample
    source=fitz.open(stream=make_sample('Scanned Demo Industries','pan',{'PAN':'ABCDE1234F'}),filetype='pdf')
    pix=source[0].get_pixmap(matrix=fitz.Matrix(2,2))
    scanned=fitz.open();page=scanned.new_page(width=source[0].rect.width,height=source[0].rect.height)
    page.insert_image(page.rect,stream=pix.tobytes('png'))
    path=tmp_path/'scanned.pdf';scanned.save(path)
    source.close();scanned.close()
    result=parse_document(str(path))
    assert 'Tesseract' in result['providers']
    assert 'ABCDE1234F' in result['raw_text']
    assert any(e['type']=='PAN' for e in RegexEntityExtractor().extract(result['pages']))


def test_external_llm_failure_keeps_grounded_summary(monkeypatch):
    from app.ai.llm import OptionalOpenAIProvider
    from app.core.config import settings
    monkeypatch.setattr(settings,'llm_base_url','http://127.0.0.1:1')
    result=OptionalOpenAIProvider().generate({'bidder_name':'Fictional Bidder','rules':[],
        'risk':{'risk_level':'LOW','contributing_factors':[]},'score':{'score':0},'verifications':[],'retrieval':{}})
    assert result['fallback_reason']
    assert 'Fictional Bidder' in result['summary']
    assert result['advisory_only'] is True
