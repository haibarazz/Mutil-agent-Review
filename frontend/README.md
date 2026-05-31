# Frontend

React/Vite/TypeScript frontend for the multi-agent paper review workbench.

The first screen ports Claude's selected **Home B** design into a real app:

- manuscript upload surface;
- full / quick review mode switch;
- CS / IS domain switch;
- upload file rules backed by `GET /api/config`;
- venue picker backed by `GET /api/venue-catalog`;
- the Venues view browses and filters the same backend catalog, then sends a selected venue back to the Workbench;
- `Begin Review` creates a local async job through `POST /api/jobs`, then polls `GET /api/jobs/{job_id}`;
- the agent roster rail maps job node progress to visible RUN / OK / ERR status marks;
- completed jobs fetch `GET /api/jobs/{job_id}/artifacts` and `GET /api/jobs/{job_id}/report` for artifact count, report preview, direct report opening, and final report download;
- the Runs view fetches `GET /api/jobs`, opens completed reports or failed partial reports, and downloads artifacts through `GET /api/jobs/{job_id}/artifacts/{artifact_name}`;
- the Library view fetches `GET /api/library` to browse generated artifacts across completed and failed local runs;
- the Report detail view opens a run through `#report=<job_id>`, renders the Markdown report or partial report, shows diagnostics, and keeps artifact downloads available;
- the Settings view shows API base, backend health, upload contract, OpenAPI contract summary, defaults, and catalog count;
- agent roster rail matching the B design direction.

## Development

Start the FastAPI backend first:

```bash
scripts/dev-backend.sh
```

Then start the frontend:

```bash
scripts/dev-frontend.sh
```

For local development, both services can be started with `scripts/dev-fullstack.sh`.

By default, local development uses the Vite proxy in `vite.config.ts`. For a
strictly separated frontend/backend setup, copy `frontend/.env.example` to
`frontend/.env.local` and set:

```bash
VITE_API_BASE_URL=http://127.0.0.1:8000
```

Open:

```text
http://127.0.0.1:5173
```

## Verification

```bash
cd frontend
npm run build
```

To run the browser smoke path that uploads a small manuscript, starts a review
job, and verifies the completed Workbench actions:

```bash
scripts/check-frontend-smoke.sh
```

To verify the failed-run path, including Runs Preview and Report detail loading
`partial_report.md`:

```bash
scripts/check-frontend-failure-smoke.sh
```

## Docker

The frontend image builds the Vite app and serves it through nginx:

```bash
docker compose up --build frontend
```

Open `http://127.0.0.1:8080`. The nginx config proxies `/api/*`, `/health`,
and `/openapi.json` to the backend service, so the browser can use the same
frontend API client without a hardcoded Docker-only base URL.
