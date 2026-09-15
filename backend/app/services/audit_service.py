"""Tamper-evident, append-only application audit chain (not a blockchain)."""
import hashlib
import json
import threading
from sqlalchemy import select, text
from datetime import datetime, timezone
from fastapi.encoders import jsonable_encoder
from app.models import AuditEvent, uid, now

AUDIT_LOCK = threading.RLock()
GENESIS = '0' * 64


def digest(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def append_event(db, *, action, object_id, bid_id=None, actor='system', role='SYSTEM',
                 object_type='bid', previous_state=None, new_state=None, metadata=None):
    """Commit evidence and its audit event together; serialize the global hash chain."""
    metadata = jsonable_encoder(metadata or {})
    previous_state = jsonable_encoder(previous_state or {})
    new_state = jsonable_encoder(new_state or {})
    with AUDIT_LOCK:
        if db.bind.dialect.name == 'postgresql':
            db.execute(text('SELECT pg_advisory_xact_lock(26100)'))
        last = db.scalar(select(AuditEvent).order_by(AuditEvent.sequence.desc()).limit(1))
        previous_hash = last.current_hash if last else GENESIS
        timestamp = now()
        event_id = uid()
        evidence_hash = digest(json.dumps(metadata or {}, sort_keys=True, default=str))
        data = {'event_id': event_id, 'timestamp': timestamp.isoformat(), 'actor': actor, 'role': role,
                'action': action, 'object_type': object_type, 'object_id': object_id, 'bid_id': bid_id,
                'previous_state': previous_state or {}, 'new_state': new_state or {},
                'metadata': metadata or {}, 'evidence_hash': evidence_hash,
                'sequence': last.sequence+1 if last else 1}
        payload = json.dumps(data, sort_keys=True, separators=(',', ':'), default=str)
        event = AuditEvent(id=event_id, created_at=timestamp, sequence=data['sequence'], bid_id=bid_id,
                           actor=actor, role=role, action=action, object_type=object_type, object_id=object_id,
                           previous_state=previous_state or {}, new_state=new_state or {}, details=metadata or {},
                           evidence_hash=evidence_hash, previous_hash=previous_hash,
                           current_hash=digest(previous_hash+payload), payload=payload)
        db.add(event)
        db.commit()
        return event


def verify_chain(events) -> dict:
    previous = GENESIS
    for index, event in enumerate(events):
        try:
            data = json.loads(event.payload)
            recorded_time = datetime.fromisoformat(data['timestamp']).replace(tzinfo=timezone.utc)
            actual_time = event.created_at.replace(tzinfo=timezone.utc)
            if recorded_time != actual_time:
                return {'status': 'FAILED', 'checked_events': index, 'failed_event_id': event.id}
        except (ValueError, KeyError, TypeError):
            return {'status': 'FAILED', 'checked_events': index, 'failed_event_id': event.id}
        columns_match = all(data.get(key) == value for key, value in {
            'event_id': event.id, 'sequence': event.sequence, 'bid_id': event.bid_id,
            'actor': event.actor, 'role': event.role, 'action': event.action,
            'object_type': event.object_type, 'object_id': event.object_id,
            'previous_state': event.previous_state, 'new_state': event.new_state,
            'metadata': event.details, 'evidence_hash': event.evidence_hash}.items())
        if (event.sequence != index+1 or event.previous_hash != previous or
                event.current_hash != digest(previous+event.payload) or not columns_match or
                event.evidence_hash != digest(json.dumps(event.details, sort_keys=True, default=str))):
            return {'status': 'FAILED', 'checked_events': index, 'failed_event_id': event.id}
        previous = event.current_hash
    return {'status': 'VERIFIED', 'checked_events': len(events), 'head_hash': previous,
            'scope': 'Entire application chain', 'limitation': 'Application append-only; a database administrator can rewrite storage.'}
