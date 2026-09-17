FROM node:22-alpine@sha256:c610fcdfb1d5b4740dd70c284ed3cb16bb857e0f7166196e36a5501df7a3aa32 AS frontend
WORKDIR /frontend
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
ENV VITE_UPLOAD_MAX_MB=4
RUN npm run build

FROM python:3.11-slim@sha256:9534e5a8e315485d4061ed659af0fd78a284c015f9b73661b41d6bab25604534
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 \
    HOSTED_MODE=true DOCUMENT_STORAGE=database DATA_DIR=/tmp/bytecode \
    UPLOAD_MAX_MB=4 VECTOR_PROVIDER=faiss ENABLE_HEAVY_ML=false \
    OCR_PROVIDER=tesseract MOCK_GOV_API_URL=http://127.0.0.1:8001 PORT=8000
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends tesseract-ocr libgomp1 && rm -rf /var/lib/apt/lists/*
COPY backend/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
COPY backend/ ./
COPY sample-docs/ ./sample-docs/
COPY mock-gov-api/ /mock-gov-api/
COPY deployment/ ./deployment/
COPY --from=frontend /frontend/dist ./public/
RUN useradd --uid 10001 --create-home app && chown -R app:app /app
USER app
EXPOSE 8000
CMD ["python", "deployment/start.py"]
