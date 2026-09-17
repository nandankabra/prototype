"""Initialize the selected cloud database using an ignored Vercel env export."""
import os
from pathlib import Path
import sys
from dotenv import dotenv_values

root = Path(__file__).resolve().parents[1]
if len(sys.argv) != 2:
    raise SystemExit('Usage: .venv/bin/python deployment/initialize_cloud.py <ignored-env-file>')
values = dotenv_values(sys.argv[1])
database_url = values.get('DATABASE_URL') or values.get('POSTGRES_URL')
if not database_url:
    raise SystemExit('The selected environment has no PostgreSQL database connection.')
key_file = root / 'output' / 'hosting-jwt.key'
key = key_file.read_text().strip() if key_file.exists() else values.get('JWT_SECRET')
if not key:
    raise SystemExit('Configure the hosted signing key before database initialization.')
os.environ.update(DATABASE_URL=database_url, JWT_SECRET=key, HOSTED_MODE='true',
                  DOCUMENT_STORAGE='database', DEMO_MODE='true',
                  DATA_DIR=str(root / 'output' / 'cloud-initialization'))
from initialize import initialize
initialize()
