"""Authorised tender-source boundary.

The application never evades CAPTCHA, login, rate limits, or access controls.
GeM documents are imported only from a public official URL supplied by an
authorised user or an approved integration configured at deployment time.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from urllib.parse import urlparse
import hashlib
import httpx


@dataclass
class ImportedTenderDocument:
    source_url: str
    content: bytes
    content_type: str


class TenderProvider(ABC):
    source: str

    @abstractmethod
    def import_public_document(self, source_url: str) -> ImportedTenderDocument: ...


class GeMTenderProvider(TenderProvider):
    source = 'GEM'
    official_hosts = {'bidplus-global.gem.gov.in', 'bidplus.gem.gov.in', 'gem.gov.in', 'assets-bg.gem.gov.in'}

    def import_public_document(self, source_url: str) -> ImportedTenderDocument:
        parsed = urlparse(source_url)
        if parsed.scheme != 'https' or parsed.hostname not in self.official_hosts:
            raise ValueError('Only an official public GeM HTTPS document URL can be imported.')
        is_public_bid_page = parsed.hostname in {'bidplus-global.gem.gov.in', 'bidplus.gem.gov.in'} and '/showbidDocument/' in parsed.path
        try:
            with httpx.Client(timeout=20, follow_redirects=False, headers={'User-Agent': 'ByteCodeVerify/1.0 procurement intake'}) as client:
                response = client.get(source_url)
        except httpx.RequestError as exc:
            raise ValueError('The official GeM document could not be reached. Check your connection and try again.') from exc
        if response.status_code in {401, 403, 429}:
            raise ValueError('GeM restricted this document request. Use an approved integration or upload the authorised document.')
        if response.status_code == 404:
            raise ValueError('GeM could not find this document page. Open the bid document in GeM and copy its complete address-bar URL again.')
        if response.is_error:
            raise ValueError(f'GeM returned {response.status_code} for this document. Check that the public bid-document page is still available.')
        content_type = response.headers.get('content-type', '').lower()
        if len(response.content) > 25 * 1024 * 1024:
            raise ValueError('Tender document exceeds the 25 MB intake limit.')
        is_pdf = 'pdf' in content_type or response.content.startswith(b'%PDF')
        is_html_bid_document = is_public_bid_page and 'html' in content_type
        if not (is_pdf or is_html_bid_document):
            raise ValueError('Use a direct official GeM PDF, or a public GeM bid-document page URL containing /showbidDocument/.')
        return ImportedTenderDocument(source_url=source_url, content=response.content, content_type=content_type)

    @staticmethod
    def digest(content: bytes) -> str:
        return hashlib.sha256(content).hexdigest()
