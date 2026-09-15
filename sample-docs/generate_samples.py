"""Export seeded PDFs for uploads during a demo; supports host and backend container."""
from pathlib import Path
import sys
import shutil
root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root / 'backend' if (root / 'backend').exists() else root))
from sqlalchemy import select
from app.core.database import SessionLocal
from app.models import Document, Bid, Bidder
from app.services.document_service import document_path

out = root / 'sample-docs' / 'generated'
out.mkdir(parents=True, exist_ok=True)
with SessionLocal() as db:
    for doc in db.scalars(select(Document).where(Document.is_seed.is_(True))):
        bid = db.get(Bid, doc.bid_id)
        bidder = db.get(Bidder, bid.bidder_id)
        folder = out / (bid.scenario+'_'+bidder.name.split()[0])
        folder.mkdir(exist_ok=True)
        shutil.copyfile(document_path(doc), folder / doc.filename)
print(f'Sample PDFs exported to {out}')
