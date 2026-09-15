# ByteCode Verify

**AI-Powered Bid Compliance Verification Platform** · Team ByteCode · SIH 2026 · PS 26100

A working local procurement decision-support prototype for the CPCL problem statement. Officers upload bidder documents, inspect extracted fields, compare them with **11 fictional HTTP source services**, evaluate tender rules, review explainable compliance/risk scores, and record their own decision with a required reason.

**The officer decides.** Every source result is labeled `MOCK AUTHORISED SOURCE — DEMO`. This application has no connection to government portals. All seeded companies, documents, and identifiers are fictional.

## Quick start

Prerequisites: Docker Desktop with Docker Compose v2, approximately 4 GB available to Docker, and an internet connection for the first dependency/image download. Heavy neural models are disabled by default to keep the prototype suitable for an 8 GB laptop. Subsequent demo runs need no external API key.

```bash
cp .env.example .env
docker compose up --build
```

Or run in the background:

```bash
make demo
# equivalent: ./scripts/demo.sh
```

Startup applies Alembic migrations, seeds missing demo records, and warms previously unprocessed seeded bids through the real pipeline. The first dashboard may show initialization in progress for a few seconds. Seeding is idempotent: it does not reset reviews, uploads, rules, or decisions.

| Service | Default URL / port |
|---|---|
| React application | http://localhost:3000 |
| Backend Swagger / ReDoc | http://localhost:8000/docs · http://localhost:8000/redoc |
| Mock-source Swagger / ReDoc | http://localhost:8001/docs · http://localhost:8001/redoc |
| Qdrant dashboard | http://localhost:6333/dashboard |
| PostgreSQL | localhost:5432 |

The current development machine already uses ports 8000 and 5432. Its ignored `.env` sets **backend 8010, mock API 8011, PostgreSQL 55432, frontend 3000**. These are host-port changes only. Container-to-container service addresses remain unchanged. A fresh `.env.example` uses the requested default ports.

```bash
docker compose ps
docker compose exec backend alembic current
docker compose exec backend python -m app.seed
make samples   # exports PDFs to sample-docs/generated on the host
make test
make stop      # stops this project's containers, preserves volumes
```

`docker compose down -v` also deletes this project's database and uploaded files. Use it only when intentionally resetting the demo.

## Demo accounts

These are **demo credentials**, not production accounts:

| Role | Email | Password |
|---|---|---|
| Procurement officer | officer@bytecode.demo | officer123 |
| Auditor (read only) | auditor@bytecode.demo | auditor123 |
| Administrator | admin@bytecode.demo | admin123 |

One-click demo logins are available on the login screen. They are disabled when `DEMO_MODE=false`. Administrators can edit rules; officers and administrators can upload, process, and decide; auditors can inspect and export evidence.

## Judge walkthrough

1. Sign in as the procurement officer. Dashboard metrics, charts, queue, and activity come from the database.
2. Open **Tenders → CPCL/2026/PROC/001 — Supply of Industrial Safety Equipment → Zenith Industrial Systems Pvt. Ltd.**
3. Open **Documents** and inspect a PDF. The viewer shows the original, extracted fields with page/bounding-box references, and source comparisons.
4. Upload a sample from `make samples`, or click **Start AI review**. The frontend polls the persisted `/status` endpoint; completed stages display their actual timestamps. Uploads invalidate the current assessment and require a fresh run.
5. Open **Government Verification**. Zenith's GSTIN ends in `9`; the fictional source record ends in `5`. PAN and Udyam match. OEM authorization is absent.
6. Open **Evidence Intelligence**. Select each finding and follow the clickable document → entity → source → rule → risk → AI → officer chain. Missing documents are shown as absence evidence, without invented document IDs.
7. With the untouched seeded files and rules, Zenith produces **74.1/100 compliance**, **58/100 HIGH risk**, and **MANUAL REVIEW REQUIRED**. These values are calculated, not scenario constants. The three risk contributions are GST mismatch +18, missing OEM +22, expired experience +18.
8. Record **NEEDS CLARIFICATION**, with a reason such as: “Please provide a corrected GST certificate, current experience certificate, and valid OEM authorization.” The officer decision remains separate from the AI recommendation.
9. Open **Audit Trail**, verify the chain, and export the PDF. To demonstrate an override, choose a different final decision and provide a substantive reason.
10. Return to the dashboard; the pending-decision count reflects the action. Sign in as the demo administrator to inspect/edit a tender's JSON rules.

For a fast walkthrough, use **Demo → Multi-risk bid → Run verification**. The other scenarios are clean bid, GST mismatch, expired document, missing OEM, blacklist flag, and name variation. Scenarios run the bidder's **current stored documents**. They do not silently restore the seed or erase uploads.

## Features and implementation

- Five tenders, fifteen bids/bidder records, and **89 generated PDF documents** on a fresh seed.
- Actual PDF text extraction with PyMuPDF, image preprocessing with OpenCV, and real Tesseract OCR when needed.
- Extracted PAN, GSTIN, Udyam, CIN, company name, address, dates, certificate numbers, declared financial/local-content values, and auxiliary registration IDs.
- Text-feature document classification; identifiers carry source page, source text, extraction confidence, and bounding boxes where available.
- Eleven separate HTTPX adapters calling the mock FastAPI microservice.
- Restricted declarative tender rules. No `eval` or executable rule expressions.
- Configurable six-part compliance weights, explicit risk factors, identity matching, and an Isolation Forest advisory analysis.
- Evidence-grounded AI explanations with retrieved tender/internal-guidance references and explicit provider/fallback labels.
- Versioned processing runs, retained decision history, role enforcement, and stale-run decision rejection.
- SHA256-linked audit events and printable, paginated audit PDFs.
- Dashboard, tenders, bid creation/review, verification matrix, risk views, rule editor, and executive demo.

## Architecture

```text
React + TypeScript + Tailwind + Recharts (3000)
  └── same-origin /api → FastAPI backend (8000)
        ├── PostgreSQL: entities, evidence, runs, rules, recommendations, decisions, audit
        ├── document volume: original PDF/image files
        ├── extraction → classification → source verification → rules → risk → explanation
        ├── HTTPX adapters → mock-gov-api (8001), 11 source endpoints
        └── policy retrieval: Qdrant → FAISS → NumPy in-memory fallback
```

The backend waits for PostgreSQL and the mock service healthchecks. It does **not** depend on Qdrant being healthy. A later mock-source outage returns `SOURCE_UNAVAILABLE`, not a match, and the job can complete for officer review.

Core tables: `users`, `tenders`, `tender_rules`, `bidders`, `bids`, `documents`, `processing_runs`, `extracted_entities`, `source_verifications`, `compliance_results`, `risk_results`, `ai_recommendations`, `officer_decisions`, `audit_events`. IDs are UUID strings. Findings retain their original rule expression and evidence references.

```text
backend/
  app/api/                    auth, tenders, bids, documents, evidence, dashboard, audit, demo
  app/core/                   settings, SQLAlchemy session, JWT/password/role handling
  app/models/                 ORM schema
  app/schemas/                validated requests and restricted rule expressions
  app/repositories/           database-to-review projections
  app/services/               document storage, processing, auditing, PDF samples/reports
  app/engines/                rules, scoring, identity matching, anomaly detection
  app/adapters/government/    eleven interchangeable HTTP source adapters
  app/ai/                    extraction/OCR, classification, retrieval, LLM contracts
  app/data/risk_weights.json  explicit JSON risk contributions
  alembic/                    initial schema migration
  tests/                      unit and isolated HTTP integration tests
mock-gov-api/                  independent fictional registry and Swagger UI
frontend/src/                 React pages, shared panels, API hooks, TypeScript models
sample-docs/                  sample PDF export utility
scripts/                      launch and seed helpers
```

## What is real, optional, and deliberately simplified

The default run performs actual extraction, HTTP verification, persistence, rule evaluation, scoring, retrieval, and auditing. It needs **no LLM API key or downloaded neural weights**.

| Capability | Default operational path | Optional extension / limitation |
|---|---|---|
| PDF extraction | PyMuPDF reads the text layer first | Scanned pages go to image preprocessing and OCR |
| OCR | Tesseract for scanned content | PaddleOCR tried first when `ENABLE_HEAVY_ML=true` and installed; otherwise falls back |
| Unreadable documents | Warnings, no invented fields, manual-review findings | Seeded PDFs provide the dependable text-layer demo path; arbitrary unreadable uploads never receive fabricated demo text |
| Entity extraction | `RegexEntityExtractor` | `SpacyEntityExtractor` and `TransformerEntityExtractor` implement the same contract; optional packages/model weights must be installed and selected in the pipeline |
| Classification | `DemoDocumentClassifier` from actual text features | `LayoutLMv3DocumentClassifier` is a replacement contract with an explicitly labeled fallback; no trained LayoutLM weights are claimed |
| Company matching | Normalize “Pvt/Ltd” to “Private/Limited”, then token-sequence similarity | Cached Sentence Transformers model used when heavy ML is enabled; thresholds are environment-configurable |
| Embeddings | Deterministic hashed-token vectors, explicitly labeled | Cached `all-MiniLM-L6-v2` used if enabled/available; no background download in default mode |
| Vector store | Actual Qdrant collection, ingestion, query, then cleanup | FAISS → NumPy fallback. Run-scoped collections avoid cross-tender contamination; retrieved excerpts remain persisted with the recommendation |
| LLM | `MockLLMProvider` templates exclusively from persisted findings | OpenAI-compatible provider can select validated failed-rule citations. Deterministic text/action remain authoritative; invalid output falls back |
| Isolation Forest | Real scikit-learn estimator over seven observed features | Deterministic synthetic reference population, not trained procurement ground truth; it adds no hidden risk points |
| Government verification | Real HTTP hop to fictional deterministic source records | No actual GSTN, PAN, Udyam, EPFO, ESIC, DigiLocker, or other government connectivity |
| Audit | Application append-only hash chain; verifier checks hashes, sequence, payload, columns, timestamp | Not a blockchain, external timestamp, or protection from a privileged database administrator rewriting storage |
| Jobs | FastAPI background tasks, persisted stages/results | Single backend process for the laptop demo; restart marks abandoned jobs failed for explicit retry |

These limitations are intentional and visible. The system does not claim to certify legal eligibility or replace procurement judgment.

## Environment variables

`.env.example` documents the safe local defaults. Compose supplies internal network addresses. The standalone backend also accepts a SQLite fallback when `DATABASE_URL` is omitted; Docker always uses PostgreSQL by default.

| Variable | Purpose |
|---|---|
| `APP_ENV`, `DEMO_MODE` | Demo behavior and one-click login |
| `DATABASE_URL` | SQLAlchemy PostgreSQL (`postgresql+psycopg://...`) or optional local SQLite URL |
| `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB` | Isolated local database defaults; change for non-demo use |
| `MOCK_GOV_API_URL` | Mock service base URL; `http://mock-gov-api:8001` within Compose |
| `QDRANT_URL`, `VECTOR_PROVIDER` | Primary vector endpoint and preferred provider |
| `JWT_SECRET` | Optional in demo; a random key is generated with restrictive permissions in the data volume. Required outside demo |
| `LLM_PROVIDER`, `LLM_API_KEY`, `LLM_BASE_URL`, `LLM_MODEL` | Optional external provider; `mock` is the default |
| `OCR_PROVIDER`, `ENABLE_HEAVY_ML` | Optional neural providers; disabled by default for laptop resource use |
| `MATCH_THRESHOLD`, `REVIEW_THRESHOLD` | Default name-match boundaries 0.95 and 0.80 |
| `UPLOAD_MAX_MB`, `DATA_DIR` | Upload limit (15 MB) and backend storage root |
| `FRONTEND_PORT`, `BACKEND_PORT`, `MOCK_GOV_PORT`, `POSTGRES_PORT`, `QDRANT_PORT` | Optional host-port overrides |

Never commit `.env`, keys, database files, or uploads. Docker build contexts exclude runtime data and local environment files.

## Non-Docker application development

Python **3.11+** and Node **22+** are recommended. Install a Tesseract system binary for scanned PDF/image OCR (`brew install tesseract` on macOS; `apt install tesseract-ocr` on Debian/Ubuntu). No OCR binary is needed for the generated text-layer PDFs.

Use standalone PostgreSQL and Qdrant containers, or an existing dedicated database:

```bash
docker run --name bytecode-dev-postgres -d -p 127.0.0.1:55432:5432 \
  -e POSTGRES_USER=bytecode -e POSTGRES_PASSWORD=bytecode_local_demo -e POSTGRES_DB=bytecode postgres:16-alpine
docker run --name bytecode-dev-qdrant -d -p 127.0.0.1:6333:6333 qdrant/qdrant:v1.13.6
```

If Compose is already running PostgreSQL/Qdrant on those ports, reuse this project's containers instead of starting duplicates.

Backend terminal:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt
export DATABASE_URL=postgresql+psycopg://bytecode:bytecode_local_demo@127.0.0.1:55432/bytecode
export MOCK_GOV_API_URL=http://127.0.0.1:8001
export QDRANT_URL=http://127.0.0.1:6333
cd backend
alembic upgrade head
python -m app.seed
uvicorn app.main:app --host 127.0.0.1 --port 8010
```

For the smallest standalone fallback, omit `DATABASE_URL`; the backend creates `backend/data/bytecode.db` after migration. This is a convenience path, not a replacement for the default PostgreSQL deployment.

Mock service terminal (a separate environment/process):

```bash
cd mock-gov-api
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --host 127.0.0.1 --port 8001
```

Frontend terminal:

```bash
cd frontend
npm ci
npm run dev
```

The Vite development proxy targets backend **8010** to coexist with the other app on this machine. Update `frontend/vite.config.ts` if you use another backend port. Docker nginx targets `backend:8000` regardless of host ports.

Export seed PDFs in standalone mode with the same backend environment:

```bash
cd backend
python ../sample-docs/generate_samples.py
```

Document database locations are volume-relative. If moving an existing database to another machine, also copy its document volume; the database alone does not contain PDF/image binaries.

## API and mock adapter contract

All protected operations use an `Authorization: Bearer …` token. The frontend uses same-origin `/api`; document previews and downloads fetch authenticated blobs instead of placing tokens in URLs.

Representative endpoints:

```text
POST /api/auth/login                  POST /api/auth/demo-login
GET  /api/tenders                     POST /api/tenders
GET  /api/tenders/{id}                PUT  /api/tenders/{id}/rules
GET  /api/bids                        POST /api/bids
GET  /api/bids/{id}                   POST /api/bids/{id}/process
GET  /api/bids/{id}/status            POST /api/bids/{id}/decision
POST /api/documents/upload           GET  /api/documents/{id}/file
GET  /api/extraction/{bid_id}         GET  /api/verification/{bid_id}
GET  /api/compliance/{bid_id}         GET  /api/risk/{bid_id}
GET  /api/ai/{bid_id}                 GET  /api/audit
GET  /api/audit/export?bid_id=...     GET  /api/dashboard/summary
GET  /api/demo/scenarios             POST /api/demo/run/{scenario}
```

`/api/bids/{id}/verification`, `/compliance`, `/risk`, `/ai-summary`, and `/audit` are also available. The first four return the complete linked review projection; the focused `/api/{stage}/{bid_id}` routes return stage-specific evidence.

The mock service supports `POST /{pan,gst,udyam,itr,epfo,esic,startup,nsic,digilocker,blacklist,oem}/verify`. Each request includes `bidder_id`, `identifier`, and `company_name`. `simulate_unavailable: true` demonstrates an outage. Responses include source, status, identifier, fictional record, confidence, timestamp, evidence, and `is_mock: true`.

To replace a mock, implement `GovernmentSourceAdapter.verify` against an **actually authorized** API, with its authentication, contractual schema, and normalized result mapping. The current `HTTPMockAdapter` deliberately requires `is_mock: true`; production source labeling must be reviewed along with the new adapter. Do not remove mock labels merely because an endpoint URL changes. No government credentials are provided by this prototype.

## Scoring, risk, and audit details

Compliance weights: document completeness 20, source verification 30, tender eligibility 25, document validity 10, identity consistency 10, anomaly signals 5. Each component earns `weight × observed pass fraction`. Unknown/unreadable evidence earns no credit in the relevant check. Components and their underlying checks are shown in the UI. Scores do not themselves determine the final officer decision.

Risk points are configured in `backend/app/data/risk_weights.json`; the UI shows every contributing signal. Levels: LOW <20, MEDIUM 20–44, HIGH 45–79, CRITICAL ≥80. Scores cap at 100. The mandatory-document list and enabled JSON rules define tender-specific checks. GSTIN/PAN validation checks structure, not checksum correctness or legal validity.

The audit chain uses `SHA256(previous_hash + canonical_event_payload)` with an explicit genesis hash. Global PostgreSQL advisory locking serializes appends. Exported per-bid events can contain gaps in sequence because they are filtered from the full application chain; integrity verification always checks the full chain. Uploading new evidence invalidates the current decision but retains its historical run and audit events.

## Tests and validation

```bash
docker compose exec backend pytest -q
# or, after activating the project venv:
cd backend
pytest -q
# frontend compilation:
cd ../frontend
npm run build
```

Tests create an isolated temporary SQLite database and a **real subprocess mock HTTP service** on a free local port. They cover identifier extraction/validation, name thresholds, actual scenarios, rules/scoring, anomaly features, HTTP adapter mismatch/outage, upload validation/path safety, scanned PDF OCR, external LLM fallback, audit tampering, role restrictions, override decisions, stale evidence, admin rules, and readable audit PDFs. PostgreSQL and Qdrant are additionally checked in the Docker smoke workflow.

See `VALIDATION.md` for the final checks and any environment-specific limitations. Optional neural models are not claimed to be validated without their weights. A feature-detected, read-only WebMCP tool exposes saved evidence in supporting browsers; normal functionality does not depend on it.

## Troubleshooting

- **Port already in use:** set the relevant host-port override in `.env`. Do not stop unrelated apps. Change Vite's proxy only when changing its standalone backend target.
- **Docker registry download stalls:** check Docker Desktop/network/credential-helper health. An anonymous temporary Docker configuration can fetch public images without altering saved credentials. Base-image digests are pinned to the images tested here. Never disable TLS verification to work around certificate errors.
- **Backend health fails:** inspect `docker compose logs backend postgres`. Confirm database configuration, migrations, and storage permissions. Avoid mixing a local database connection with a container service hostname.
- **Documents unavailable after moving storage:** copy the document volume as well as the database. No document content is reconstructed from a failed upload.
- **Qdrant down:** the explanation uses FAISS or NumPy and labels the selected provider. Run `docker compose up -d qdrant` to restore it. Backend startup is independent of Qdrant.
- **Mock source down:** affected checks show `SOURCE_UNAVAILABLE` with zero confidence. Restore the source and run a new review; earlier results remain in history.
- **OCR/model unavailable:** readable PDF text still works. Tesseract is installed in the backend container. Unreadable content creates review findings, never fabricated extracted text.
- **Rule changes do not alter a saved score:** intentional. Start a new verification run to apply the new configuration.
- **A run was interrupted by restart:** it is marked failed with a retry explanation. Start another run.
- **A clean scenario gains issues after uploads:** the demo uses current stored evidence. Inspect duplicates/conflicts instead of assuming the seed was silently restored.
- **No external LLM key:** no action needed; the evidence-based explanation is the default.

## Deliberate MVP scope

Kubernetes, Kafka, MongoDB, Elasticsearch, and a real MeitY-empanelled cloud deployment belong to the official pitch's **department-scale rollout vision**, not this laptop prototype. PostgreSQL + Qdrant/FAISS and Docker Compose are an intentional MVP subset. Redis is an optional future cache. Production readiness would additionally require approved government integrations, organizational identity and authorization, durable distributed jobs, external audit retention/attestation, validated models and evaluation datasets, and a deployment/security review.
# prototype
