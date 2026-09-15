from functools import lru_cache
import numpy as np
from app.models import uid

from pathlib import Path
import json

RISK_POINTS = json.loads((Path(__file__).resolve().parents[1] / 'data' / 'risk_weights.json').read_text())


class RuleBasedAnomalyDetector:
    def detect(self, rules, documents, verifications, identity_checks, required_documents=()):
        signals = []
        def add(kind, description, evidence, rule_result_ids=None):
            signals.append({'id': uid(), 'type': kind, 'description': description, 'points': RISK_POINTS[kind],
                            'evidence': evidence, 'rule_result_ids': rule_result_ids or []})
        linked_verifications = set()
        for rule in rules:
            if rule['status'] == 'PASS':
                continue
            exp = rule['expression']
            if exp['op'] == 'source_status':
                ev = rule['evidence'][0] if rule['evidence'] else {}
                linked_verifications.add(ev.get('verification_id'))
                if ev.get('status') == 'SOURCE_UNAVAILABLE':
                    kind = 'source_unavailable'
                elif exp['source'] == 'BLACKLIST' and ev.get('status') == 'MISMATCH':
                    kind = 'blacklisting_hit'
                else:
                    kind = 'identity_mismatch' if exp['source'] == 'PAN' else 'source_mismatch'
            elif exp['op'] == 'document_present':
                kind = 'missing_mandatory_document'
            elif exp['op'] == 'valid_documents':
                kind = 'unknown_validity' if '0 expired;' in rule['explanation'] else 'expired_certificate'
            else:
                kind = 'tender_rule_violation'
            add(kind, rule['explanation'], rule['evidence'], [rule['result_id']])
        for v in verifications:
            if v.id not in linked_verifications and v.status != 'VERIFIED':
                # A missing OEM is already explained by the mandatory document rule.
                if v.source == 'OEM' and any(s['type'] == 'missing_mandatory_document' and 'Oem' in s['description'] for s in signals):
                    continue
                add('source_unavailable' if v.status == 'SOURCE_UNAVAILABLE' else 'source_mismatch',
                    f'{v.source}: {v.status}', [{'verification_id': v.id, 'entity_id': v.entity_id}])
        present = {d.classification for d in documents if d.raw_text.strip()}
        covered = {r['expression'].get('document') for r in rules if r['expression']['op'] == 'document_present' and r['status'] != 'PASS'}
        for kind in required_documents:
            if kind not in present and kind not in covered:
                add('missing_mandatory_document', f"{kind.replace('_', ' ').title()}: missing or unreadable", [])
        seen = set()
        for doc in documents:
            if doc.sha256 in seen:
                add('duplicate_document', f'Duplicate file content: {doc.filename}', [{'document_id': doc.id, 'sha256': doc.sha256}])
            seen.add(doc.sha256)
            for warning in doc.extraction.get('metadata_warnings', []):
                add('suspicious_metadata', warning, [{'document_id': doc.id}])
            if not doc.raw_text.strip():
                add('unreadable_document', f'No readable text: {doc.filename}', [{'document_id': doc.id}])
        for check in identity_checks:
            if check['label'] == 'Company name' and check['status'] != 'MATCH':
                add('inconsistent_company', 'Company name differs across uploaded and source records', check.get('evidence', []))
        score = min(100, sum(s['points'] for s in signals))
        level = 'CRITICAL' if score >= 80 else 'HIGH' if score >= 45 else 'MEDIUM' if score >= 20 else 'LOW'
        return {'risk_score': score, 'risk_level': level, 'contributing_factors': signals,
                'method': 'Sum of explicit risk points, capped at 100. LOW <20; MEDIUM 20–44; HIGH 45–79; CRITICAL ≥80.',
                'weights': RISK_POINTS}


@lru_cache(maxsize=1)
def isolation_model():
    from sklearn.ensemble import IsolationForest
    # Transparent synthetic reference population, not procurement-ground-truth training data.
    rng = np.random.default_rng(26100)
    baseline = np.column_stack([rng.poisson(.3, 160), rng.poisson(.15, 160), rng.poisson(.2, 160),
                                rng.uniform(.94, 1, 160), rng.poisson(.1, 160), rng.uniform(0, 5, 160), rng.poisson(.2, 160)])
    return IsolationForest(n_estimators=64, contamination=.1, random_state=26100).fit(baseline)


class IsolationForestDetector:
    def detect(self, features: dict):
        try:
            model = isolation_model()
            x = np.array([list(features.values())])
            score = round(float(-model.score_samples(x)[0]), 4)
            unusual = bool(model.predict(x)[0] == -1)
            return {'anomaly_score': score, 'anomalies': ['Unusual feature combination'] if unusual else [],
                    'detector': 'IsolationForestDetector', 'features': features,
                    'explanation': 'Compared with a deterministic synthetic reference population. Advisory signal only; it does not add hidden points to the risk score.'}
        except Exception:
            return {'anomaly_score': None, 'anomalies': [], 'features': features, 'detector': 'RuleBasedAnomalyDetector fallback',
                    'explanation': 'Isolation Forest unavailable. Explicit rule-based risk scoring remains active.'}
