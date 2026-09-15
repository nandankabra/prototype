"""Idempotent deterministic demo seeding. Existing reviews and decisions are preserved."""
from sqlalchemy import select
from app.core.database import SessionLocal
from app.core.security import hash_password
from app.demo_data import NAMES, SCENARIOS, TENDER_TITLES, stable_id, bidder_record
from app.models import User, Tender, TenderRule, Bidder, Bid
from app.engines.scoring_engine import DEFAULT_WEIGHTS
from app.services.sample_service import make_sample
from app.services.document_service import save_upload
from app.services.audit_service import append_event

RULES = [
 ('R01', 'GST registration must be active and match', 'source', {'op': 'source_status', 'source': 'GST'}, 'HIGH'),
 ('R02', 'PAN must match the bidder identity', 'identity', {'op': 'source_status', 'source': 'PAN'}, 'HIGH'),
 ('R03', 'Udyam registration must be verified', 'source', {'op': 'source_status', 'source': 'UDYAM'}, 'MEDIUM'),
 ('R04', 'Bidder must be clear of debarment', 'eligibility', {'op': 'source_status', 'source': 'BLACKLIST'}, 'CRITICAL'),
 ('R05', 'OEM authorization must be submitted', 'documents', {'op': 'document_present', 'document': 'oem_authorization'}, 'HIGH'),
 ('R06', 'Experience certificate must be submitted', 'documents', {'op': 'document_present', 'document': 'experience_certificate'}, 'HIGH'),
 ('R07', 'Required certificates must be valid at submission', 'validity', {'op': 'valid_documents'}, 'HIGH'),
 ('R08', 'Declared local content must meet the tender threshold', 'eligibility', {'op': 'minimum_field', 'field': 'local_content', 'value': 50}, 'MEDIUM')]


def seed():
    with SessionLocal() as db:
        if not db.scalar(select(User).limit(1)):
            for email, name, role, password in [('officer@bytecode.demo', 'Priya Raman', 'PROCUREMENT_OFFICER', 'officer123'),
                                                ('auditor@bytecode.demo', 'Arjun Menon', 'AUDITOR', 'auditor123'),
                                                ('admin@bytecode.demo', 'Demo Administrator', 'ADMIN', 'admin123')]:
                db.add(User(email=email, name=name, role=role, password_hash=hash_password(password)))
            db.commit()
        for i, title in enumerate(TENDER_TITLES):
            tender_id = stable_id(f'tender-{i}')
            if db.get(Tender, tender_id):
                continue
            db.add(Tender(id=tender_id, reference=f'CPCL/2026/PROC/{i+1:03}', title=title,
                          department='Chennai Petroleum Corporation Limited', deadline='2026-09-30T17:00:00+05:30',
                          description='Fictional procurement tender for the CPCL demo. Review bidder eligibility, documentary evidence, and mandatory compliance requirements.',
                          required_documents=['pan', 'gst_certificate', 'udyam', 'oem_authorization', 'experience_certificate', 'tax_compliance'],
                          local_content_threshold=50, scoring_weights=DEFAULT_WEIGHTS))
            db.flush()
            for code, name, category, expression, severity in RULES:
                db.add(TenderRule(tender_id=tender_id, rule_id=code, name=name, category=category,
                                  expression=expression, severity=severity))
            db.commit()
        for i, name in enumerate(NAMES):
            bid_id = stable_id(f'bid-{i}')
            if db.get(Bid, bid_id):
                continue
            bidder_id, sources = bidder_record(i)
            bidder = Bidder(id=bidder_id, name=name, pan=sources['PAN']['identifier'], gstin=sources['GST']['identifier'],
                            udyam=sources['UDYAM']['identifier'], address=f'{120+i}, Demo Industrial Estate, Chennai, Tamil Nadu - 600032',
                            profile={'is_fictional': True, 'registration_date': '2018-04-12', 'local_content': 62})
            db.add(bidder)
            db.flush()
            tender_index = 0 if i < 7 else 1+(i-7)//2
            bid = Bid(id=bid_id, bidder_id=bidder_id, tender_id=stable_id(f'tender-{tender_index}'), scenario=SCENARIOS[i], status='READY_FOR_REVIEW')
            db.add(bid)
            db.commit()
            append_event(db, action='BID_CREATED', bid_id=bid_id, object_id=bid_id,
                         metadata={'bidder_name': name, 'scenario': SCENARIOS[i], 'fictional': True})
            kinds = ['pan', 'gst_certificate', 'udyam', 'oem_authorization', 'experience_certificate', 'tax_compliance']
            if i == 0:
                kinds += ['incorporation', 'bank_certificate']
            if SCENARIOS[i] in {'MULTI_RISK', 'MISSING_OEM'}:
                kinds.remove('oem_authorization')
            for kind in kinds:
                fields = {'Address': bidder.address, 'Registration Date': '2018-04-12', 'Certificate Number': f'DEMO-{i:03}-{kind[:3].upper()}'}
                if kind == 'pan':
                    fields['PAN'] = bidder.pan
                elif kind == 'gst_certificate':
                    fields['GSTIN'] = bidder.gstin[:-1]+'9' if SCENARIOS[i] in {'GST_MISMATCH', 'MULTI_RISK'} else bidder.gstin
                elif kind == 'udyam':
                    fields['Udyam Number'] = bidder.udyam
                elif kind == 'oem_authorization':
                    fields.update({'OEM ID': sources['OEM']['identifier'], 'Valid Until': '2028-12-31'})
                elif kind == 'experience_certificate':
                    fields.update({'Valid Until': '2025-12-31' if SCENARIOS[i] in {'EXPIRED_DOCUMENT', 'MULTI_RISK'} else '2028-12-31',
                                   'Project': 'Fictional industrial safety equipment supply'})
                elif kind == 'incorporation':
                    fields['CIN'] = f'U12345TN2018PTC{100000+i}'
                elif kind == 'tax_compliance':
                    fields.update({'PAN': bidder.pan, 'Local Content': '62%', 'Annual Turnover': '25000000',
                                   'EPFO': sources['EPFO']['identifier'], 'ESIC': sources['ESIC']['identifier'],
                                   'Startup ID': sources['STARTUP_INDIA']['identifier'], 'NSIC': sources['NSIC']['identifier'],
                                   'DigiLocker': sources['DIGILOCKER']['identifier']})
                document = save_upload(db, bid_id, kind+'.pdf', make_sample(name, kind, fields), is_seed=True)
                append_event(db, action='DOCUMENT_UPLOADED', object_type='document', object_id=document.id,
                             bid_id=bid_id, metadata={'filename': document.filename, 'sha256': document.sha256, 'fictional': True})
        return {'status': 'seeded', 'tenders': 5, 'bidders': 15}


if __name__ == '__main__':
    print(seed())
