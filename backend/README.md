# Backend Placeholder

The backend implementation lives under `src/` and is served through FastAPI:

- `src/api/`: FastAPI app and routes
- `src/services/`: application services
- `src/graphs/`: LangGraph review workflow
- `src/core/`: domain models, prompts, venues
- `src/infra/`: parser, LLM, storage, settings

## Development

```bash
scripts/dev-backend.sh
```

Configure browser origins with `APP_CORS_ORIGINS`:

```bash
APP_CORS_ORIGINS=http://127.0.0.1:5173,http://localhost:5173
```

Configure the upload contract shared with the frontend:

```bash
APP_SUPPORTED_UPLOAD_EXTENSIONS=.pdf,.md,.tex
APP_MAX_UPLOAD_BYTES=83886080
```

Current frontend-facing endpoints:

- `GET /health`
- `GET /api/config`
  - Returns frontend-facing upload limits and default review options.
- `GET /api/venues`
- `GET /api/venue-catalog`
- `POST /api/reviews`
  - JSON: keeps the CLI-style local `paper_path` contract.
  - Multipart: browser upload with `paper`, `review_mode`, `output_language`, `venue_domain`, `venue_collection`, and `venue_code`.
- `POST /api/jobs`
  - Creates an artifact-backed local review job and starts the workflow in the background.
- `GET /api/jobs`
  - Lists local review job history for the frontend Runs view.
- `GET /api/library`
  - Lists generated artifacts across completed jobs for the frontend Library view.
- `GET /api/jobs/{job_id}`
  - Returns queued / running / succeeded / failed status, node-level progress, and final run metadata when available.
- `GET /api/jobs/{job_id}/artifacts`
  - Lists generated artifacts such as `final_report.md`, JSON diagnostics, and intermediate outputs.
- `GET /api/jobs/{job_id}/artifacts/{artifact_name}`
  - Downloads a generated artifact file by artifact filename.
- `GET /api/jobs/{job_id}/report`
  - Returns the rendered Markdown review report for frontend preview / future report pages.

The frontend-facing JSON routes use Pydantic response models in
`src/api/schemas.py`. The exported contract lives at
`docs/api/openapi.json` and can be refreshed with `scripts/export-openapi.sh`.

This folder is reserved for future deployment-facing backend files such as
Docker Compose profiles, reverse-proxy configs, or backend-specific operations
notes.

## Docker

The backend image is defined by the root [Dockerfile](../Dockerfile). In
Compose, the service is exposed on `127.0.0.1:8000` and persists local runs
through the repository `data/` bind mount.
