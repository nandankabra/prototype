"""Vercel container entrypoint. Only the app's HTTP port is exposed."""
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
import urllib.request

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.core.config import settings
settings.signing_key()

mock = subprocess.Popen([sys.executable, '-m', 'uvicorn', 'main:app', '--host', '127.0.0.1', '--port', '8001'], cwd='/mock-gov-api')
server = None

def stop(*_):
    if server is not None:
        server.terminate()
    mock.terminate()

signal.signal(signal.SIGTERM, stop)
signal.signal(signal.SIGINT, stop)
try:
    for _ in range(100):
        if mock.poll() is not None:
            raise RuntimeError('Mock source service exited during startup')
        try:
            urllib.request.urlopen('http://127.0.0.1:8001/health', timeout=.2).close()
            break
        except OSError:
            time.sleep(.1)
    else:
        raise RuntimeError('Mock source service did not become ready')
    server = subprocess.Popen([sys.executable, '-m', 'uvicorn', 'deployment.web:app', '--host', '0.0.0.0', '--port', os.environ.get('PORT', '8000')])
    sys.exit(server.wait())
finally:
    stop()
    mock.wait(timeout=15)
