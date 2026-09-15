import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time

TEST_ROOT = Path(tempfile.mkdtemp(prefix='bytecode-tests-'))
os.environ['DATABASE_URL'] = 'sqlite:///'+str(TEST_ROOT/'test.db')
os.environ['DATA_DIR'] = str(TEST_ROOT/'uploads')
os.environ['JWT_SECRET'] = 'test-only-key-not-used-outside-isolated-test-environment-26100'
os.environ['DEMO_MODE'] = 'false'
os.environ['QDRANT_URL'] = 'http://127.0.0.1:1'
os.environ['VECTOR_PROVIDER'] = 'faiss'
with socket.socket() as sock:
    sock.bind(('127.0.0.1', 0))
    MOCK_PORT = sock.getsockname()[1]
os.environ['MOCK_GOV_API_URL'] = f'http://127.0.0.1:{MOCK_PORT}'

import httpx
import pytest
from fastapi.testclient import TestClient
from app.core.database import Base, engine, SessionLocal
from app.models import Bid
from app.seed import seed
from app.main import app
from app.services.processing_service import queue_run, process_bid
from sqlalchemy import select


@pytest.fixture(scope='session', autouse=True)
def database_and_mock():
    root = Path(__file__).resolve().parents[2]
    mock_root = root/'mock-gov-api' if (root/'mock-gov-api').exists() else Path('/mock-gov-api')
    process = subprocess.Popen([sys.executable, '-m', 'uvicorn', 'main:app', '--host', '127.0.0.1', '--port', str(MOCK_PORT)],
                               cwd=mock_root, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        for _ in range(100):
            try:
                if httpx.get(os.environ['MOCK_GOV_API_URL']+'/health', timeout=.3).status_code == 200:
                    break
            except httpx.HTTPError:
                time.sleep(.1)
        else:
            raise RuntimeError('Isolated mock HTTP service did not start')
        Base.metadata.create_all(engine)
        seed()
        with SessionLocal() as db:
            bid_ids = list(db.scalars(select(Bid.id)))
        for bid_id in bid_ids:
            with SessionLocal() as db:
                run = queue_run(db, db.get(Bid, bid_id), 'test-runner', 'SYSTEM')
                run_id = run.id
            process_bid(run_id)
        yield
    finally:
        process.terminate()
        process.wait(timeout=10)
        engine.dispose()


@pytest.fixture
def db():
    with SessionLocal() as session:
        yield session


@pytest.fixture
def client():
    with TestClient(app) as client:
        response = client.post('/api/auth/login', json={'email':'officer@bytecode.demo','password':'officer123'})
        client.headers['Authorization'] = 'Bearer '+response.json()['access_token']
        yield client
