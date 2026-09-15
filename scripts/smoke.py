"""Exercise the running Docker stack with fictional seeded records.

This intentionally creates new review runs and a NEEDS CLARIFICATION officer
record for Zenith. It never deletes data or resets uploaded files.
"""
import argparse
import json
from pathlib import Path
import time
import httpx

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--base-url', default='http://127.0.0.1:8000')
parser.add_argument('--output', default='output/pdf/zenith-audit-report.pdf')
args = parser.parse_args()

with httpx.Client(base_url=args.base_url, timeout=30) as client:
    for route in ['/health', '/docs', '/redoc', '/openapi.json']:
        response = client.get(route)
        response.raise_for_status()
    response = client.post('/api/auth/login', json={'email':'officer@bytecode.demo','password':'officer123'})
    response.raise_for_status()
    client.headers['Authorization'] = 'Bearer '+response.json()['access_token']
    tenders = client.get('/api/tenders').json()
    bids = client.get('/api/bids').json()
    assert len(tenders) >= 5 and len(bids) >= 15
    results = []
    for bid in bids:
        if bid['scenario'] == 'CUSTOM':
            continue
        started = time.monotonic()
        response = client.post('/api/bids/'+bid['id']+'/process', json={})
        response.raise_for_status()
        run_id = response.json()['id']
        while time.monotonic()-started < 60:
            status = client.get('/api/bids/'+bid['id']+'/status').json()['run']
            if status['id'] == run_id and status['status'] in {'COMPLETED','FAILED'}:
                break
            time.sleep(.2)
        assert status['status'] == 'COMPLETED', status
        data = client.get('/api/bids/'+bid['id']).json()
        assert len(data['verifications']) == 11
        assert all(v['is_mock'] for v in data['verifications'])
        original = client.get('/api/documents/'+data['documents'][0]['id']+'/file')
        assert original.status_code == 200 and original.content.startswith(b'%PDF')
        result = {'scenario':bid['scenario'],'bidder':bid['bidder']['name'],'score':data['compliance_score'],
                  'risk':data['risk_level'],'risk_score':data['risk_score'],'seconds':round(time.monotonic()-started,2),
                  'retrieval':data['ai']['reasoning_sources']['vector_provider']}
        results.append(result)
        print(json.dumps(result), flush=True)
        if bid['scenario'] == 'MULTI_RISK':
            assert 65 <= data['compliance_score'] <= 80 and data['risk_level'] == 'HIGH'
            assert data['ai']['recommended_action'] == 'MANUAL REVIEW REQUIRED'
            zenith = data
        if bid['scenario'] in {'CLEAN','NAME_VARIATION'}:
            assert data['compliance_score'] == 100 and data['risk_level'] == 'LOW'
    decision = client.post('/api/bids/'+zenith['id']+'/decision',json={'run_id':zenith['current_run_id'],
        'decision':'NEEDS CLARIFICATION','reason':'Demo review: provide a corrected GST certificate, a current experience certificate, and valid OEM authorization.',
        'comments':'Fictional judge walkthrough. Officer decision recorded independently of the AI recommendation.'})
    decision.raise_for_status()
    audit = client.get('/api/bids/'+zenith['id']+'/audit').json()
    assert audit['integrity']['status'] == 'VERIFIED'
    pdf = client.get('/api/audit/export',params={'bid_id':zenith['id']})
    pdf.raise_for_status()
    output = Path(args.output); output.parent.mkdir(parents=True,exist_ok=True); output.write_bytes(pdf.content)
    summary = client.get('/api/dashboard/summary').json()
    system = client.get('/api/system').json()
    print(json.dumps({'database':system['database'],'bids':summary['total_bids'],'documents':summary['total_documents'],
                      'integrity':audit['integrity']['status'],'officer_decision':decision.json()['decision'],
                      'report':str(output)}), flush=True)
    Path('output/smoke-results.json').write_text(json.dumps(results,indent=2))
