"""Observable, persisted local job pipeline. Every displayed stage reflects actual work."""
from concurrent.futures import ThreadPoolExecutor
from datetime import date
import logging
import json
from pathlib import Path
from sqlalchemy import select
from app.core.database import SessionLocal
from app.core.config import settings
from app.models import (Bid, Bidder, Tender, TenderRule, Document, ProcessingRun, ExtractedEntity,
                        SourceVerification, ComplianceResult, RiskResult, AIRecommendation, uid, now)
from app.ai.extraction import RegexEntityExtractor, parse_document
from app.ai.classification import DemoDocumentClassifier
from app.ai.rag import PolicyRetriever
from app.ai.llm import MockLLMProvider, OptionalOpenAIProvider
from app.adapters.government import ADAPTERS
from app.engines.rule_engine import RuleEvaluator
from app.engines.scoring_engine import calculate_score
from app.engines.anomaly_engine import RuleBasedAnomalyDetector, IsolationForestDetector
from app.engines.entity_matching_engine import match_name
from app.services.audit_service import append_event
from app.services.document_service import document_path

STAGES = ['Uploaded', 'PDF Parsed', 'OCR Processing', 'Entity Extraction', 'Document Classification',
          'Cross Verification', 'Compliance Evaluation', 'Risk Analysis', 'AI Explanation', 'Completed']


def queue_run(db, bid, actor, role):
    run = ProcessingRun(id=uid(), bid_id=bid.id, actor=actor, role=role,
                        stages=[{'name': name, 'status': 'PENDING'} for name in STAGES])
    db.add(run)
    bid.current_run_id = run.id
    bid.status = 'PROCESSING'
    bid.final_decision = None
    db.commit()
    return run


def process_bid(run_id: str, unavailable_sources=None):
    """Each completed stage commits evidence and timestamps; failures remain inspectable."""
    with SessionLocal() as db:
        run = db.get(ProcessingRun, run_id)
        if not run or run.status not in {'QUEUED', 'RUNNING'}:
            return
        bid = db.get(Bid, run.bid_id)
        bidder, tender = db.get(Bidder, bid.bidder_id), db.get(Tender, bid.tender_id)
        documents = list(db.scalars(select(Document).where(Document.bid_id == bid.id).order_by(Document.created_at)))
        def audit(action, metadata, object_id=None, object_type='bid'):
            append_event(db, action=action, object_id=object_id or bid.id, object_type=object_type, bid_id=bid.id,
                         actor=run.actor, role=run.role, metadata={'correlation_id': run.id, **metadata})
            logging.info(json.dumps({'action': action, 'correlation_id': run.id, 'bid_id': bid.id}))
        def stage(index, status, detail=''):
            values = [dict(item) for item in run.stages]
            values[index].update(status=status, detail=detail)
            values[index]['started_at' if status == 'RUNNING' else 'completed_at'] = now().isoformat()
            run.stages = values
            db.commit()
        try:
            run.status = 'RUNNING'
            stage(0, 'RUNNING')
            stage(0, 'COMPLETED', f'{len(documents)} stored documents')
            audit('BID_PROCESSING_STARTED', {'documents': len(documents)})
            stage(1, 'RUNNING')
            from app.ai.extraction import inspect_document
            for doc in documents:
                doc.extraction = inspect_document(str(document_path(doc)))
            db.commit()
            stage(1, 'COMPLETED', 'PDF structures, page limits, text layers, and image dimensions inspected')
            stage(2, 'RUNNING')
            for doc in documents:
                parsed = parse_document(str(document_path(doc)))
                doc.raw_text = parsed['raw_text']
                doc.normalized_text = parsed['normalized_text']
                doc.pages = parsed['pages']
                doc.extraction = {key: value for key, value in parsed.items() if key not in {'raw_text', 'normalized_text', 'pages'}}
                audit('OCR_COMPLETED', {'document_id': doc.id, 'providers': parsed['providers'],
                                       'confidence': parsed['ocr_confidence'], 'warnings': parsed['warnings']}, doc.id, 'document')
            stage(2, 'COMPLETED', 'PDF text layers extracted; image pages use available OCR engines')
            stage(3, 'RUNNING')
            entities = []
            for doc in documents:
                for item in RegexEntityExtractor().extract(doc.pages):
                    entity = ExtractedEntity(id=uid(), run_id=run.id, document_id=doc.id, **item)
                    db.add(entity)
                    entities.append(entity)
                db.flush()
                audit('ENTITY_EXTRACTED', {'document_id': doc.id, 'entity_ids': [e.id for e in entities if e.document_id == doc.id]}, doc.id, 'document')
            stage(3, 'COMPLETED', f'{len(entities)} fields extracted with document and page references')
            stage(4, 'RUNNING')
            for doc in documents:
                classification = DemoDocumentClassifier().classify(doc.raw_text)
                doc.classification = classification['type']
                doc.extraction = {**doc.extraction, 'classification': classification}
            stage(4, 'COMPLETED', f'{len(documents)} documents classified from extracted text')
            stage(5, 'RUNNING')
            mapping = {'INCOME_TAX': 'PAN', 'BLACKLIST': 'PAN', 'GST': 'GSTIN'}
            def verify(adapter_cls):
                adapter = adapter_cls()
                field_type = mapping.get(adapter.source, adapter.source)
                candidates = [e for e in entities if e.type == field_type]
                entity = candidates[0] if candidates else None
                result = adapter.verify(bidder.id, entity.normalized_value if entity else '', bidder.name,
                                        adapter.source in (unavailable_sources or []))
                result['evidence']['input_provenance'] = 'extracted_document' if entity else 'missing_extracted_identifier'
                result['evidence']['document_id'] = entity.document_id if entity else None
                result['evidence']['source_page'] = entity.source_page if entity else None
                if entity:
                    result['confidence'] = min(result['confidence'], entity.confidence)
                    if entity.confidence < settings.review_threshold and result['status'] == 'VERIFIED':
                        result['status'] = 'MANUAL_REVIEW'
                        result['evidence']['reason'] = 'Source record matched, but extraction confidence requires officer review'
                elif result['status'] == 'VERIFIED':
                    result['status'] = 'MANUAL_REVIEW'
                    result['confidence'] = 0
                    result['evidence']['reason'] = 'No supporting extracted identifier; a source record alone is insufficient'
                if entity and len({e.normalized_value for e in candidates}) > 1:
                    result['status'] = 'MISMATCH'
                    result['evidence']['conflicting_values'] = [e.normalized_value for e in candidates]
                    result['evidence']['reason'] = 'Conflicting identifiers across uploaded documents; first source comparison retained'
                return entity, result
            with ThreadPoolExecutor(max_workers=6) as pool:
                checks = list(pool.map(verify, ADAPTERS))
            verifications = []
            for entity, result in checks:
                verification = SourceVerification(id=uid(), run_id=run.id, entity_id=entity.id if entity else None, **result)
                db.add(verification)
                verifications.append(verification)
                db.flush()
                audit('SOURCE_VERIFIED', {'verification_id': verification.id, 'entity_id': verification.entity_id,
                                          'source': verification.source, 'status': verification.status, 'is_mock': True}, verification.id, 'verification')
            stage(5, 'COMPLETED', f'{len(verifications)} HTTP source checks recorded')
            stage(6, 'RUNNING')
            rules = list(db.scalars(select(TenderRule).where(TenderRule.tender_id == tender.id, TenderRule.enabled.is_(True)).order_by(TenderRule.rule_id)))
            results = []
            for rule in rules:
                result = RuleEvaluator().evaluate(rule, documents=documents, entities=entities, verifications=verifications, deadline=tender.deadline)
                result_id = uid()
                result['result_id'] = result_id
                db.add(ComplianceResult(id=result_id, run_id=run.id, rule_id=rule.id, result=result))
                results.append(result)
                audit('RULE_EVALUATED', {'rule_result_id': result_id, 'rule_code': rule.rule_id, 'status': result['status'], 'evidence': result['evidence']}, result_id, 'rule_result')
            stage(6, 'COMPLETED', f"{sum(r['status'] == 'PASS' for r in results)}/{len(results)} rules passed")
            stage(7, 'RUNNING')
            names = [e for e in entities if e.type == 'company_name']
            source_name = next((v.record.get('company_name') for v in verifications if v.source == 'PAN'), '') or ''
            name_matches = [match_name(e.value, source_name) for e in names]
            name_check = min(name_matches, key=lambda c: c['similarity']) if name_matches else match_name('', source_name)
            identity = [{'label': 'Company name', **name_check,
                         'evidence': [{'entity_id': e.id, 'document_id': e.document_id} for e in names]}]
            for source in ['PAN', 'GST']:
                v = next(v for v in verifications if v.source == source)
                identity.append({'label': source+' identity', 'status': 'MATCH' if v.status == 'VERIFIED' else 'MISMATCH',
                                 'evidence': [{'verification_id': v.id, 'entity_id': v.entity_id}]})
            risk = RuleBasedAnomalyDetector().detect(results, documents, verifications, identity, tender.required_documents)
            expired_ids = {d.id for d in documents if not d.raw_text.strip()}
            for entity in entities:
                if entity.type == 'expiry_date':
                    try:
                        if date.fromisoformat(entity.value[:10]) < date.fromisoformat(tender.deadline[:10]):
                            expired_ids.add(entity.document_id)
                    except ValueError:
                        expired_ids.add(entity.document_id)
            expired_ids.update(d.id for d in documents if d.classification in {'oem_authorization', 'experience_certificate'} and
                               not any(e.document_id == d.id and e.type == 'expiry_date' for e in entities))
            features = {'number_of_mismatches': sum(v.status == 'MISMATCH' for v in verifications),
                        'number_of_expired_docs': len(expired_ids),
                        'missing_mandatory_documents': sum(s['type'] == 'missing_mandatory_document' for s in risk['contributing_factors']),
                        'identifier_similarity': name_check['similarity'],
                        'duplicate_documents': len(documents)-len({d.sha256 for d in documents}),
                        'unusual_document_age': max([max(0, (date.fromisoformat(tender.deadline[:10])-date.fromisoformat(e.value[:10])).days/365)
                                                     for e in entities if e.type == 'registration_date' and _valid_date(e.value)] or [0]),
                        'source_conflicts': sum(bool(v.evidence.get('conflicting_values')) for v in verifications)}
            risk['anomaly'] = IsolationForestDetector().detect(features)
            risk['identity_checks'] = identity
            risk['compliance'] = calculate_score(required=tender.required_documents, documents=documents, verifications=verifications,
                rules=results, expired_ids=expired_ids, identity_checks=identity, signals=risk['contributing_factors'], weights=tender.scoring_weights)
            risk_result = RiskResult(id=uid(), run_id=run.id, result=risk)
            db.add(risk_result)
            audit('RISK_CALCULATED', {'risk_result_id': risk_result.id, 'risk_score': risk['risk_score'],
                                     'compliance_score': risk['compliance']['score'], 'signals': risk['contributing_factors']}, risk_result.id, 'risk')
            stage(7, 'COMPLETED', f"Compliance {risk['compliance']['score']}/100 · {risk['risk_level']} risk")
            stage(8, 'RUNNING')
            retrieval = PolicyRetriever().retrieve(results, ' '.join(r['name'] for r in results if r['status'] == 'FAIL') or 'Verified compliant tender requirements')
            provider = OptionalOpenAIProvider() if settings.llm_api_key and settings.llm_provider != 'mock' else MockLLMProvider()
            explanation = provider.generate({'bidder_name': bidder.name, 'rules': results, 'risk': risk,
                                             'score': risk['compliance'], 'retrieval': retrieval,
                                             'verifications': [{'source': v.source, 'status': v.status, 'confidence': v.confidence} for v in verifications]})
            ai = AIRecommendation(id=uid(), run_id=run.id, result=explanation)
            db.add(ai)
            audit('AI_RECOMMENDATION_CREATED', {'ai_recommendation_id': ai.id, 'action': explanation['recommended_action'],
                                               'rule_result_ids': [r['result_id'] for r in results]}, ai.id, 'ai_recommendation')
            stage(8, 'COMPLETED', 'Evidence-grounded explanation and retrieved policy references saved')
            run.status, run.completed_at = 'COMPLETED', now()
            bid.status = 'PENDING_DECISION'
            stage(9, 'COMPLETED', 'Ready for officer review; no qualification decision made by AI')
        except Exception as exc:
            db.rollback()
            run = db.get(ProcessingRun, run_id)
            run.status = 'FAILED'
            run.error = f'Processing stopped ({type(exc).__name__}). Evidence already saved remains available. Retry the review.'
            run.completed_at = now()
            run.stages = [{**s, 'status': 'FAILED' if s['status'] == 'RUNNING' else s['status']} for s in run.stages]
            bid.status = 'PROCESSING_FAILED'
            db.commit()
            logging.exception('BID_PROCESSING_FAILED correlation_id=%s', run_id)
            audit('BID_PROCESSING_FAILED', {'error_type': type(exc).__name__})


def _valid_date(value):
    try:
        date.fromisoformat(value[:10])
        return True
    except ValueError:
        return False
