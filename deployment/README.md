# Vercel deployment

Target: `nandankabras-projects/bytecode-verify`.

`Dockerfile.vercel` packages React, FastAPI, Tesseract OCR, and the fictional source microservice. Vercel serves one public HTTP port. The mock service only listens on container loopback. Hosted retrieval uses the existing FAISS fallback; the local Compose deployment retains Qdrant.

PostgreSQL stores the review records **and original document bytes** in `document_contents`. The local container filesystem is only a cache. Uploaded originals are restored from PostgreSQL and checked against their SHA256 when a new instance needs them. The local Docker Compose workflow keeps its existing filesystem storage.

Hosted requests remain active until processing finishes. Starting an additional instance does not cancel another instance's active job. Jobs older than 15 minutes are marked failed on startup so they can be retried. The hosted upload limit is 4 MB per file to remain below Vercel's request limit; the local workflow remains at 15 MB.

## Required configuration

- A Neon PostgreSQL database connected to the Vercel project, providing `DATABASE_URL`.
- A stable secret `JWT_SECRET` in the production environment.
- `PORT=8000` in the production environment, matching the container listener.
- `HOSTED_MODE=true`, `DOCUMENT_STORAGE=database`, `DEMO_MODE=true`, and `UPLOAD_MAX_MB=4` (the image supplies hosted defaults, except `DEMO_MODE` defaults in application settings).

Database provisioning uses the free Neon plan. Its Marketplace terms must be accepted by the account owner before provisioning can complete. No live deployment has been claimed until the deployment and HTTP checks succeed.

## Release sequence

1. Accept the Neon integration terms in Vercel, then finish provisioning and connect the database to this project.
2. Configure the stable signing secret and `PORT`. Never commit environment files or credentials.
3. Pull production environment values into an ignored file under `output/`.
4. Run `.venv/bin/python deployment/initialize_cloud.py output/vercel.production.env`. This applies additive migrations through `0002` and seeds fictional records. A PostgreSQL advisory lock serializes initializers.
5. Deploy with `vercel deploy --prod --scope nandankabras-projects --global-config output/vercel-auth`.
6. Sign in through the deployed API, call `POST /api/demo/initialize` once to assess previously unprocessed seeded bids, then verify the dashboard, Zenith scenario, original PDFs, decisions, and audit export.

The project-specific CLI login is stored under ignored `output/vercel-auth`, preserving the computer's existing default Vercel account. `.vercelignore` excludes credentials, runtime data, and the recorded video while explicitly retaining the fictional source registry and risk configuration.

## Validation

- 36 tests passed locally and inside the deployment container.
- The complete container ran against an isolated PostgreSQL database.
- All 15 seeded bids processed through actual HTTP source checks.
- Zenith returned 74.1 compliance and HIGH risk at 58 points.
- Original PDFs were recovered from PostgreSQL after initialization in a separate container.
- An officer clarification decision and verified audit chain were saved.
