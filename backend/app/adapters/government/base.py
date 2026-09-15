from abc import ABC, abstractmethod
from datetime import datetime, timezone
import httpx
from app.core.config import settings


class GovernmentSourceAdapter(ABC):
    source: str

    @abstractmethod
    def verify(self, bidder_id: str, identifier: str, company_name: str, simulate_unavailable: bool = False) -> dict:
        """Return a normalized verification record with explicit source provenance."""


class HTTPMockAdapter(GovernmentSourceAdapter):
    path: str

    def verify(self, bidder_id, identifier, company_name, simulate_unavailable=False):
        try:
            response = httpx.post(f'{settings.mock_gov_api_url}/{self.path}/verify',
                                  json={'bidder_id': bidder_id, 'identifier': identifier,
                                        'company_name': company_name, 'simulate_unavailable': simulate_unavailable}, timeout=3)
            response.raise_for_status()
            result = response.json()
            required = {'source', 'status', 'record', 'confidence', 'checked_at', 'evidence', 'is_mock', 'identifier'}
            if not required.issubset(result) or result['status'] not in {
                'VERIFIED', 'MISMATCH', 'NOT_FOUND', 'EXPIRED', 'SOURCE_UNAVAILABLE', 'MANUAL_REVIEW'
            } or result['is_mock'] is not True:
                raise ValueError('Invalid mock-source response')
            return result
        except (httpx.HTTPError, ValueError, TypeError):
            return {'source': self.source, 'status': 'SOURCE_UNAVAILABLE', 'identifier': identifier,
                    'record': {}, 'confidence': 0, 'is_mock': True,
                    'checked_at': datetime.now(timezone.utc).isoformat(),
                    'evidence': {'extracted_value': identifier, 'source_value': None,
                                 'reason': 'Source unavailable; officer review required. No verification inferred.',
                                 'label': 'MOCK AUTHORISED SOURCE — DEMO'}}
