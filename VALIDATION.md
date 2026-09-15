# Validation record

Validated on 15 September 2026 in the local workspace. This is a fictional, local demonstration, not production authorization or government verification.

## Passing checks

- `docker compose up -d --build --wait --wait-timeout 90` completed successfully with the normal Docker configuration after pinning the downloaded base-image digests.
- All five services report healthy: frontend, backend, mock-gov-api, PostgreSQL, Qdrant.
- PostgreSQL migration is at `0001 (head)`; idempotent seeding succeeds.
- Live database contains 5 tenders, 15 bidders/bids, and 89 documents.
- Backend Swagger, ReDoc, health, and OpenAPI endpoints respond successfully. Mock-source Swagger/ReDoc and Qdrant dashboard respond successfully.
- `npm run build` passes TypeScript and Vite production compilation. Dashboard is split into a separate bundle.
- `pytest -q`: **33 passed** on the host and **33 passed** inside the Python 3.11 backend container. The container run reported two third-party deprecation warnings (Starlette's HTTPX/AnyIO compatibility); no test failures.
- Every seeded bid was processed against the real Docker PostgreSQL, mock HTTP microservice, and Qdrant services using `scripts/smoke.py`.
- Warm Docker processing times observed: approximately **0.22–0.88 seconds per seeded bid**. Cold startup, OCR input, external providers, and machine load can increase times.
- Zenith: **74.1/100 compliance**, **58/100 HIGH risk**, three findings (GST mismatch, missing OEM, expired experience), **MANUAL REVIEW REQUIRED**.
- Clean and name-variation scenarios: **100/100**, **LOW risk**. Blacklist scenario: **CRITICAL risk**. All results derive from actual stored documents/source records.
- Zenith's example officer decision **NEEDS CLARIFICATION** is saved separately from its AI recommendation, with a substantive reason, reviewer, timestamp, and linked audit events.
- Full application audit chain verifies. The latest exported Zenith PDF contains 17 pages, including the retained development/processing history; filtered audit sequences can have gaps.
- Audit export was rendered and visually inspected across all pages. Rule headings were kept with their descriptions to prevent orphan headings. A representative generated GST sample was rendered and visually inspected.
- All 89 sample PDFs were exported to `sample-docs/generated` for live uploads.
- Authenticated document retrieval and focused extraction/verification/compliance/risk/AI endpoints pass HTTP checks.
- Browser: one-click officer login and the dashboard were opened and visually inspected in native Chrome. Live counts, charts, queue, mock-source labels, and audit state rendered successfully.

## Test coverage

Identifier extraction and provenance; PAN/GSTIN structural validation; exact similarity threshold boundaries; text classification; declarative source rules; transparent scoring; Isolation Forest features; real scanned-PDF Tesseract OCR; malformed PDF handling; source mismatch and outage handling; external LLM fallback; upload size/type/signature/path safety; authentication and auditor restrictions; required reasons; officer overrides; stale-run protection; retained decision history after uploads; administrative rule validation; audit hash/payload/column tamper detection; PDF generation and content.

## Explicit limits of validation

- No claim of a complete automated browser suite, all-device visual coverage, or a captured clean browser console. The remaining interaction logic is covered through the compiled frontend and backend integration tests; only login/dashboard were directly inspected in the browser.
- Optional PaddleOCR, spaCy, Transformer NER, trained LayoutLM, and Sentence Transformer neural weights were not installed/tested. Default Tesseract/regex/text-classifier/hashed-token fallback paths are operational and labeled.
- External model success was not tested with a real API key; evidence-preserving failure fallback was tested. Default explanations work without keys.
- Qdrant retrieval was exercised in the Docker smoke run; the isolated tests use FAISS fallback. NumPy is a final emergency fallback, not a separately benchmarked production vector store.
- Browser WebMCP support was unavailable for a structured contract test. The optional read-only tool is feature-detected; no WebMCP verification is claimed.
- Hash chaining is application-level tamper evidence, not an independently anchored immutable ledger.
- No live government service, production procurement decision, deployment to a cloud provider, or external communication occurred.

## Running services on this machine

- App: http://localhost:3000
- Backend docs: http://localhost:8010/docs
- Mock-source docs: http://localhost:8011/docs
- Qdrant: http://localhost:6333/dashboard
- Dedicated PostgreSQL: localhost:55432

Ports 8000 and 5432 were already occupied by unrelated local services and were left intact. The ignored `.env` stores this project's host-port overrides. The temporary standalone development processes were stopped; the five Docker services remain running.
