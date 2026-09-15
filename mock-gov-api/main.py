"""Fictional records behind an actual HTTP boundary. No government network calls."""
from datetime import datetime, timezone
import json
import logging
from pathlib import Path
from fastapi import FastAPI
from pydantic import BaseModel, Field

app = FastAPI(title='ByteCode Mock Authorised Sources - DEMO', version='1.0.0',
              description='Entirely fictional records. These endpoints do not connect to any government portal.')
RECORDS = json.loads((Path(__file__).parent / 'data' / 'seed_bidders.json').read_text())
SOURCES = {'pan': 'PAN', 'gst': 'GST', 'udyam': 'UDYAM', 'itr': 'INCOME_TAX', 'epfo': 'EPFO',
           'esic': 'ESIC', 'startup': 'STARTUP_INDIA', 'nsic': 'NSIC', 'digilocker': 'DIGILOCKER',
           'blacklist': 'BLACKLIST', 'oem': 'OEM'}


class Check(BaseModel):
    bidder_id: str = Field(max_length=36)
    identifier: str = Field(default='', max_length=255)
    company_name: str = Field(default='', max_length=255)
    simulate_unavailable: bool = False


@app.get('/health')
def health():
    return {'status': 'ok', 'is_mock': True, 'records': len(RECORDS)}


def endpoint_for(source: str):
    def verify(check: Check):
        bidder = RECORDS.get(check.bidder_id)
        record = bidder.get(source, {}) if bidder else {}
        expected = str(record.get('identifier', ''))
        if check.simulate_unavailable:
            status = 'SOURCE_UNAVAILABLE'
        elif not record:
            status = 'NOT_FOUND'
        elif source == 'BLACKLIST':
            status = 'MISMATCH' if record.get('listed') else 'VERIFIED'
        elif not check.identifier:
            status = 'MANUAL_REVIEW'
        elif check.identifier.upper() != expected.upper():
            status = 'MISMATCH'
        elif record.get('valid_until', '9999') < '2026-09-30':
            status = 'EXPIRED'
        elif record.get('status') not in {'ACTIVE', 'CLEAR', 'FILED', 'VALID'}:
            status = 'MANUAL_REVIEW'
        else:
            status = 'VERIFIED'
        logging.info(json.dumps({'source': source, 'status': status, 'is_mock': True}))
        return {'source': source, 'status': status, 'identifier': check.identifier,
                'record': record if status != 'SOURCE_UNAVAILABLE' else {},
                'confidence': 0 if status in {'SOURCE_UNAVAILABLE', 'NOT_FOUND', 'MANUAL_REVIEW'} else 0.99,
                'checked_at': datetime.now(timezone.utc).isoformat(), 'is_mock': True,
                'evidence': {'extracted_value': check.identifier,
                             'source_value': expected if status != 'SOURCE_UNAVAILABLE' else None,
                             'reason': 'Simulated service outage' if check.simulate_unavailable else
                             f'{source}: submitted identifier compared with fictional source record',
                             'label': 'MOCK AUTHORISED SOURCE — DEMO'}}
    verify.__name__ = f'verify_{source.lower()}'
    return verify


for path, source in SOURCES.items():
    app.post(f'/{path}/verify', tags=[source])(endpoint_for(source))
