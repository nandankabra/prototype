"""Serve the existing API and React SPA from one Vercel container."""
from pathlib import Path
from fastapi import HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from app.main import app

PUBLIC = Path(__file__).resolve().parents[1] / 'public'
app.mount('/assets', StaticFiles(directory=PUBLIC / 'assets'), name='assets')


@app.get('/{path:path}', include_in_schema=False)
def frontend(path: str):
    if path == 'api' or path.startswith('api/'):
        raise HTTPException(404)
    requested = (PUBLIC / path).resolve()
    if PUBLIC in requested.parents and requested.is_file():
        return FileResponse(requested)
    return FileResponse(PUBLIC / 'index.html', headers={'Cache-Control': 'no-cache'})
