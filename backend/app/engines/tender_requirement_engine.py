"""Evidence-first extraction of tender-specific document requirements."""
from dataclasses import dataclass
import re


@dataclass(frozen=True)
class RequirementTemplate:
    code: str
    type: str
    label: str
    pattern: str
    evidence: tuple[str, ...]
    exemptions: tuple[str, ...] = ()


TEMPLATES = (
    RequirementTemplate('GST', 'GST_REGISTRATION', 'GST registration certificate', r'\bGST(?:IN| registration)\b', ('GST_CERTIFICATE',)),
    RequirementTemplate('PAN', 'PAN', 'PAN evidence', r'\bPAN\b', ('PAN_CARD',)),
    RequirementTemplate('UDYAM', 'UDYAM', 'Udyam registration', r'\b(?:UDYAM|MSME)\b', ('UDYAM_CERTIFICATE',), ('MSE',)),
    RequirementTemplate('OEM', 'OEM_AUTHORIZATION', 'OEM authorisation', r'\bOEM (?:authori[sz]ation|certificate)\b', ('OEM_AUTHORIZATION',)),
    RequirementTemplate('EXP', 'EXPERIENCE', 'Past-performance evidence', r'\b(?:experience|work order|completion certificate)\b', ('WORK_ORDER', 'COMPLETION_CERTIFICATE'), ('MSE', 'DPIIT_STARTUP')),
    RequirementTemplate('TURNOVER', 'TURNOVER', 'Annual-turnover evidence', r'\b(?:annual turnover|turnover criteria|audited balance sheet|CA certificate)\b', ('AUDITED_FINANCIAL_STATEMENT', 'CA_CERTIFICATE'), ('MSE', 'DPIIT_STARTUP')),
    RequirementTemplate('BIS', 'BIS_CERTIFICATE', 'BIS certificate', r'\bBIS(?: certification| licence)?\b', ('BIS_CERTIFICATE',)),
    RequirementTemplate('EMD', 'EMD', 'EMD or verified exemption evidence', r'\b(?:EMD|earnest money deposit)\b', ('EMD_RECEIPT', 'EMD_EXEMPTION_EVIDENCE'), ('MSE', 'DPIIT_STARTUP')),
    RequirementTemplate('EPFO', 'EPFO', 'EPFO registration', r'\bEPFO\b', ('EPFO_REGISTRATION',)),
    RequirementTemplate('FSSAI', 'FSSAI', 'FSSAI licence', r'\bFSSAI\b', ('FSSAI_LICENCE',)),
    RequirementTemplate('LOCAL', 'LOCAL_CONTENT', 'Make in India / local-content declaration', r'\b(?:local content|make in india)\b', ('LOCAL_CONTENT_CERTIFICATE',)),
)


class TenderRequirementEngine:
    """Extract only requirements supported by a tender-document line of evidence."""
    def extract(self, pages: list[dict]) -> list[dict]:
        requirements, seen = [], set()
        for page in pages:
            for line in (page.get('text') or '').splitlines():
                for template in TEMPLATES:
                    if template.code in seen or not re.search(template.pattern, line, re.I):
                        continue
                    value = {}
                    amount = re.search(r'(?:₹|Rs\.?)(\s*[\d,]+(?:\.\d+)?)', line, re.I)
                    years = re.search(r'\b(\d+)\s+years?\b', line, re.I)
                    if amount:
                        value['amount_text'] = amount.group(0)
                    if years:
                        value['period_years'] = int(years.group(1))
                    requirements.append({'requirement_code': template.code, 'type': template.type, 'label': template.label,
                        'mandatory': not bool(re.search(r'\boptional\b', line, re.I)), 'requirement_value': value,
                        'accepted_evidence': list(template.evidence), 'exemptions': list(template.exemptions),
                        'source_page': page.get('page_number'), 'source_clause': None, 'source_text': line.strip()[:2000],
                        'confidence': min(float(page.get('confidence', .7)), .98), 'status': 'EXTRACTED'})
                    seen.add(template.code)
        return requirements
