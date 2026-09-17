"""Verification registry. Unapproved sources never claim a successful check."""
from datetime import datetime, timezone


SOURCES = [
    ('GST', 'GST_REGISTRATION', 'GSTN', 'https://www.gst.gov.in/', 'AUTHORISED_API'),
    ('UDYAM', 'UDYAM', 'Ministry of MSME', 'https://udyamregistration.gov.in/', 'AUTHORISED_API'),
    ('MCA', 'CIN', 'Ministry of Corporate Affairs', 'https://www.mca.gov.in/', 'AUTHORISED_API'),
    ('PAN', 'PAN', 'Income Tax Department', 'https://www.incometax.gov.in/', 'APPROVED_AGENCY_API'),
    ('DPIIT', 'DPIIT', 'Startup India', 'https://www.startupindia.gov.in/', 'AUTHORISED_API'),
    ('EPFO', 'EPFO', 'Employees\' Provident Fund Organisation', 'https://www.epfindia.gov.in/', 'OFFICIAL_SOURCE'),
    ('BIS', 'BIS_CERTIFICATE', 'Bureau of Indian Standards', 'https://www.bis.gov.in/', 'OFFICIAL_SOURCE'),
    ('DIGILOCKER', 'DIGILOCKER_DOCUMENT', 'DigiLocker / API Setu', 'https://www.digilocker.gov.in/', 'CONSENTED_ISSUER_RECORD'),
    ('FSSAI', 'FSSAI', 'Food Safety and Standards Authority of India', 'https://foscos.fssai.gov.in/', 'OFFICIAL_SOURCE'),
    ('DGFT', 'IEC', 'Directorate General of Foreign Trade', 'https://www.dgft.gov.in/', 'OFFICIAL_SOURCE'),
    ('NSIC', 'NSIC', 'National Small Industries Corporation', 'https://www.nsic.co.in/', 'OFFICIAL_SOURCE'),
]


class VerificationProviderRegistry:
    def verify(self, source: str, identifier: str, *, consent: bool = False) -> dict:
        item = next((row for row in SOURCES if row[0] == source), None)
        now = datetime.now(timezone.utc).isoformat()
        if not item:
            return {'source': source, 'status': 'SOURCE_UNAVAILABLE', 'identifier': identifier, 'record': {}, 'confidence': 0,
                    'is_mock': False, 'checked_at': now, 'evidence': {'reason': 'Source is not registered for this deployment.', 'method': 'NONE'}}
        return {'source': source, 'status': 'API_ACCESS_NOT_CONFIGURED', 'identifier': identifier, 'record': {}, 'confidence': 0,
                'is_mock': False, 'checked_at': now,
                'evidence': {'reason': 'Authorised credentials, consent, or onboarding are required before this source can be queried.',
                             'authority': item[2], 'source_url': item[3], 'method': item[4], 'consent_recorded': consent}}
