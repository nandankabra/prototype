"""Restricted declarative expressions; no eval, executable Python, or API-level rules."""
from dataclasses import dataclass
from datetime import date

ALLOWED_OPERATORS = {'source_status', 'document_present', 'valid_documents', 'minimum_field'}


@dataclass
class RuleCondition:
    op: str
    source: str | None = None
    document: str | None = None
    field: str | None = None
    value: float | None = None


@dataclass
class RuleResult:
    passed: bool
    explanation: str
    evidence: list


class RuleEvaluator:
    def evaluate(self, rule, *, documents, entities, verifications, deadline) -> dict:
        exp = rule.expression
        op = exp['op']
        evidence = []
        if op == 'source_status':
            v = next((v for v in verifications if v.source == exp['source']), None)
            passed = v is not None and v.status == 'VERIFIED'
            explanation = f"{exp['source']}: {v.status if v else 'NOT_CHECKED'}"
            if v:
                evidence = [{'verification_id': v.id, 'entity_id': v.entity_id, 'source': v.source,
                             'extracted': v.identifier, 'source_value': v.evidence.get('source_value'), 'status': v.status}]
        elif op == 'document_present':
            matching = [d for d in documents if d.classification == exp['document'] and d.raw_text.strip()]
            passed = bool(matching)
            explanation = f"{exp['document'].replace('_', ' ').title()}: {'submitted' if passed else 'missing or unreadable'}"
            evidence = [{'document_id': d.id, 'filename': d.filename} for d in matching]
        elif op == 'valid_documents':
            expired, unknown = [], []
            for ent in entities:
                if ent.type == 'expiry_date':
                    try:
                        if date.fromisoformat(ent.value[:10]) < date.fromisoformat(deadline[:10]):
                            expired.append(ent)
                    except ValueError:
                        unknown.append(ent)
            certificate_docs = [d for d in documents if d.classification in {'experience_certificate', 'oem_authorization'}]
            unprovided = [d for d in certificate_docs if not any(e.document_id == d.id and e.type == 'expiry_date' for e in entities)]
            passed = not expired and not unknown and not unprovided
            explanation = f'{len(expired)} expired; {len(unknown)+len(unprovided)} validity dates require review. Reference date: {deadline[:10]}.'
            evidence = [{'entity_id': e.id, 'document_id': e.document_id, 'extracted': e.value, 'source_page': e.source_page} for e in expired+unknown]
            evidence += [{'document_id': d.id, 'status': 'MISSING_VALIDITY_DATE'} for d in unprovided]
        elif op == 'minimum_field':
            relevant = [e for e in entities if e.type == exp['field']]
            values = []
            for ent in relevant:
                try:
                    values.append(float(ent.value.replace('%', '').replace(',', '').strip()))
                except ValueError:
                    pass
            passed = bool(values) and min(values) >= exp['value']
            explanation = f"{exp['field'].replace('_', ' ').title()}: {min(values) if values else 'not provided'}; minimum {exp['value']}%. Bidder declaration, not independently verified."
            evidence = [{'entity_id': e.id, 'document_id': e.document_id, 'extracted': e.value} for e in relevant]
        else:
            passed, explanation = False, 'Unsupported rule expression; administrator review required'
        return {'rule_id': rule.id, 'rule_code': rule.rule_id, 'name': rule.name, 'category': rule.category,
                'severity': rule.severity, 'required': rule.required, 'expression': exp,
                'status': 'PASS' if passed else 'FAIL', 'explanation': explanation, 'evidence': evidence}
