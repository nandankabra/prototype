"""Apply additive migrations and seed the hosted demo once before serving it.

Run with DATABASE_URL, JWT_SECRET, HOSTED_MODE=true and DOCUMENT_STORAGE=database.
Cloud environment values must stay outside the source tree/deployment archive.
"""
from pathlib import Path
import sys
from sqlalchemy import text
from alembic import command
from alembic.config import Config

root = Path(__file__).resolve().parents[1]
backend = root / 'backend' if (root / 'backend').exists() else root
sys.path.insert(0, str(backend))
from app.core.config import settings
from app.core.database import engine
from app.seed import seed


def initialize():
    settings.signing_key()
    if not settings.database_url.startswith('postgresql') or settings.document_storage != 'database':
        raise RuntimeError('Hosted initialization requires PostgreSQL and durable document storage')
    config = Config(str(backend / 'alembic.ini'))
    config.set_main_option('script_location', str(backend / 'alembic'))
    # Session advisory locks must not be held inside a long idle transaction:
    # Neon closes those sessions while seed() uses its own short-lived commits.
    with engine.connect().execution_options(isolation_level='AUTOCOMMIT') as lock:
        lock.execute(text('SELECT pg_advisory_lock(2610026)'))
        try:
            command.upgrade(config, 'head')
            print(seed(), flush=True)
        finally:
            try:
                lock.execute(text('SELECT pg_advisory_unlock(2610026)'))
            except Exception:
                # A closed connection releases a PostgreSQL session lock itself.
                pass


if __name__ == '__main__':
    initialize()
