import pytest
from sqlalchemy import select
from app.models import Bid, Document, ProcessingRun, SourceVerification, AuditEvent
from app.repositories.review_repository import review
from app.adapters.government.gst import MockGSTAdapter
from app.services.sample_service import make_sample
from app.core.config import settings


@pytest.mark.parametrize('scenario,expected', [('CLEAN','LOW'),('MULTI_RISK','HIGH'),('BLACKLIST','CRITICAL'),('NAME_VARIATION','LOW')])
def test_scenarios_complete_through_real_http_service(db,scenario,expected):
    bid=db.scalar(select(Bid).where(Bid.scenario==scenario))
    result=review(db,bid)
    assert result['run']['status']=='COMPLETED',result['run'].get('error')
    assert result['risk_level']==expected
    assert len(result['verifications'])==11
    assert all(v['is_mock'] for v in result['verifications'])
    assert all(s['status']=='COMPLETED' for s in result['run']['stages'])
    if scenario=='MULTI_RISK':
        assert 65<=result['compliance_score']<=80
        assert result['risk_score']==58
        assert result['ai']['recommended_action']=='MANUAL REVIEW REQUIRED'
        assert len(result['risk']['contributing_factors'])==3
        assert len(result['ai']['evidence'])==8
    if scenario=='CLEAN':
        assert result['compliance_score']==100
        assert result['ai']['recommended_action']=='RECOMMEND COMPLIANT'


def test_real_adapter_mismatch_and_outage(db):
    bid=db.scalar(select(Bid).where(Bid.scenario=='MULTI_RISK'))
    result=MockGSTAdapter().verify(bid.bidder_id,'33ABCDA1000F1Z9','Zenith')
    assert result['status']=='MISMATCH' and result['record']['identifier']=='33ABCDA1000F1Z5'
    down=MockGSTAdapter().verify(bid.bidder_id,'33ABCDA1000F1Z9','Zenith',True)
    assert down['status']=='SOURCE_UNAVAILABLE' and down['confidence']==0


def test_unreachable_source_degrades_safely(monkeypatch):
    monkeypatch.setattr(settings,'mock_gov_api_url','http://127.0.0.1:1')
    result=MockGSTAdapter().verify('unknown','33ABCDE1234F1Z5','Test')
    assert result['status']=='SOURCE_UNAVAILABLE' and result['confidence']==0 and result['record']=={}


def test_login_and_role_enforcement(client):
    assert client.get('/api/tenders').status_code==200
    assert client.post('/api/auth/login',json={'email':'officer@bytecode.demo','password':'wrong'}).status_code==401
    token=client.post('/api/auth/login',json={'email':'auditor@bytecode.demo','password':'auditor123'}).json()['access_token']
    client.headers['Authorization']='Bearer '+token
    bid=client.get('/api/bids').json()[0]
    assert client.post('/api/bids/'+bid['id']+'/process',json={}).status_code==403
    assert client.post('/api/bids/'+bid['id']+'/decision',json={'run_id':bid['current_run_id'],'decision':'QUALIFIED','reason':'Evidence reviewed'}).status_code==403
    assert client.get('/api/audit').status_code==200


def test_officer_decision_override_and_audit_export(client):
    bid=next(b for b in client.get('/api/bids').json() if b['scenario']=='MULTI_RISK')
    endpoint='/api/bids/'+bid['id']+'/decision'
    assert client.post(endpoint,json={'run_id':bid['current_run_id'],'decision':'QUALIFIED','reason':'    '}).status_code==422
    assert client.post(endpoint,json={'run_id':'old-run','decision':'QUALIFIED','reason':'Manual review complete'}).status_code==409
    result=client.post(endpoint,json={'run_id':bid['current_run_id'],'decision':'QUALIFIED','reason':'Demo override: documentary evidence accepted after officer inspection.'})
    assert result.status_code==200
    assert result.json()['is_override'] is True
    refreshed=client.get('/api/bids/'+bid['id']).json()
    assert refreshed['final_decision']=='QUALIFIED'
    assert refreshed['ai']['recommended_action']=='MANUAL REVIEW REQUIRED'
    audit=client.get('/api/bids/'+bid['id']+'/audit').json()
    assert audit['integrity']['status']=='VERIFIED'
    assert {'OFFICER_OVERRIDDEN','FINAL_DECISION_RECORDED'} <= {e['action'] for e in audit['events']}
    pdf=client.get('/api/audit/export',params={'bid_id':bid['id']})
    assert pdf.status_code==200 and pdf.content.startswith(b'%PDF')
    import fitz
    with fitz.open(stream=pdf.content,filetype='pdf') as doc:
        text=''.join(p.get_text() for p in doc)
        assert 'QUALIFIED' in text and 'MOCK AUTHORISED SOURCE' in text and 'Current hash' in text


def test_upload_validation_and_genuine_processing(client):
    tender=client.get('/api/tenders').json()[0]
    result=client.post('/api/bids',json={'tender_id':tender['id'],'name':'Fictional Upload Test Ltd','pan':'ABCDE9999F','gstin':'33ABCDE9999F1Z5','address':'Demo address'})
    assert result.status_code==201
    bid_id=result.json()['id']
    assert client.post('/api/documents/upload',data={'bid_id':bid_id},files={'file':('unsafe.exe',b'MZbad')}).status_code==415
    assert client.post('/api/documents/upload',data={'bid_id':bid_id},files={'file':('fake.pdf',b'not a pdf')}).status_code==415
    pdf=make_sample('Fictional Upload Test Ltd','pan',{'PAN':'ABCDE9999F'})
    upload=client.post('/api/documents/upload',data={'bid_id':bid_id},files={'file':('../../PAN.pdf',pdf,'application/pdf')})
    assert upload.status_code==201 and upload.json()['filename']=='PAN.pdf'
    assert 'path' not in upload.json()
    assert client.get('/api/documents/'+upload.json()['id']+'/file').content==pdf
    process=client.post('/api/bids/'+bid_id+'/process',json={})
    assert process.status_code==202
    review=client.get('/api/bids/'+bid_id).json()
    assert review['run']['status']=='COMPLETED'
    assert any(e['type']=='PAN' and e['value']=='ABCDE9999F' for e in review['entities'])
    assert all(v['status']=='NOT_FOUND' for v in review['verifications'])
    assert review['compliance_score']<50


def test_rule_validation_and_admin_authorization(client):
    tender=client.get('/api/tenders').json()[0]
    detail=client.get('/api/tenders/'+tender['id']).json()
    body={'rules':detail['rules'],'scoring_weights':detail['scoring_weights']}
    endpoint='/api/tenders/'+tender['id']+'/rules'
    assert client.put(endpoint,json=body).status_code==403
    token=client.post('/api/auth/login',json={'email':'admin@bytecode.demo','password':'admin123'}).json()['access_token']
    client.headers['Authorization']='Bearer '+token
    assert client.put(endpoint,json=body).status_code==200
    body['scoring_weights']['Document completeness']=99
    assert client.put(endpoint,json=body).status_code==422
    body['scoring_weights']=detail['scoring_weights']
    body['rules'][0]['expression']={'op':'__import__'}
    assert client.put(endpoint,json=body).status_code==422


def test_new_upload_invalidates_decision_and_preserves_history(client):
    bid=next(b for b in client.get('/api/bids').json() if b['scenario']=='CLEAN')
    old_run=bid['current_run_id']
    decision=client.post('/api/bids/'+bid['id']+'/decision',json={'run_id':old_run,'decision':'QUALIFIED','reason':'Clean evidence reviewed in isolated test.'})
    assert decision.status_code==200
    pdf=make_sample(bid['bidder']['name'],'pan',{'PAN':bid['bidder']['pan']})
    uploaded=client.post('/api/documents/upload',data={'bid_id':bid['id']},files={'file':('additional-pan.pdf',pdf,'application/pdf')})
    assert uploaded.status_code==201
    current=client.get('/api/bids/'+bid['id']).json()
    assert current['current_run_id'] is None and current['final_decision'] is None
    assert current['decisions'][0]['run_id']==old_run
    assert client.post('/api/bids/'+bid['id']+'/decision',json={'run_id':old_run,'decision':'QUALIFIED','reason':'Attempt to use stale evidence'}).status_code==409


def test_volume_relative_document_storage(client):
    bid=client.get('/api/bids').json()[0]
    detail=client.get('/api/bids/'+bid['id']).json()
    doc=detail['documents'][0]
    assert client.get('/api/documents/'+doc['id']+'/file').content.startswith(b'%PDF')
    assert 'path' not in doc
