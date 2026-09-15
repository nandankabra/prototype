from pathlib import Path
import hashlib
import re
from fastapi import HTTPException
from app.core.config import settings
from app.models import Document, uid

MIME_TYPES = {'.pdf': 'application/pdf', '.png': 'image/png', '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg'}


def save_upload(db, bid_id: str, filename: str, content: bytes, is_seed=False) -> Document:
    """Store under generated IDs; submitted filenames never determine filesystem paths."""
    suffix = Path(filename).suffix.lower()
    if suffix not in MIME_TYPES:
        raise HTTPException(415, 'Upload a PDF, PNG, JPG, or JPEG')
    if not content or len(content) > settings.upload_max_mb * 1024 * 1024:
        raise HTTPException(413, f'File must be non-empty and at most {settings.upload_max_mb} MB')
    signatures = {'.pdf': content.startswith(b'%PDF'), '.png': content.startswith(b'\x89PNG\r\n\x1a\n'),
                  '.jpg': content.startswith(b'\xff\xd8'), '.jpeg': content.startswith(b'\xff\xd8')}
    if not signatures[suffix]:
        raise HTTPException(415, 'File contents do not match the extension')
    document_id = uid()
    directory = Path(settings.data_dir).resolve() / 'documents'
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f'{document_id}{suffix}'
    path.write_bytes(content)
    safe_name = re.sub(r'[^A-Za-z0-9._ -]', '_', Path(filename.replace('\\', '/')).name)[:200]
    doc = Document(id=document_id, bid_id=bid_id, filename=safe_name, path='documents/'+path.name, mime_type=MIME_TYPES[suffix],
                   sha256=hashlib.sha256(content).hexdigest(), is_seed=is_seed)
    db.add(doc)
    db.flush()
    return doc


def document_path(document: Document) -> Path:
    """Resolve uploads against the active volume, including legacy absolute locations."""
    root = Path(settings.data_dir).resolve() / 'documents'
    suffix = Path(document.path).suffix.lower()
    if suffix not in MIME_TYPES:
        raise ValueError('Unsupported stored document format')
    return root / f'{document.id}{suffix}'
