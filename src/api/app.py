from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path
from uuid import uuid4

try:
    from fastapi import BackgroundTasks, FastAPI, HTTPException, Request
    from fastapi.middleware.cors import CORSMiddleware
    from fastapi.responses import FileResponse
    from pydantic import ValidationError
except ImportError as exc:
    raise RuntimeError("fastapi and pydantic are required for the API app") from exc

from src.api.schemas import (
    AppConfigResponse,
    ArxivFetchCreate,
    ArtifactDeleteCreate,
    ArtifactDeleteResponse,
    FetchedPaperResponse,
    HealthResponse,
    LibraryResponse,
    LibraryRunsResponse,
    LLMRuntimeConfigResponse,
    ReviewArtifactsResponse,
    ReviewCreate,
    ReviewDiagnosticsResponse,
    ReviewLLMCallsResponse,
    ReviewJobResponse,
    ReviewJobsResponse,
    ReviewJobsSummaryResponse,
    ReviewPresetCreate,
    ReviewPresetResponse,
    ReviewPresetsResponse,
    ReviewReportResponse,
    ReviewRunResponse,
    RunDeleteCreate,
    RunDeleteResponse,
    VenueCatalogResponse,
    VenueCodesResponse,
)
from src.core.venue_catalog import VenueCatalogRepository
from src.core.venues import VenueRepository
from src.services.review_service import build_workflow
from src.services.review_service import ReviewSubmissionError
from src.core.models import OutputLanguage, ReviewMode, ReviewRequest, VenueCollection, VenueDomain
from src.core.models import to_jsonable
from src.infra.settings import load_settings
from src.services.paper_sources import PaperSourceFetchError, PaperSourceTooLargeError, fetch_arxiv_pdf
from src.services.llm_config import build_llm_runtime_config
from src.services.presets import ReviewPresetInput, build_preset_store
from src.services.review_jobs import (
    ReviewJobArtifactNotFoundError,
    ReviewJobArtifactsUnavailableError,
    ReviewJobNotCancelableError,
    ReviewJobNotFoundError,
    ReviewJobNotRetryableError,
    ReviewJobStatus,
    build_job_runner,
)


_SAFE_FILENAME_PATTERN = re.compile(r"[^A-Za-z0-9._-]+")
_FULL_REVIEW_PROGRESS_PATH = [
    "doc_parse",
    "content_check",
    "journal_req_collector",
    "field_analyst",
    "se_check",
    "ae_check",
    "review_dispatch",
    "reviewer1",
    "reviewer2",
    "reviewer3",
    "devils_advocate",
    "ae_final",
    "final_artifact_render",
]
_QUICK_REVIEW_PROGRESS_PATH = [
    "doc_parse",
    "content_check",
    "journal_req_collector",
    "field_analyst",
    "review_dispatch",
    "reviewer1",
    "reviewer2",
    "reviewer3",
    "devils_advocate",
    "ae_final",
    "final_artifact_render",
]
_SINGLE_AGENT_REVIEW_PROGRESS_PATH = [
    "doc_parse",
    "content_check",
    "journal_req_collector",
    "field_analyst",
    "single_reviewer",
    "final_artifact_render",
]


def _safe_upload_filename(filename: str) -> str:
    # 只保留 basename，并把奇怪字符收敛掉，避免浏览器上传文件名影响本地路径。
    name = Path(filename or "paper").name
    cleaned = _SAFE_FILENAME_PATTERN.sub("_", name).strip("._")
    return cleaned or "paper"


def _review_progress_path(job: dict[str, object]) -> list[str]:
    request = job.get("request") if isinstance(job.get("request"), dict) else {}
    nodes = job.get("nodes") if isinstance(job.get("nodes"), dict) else {}
    node_names = set(nodes)
    if "parse_fail_output" in node_names:
        return ["doc_parse", "parse_fail_output", "final_artifact_render"]
    if "invalid_file" in node_names:
        return ["doc_parse", "content_check", "invalid_file", "final_artifact_render"]
    if "desk_reject_output" in node_names:
        # 桌拒可能发生在 SE，也可能发生在 AE；按已经出现的节点还原实际路径。
        if "ae_check" in node_names:
            return ["doc_parse", "content_check", "journal_req_collector", "field_analyst", "se_check", "ae_check", "desk_reject_output", "final_artifact_render"]
        return ["doc_parse", "content_check", "journal_req_collector", "field_analyst", "se_check", "desk_reject_output", "final_artifact_render"]
    if request.get("review_mode") == ReviewMode.SINGLE_AGENT_REVIEW.value:
        return list(_SINGLE_AGENT_REVIEW_PROGRESS_PATH)
    if request.get("review_mode") == ReviewMode.QUICK_REVIEW.value:
        return list(_QUICK_REVIEW_PROGRESS_PATH)
    return list(_FULL_REVIEW_PROGRESS_PATH)


def _elapsed_ms(started_at: object, updated_at: object) -> float | None:
    try:
        start = datetime.fromisoformat(str(started_at))
        end = datetime.fromisoformat(str(updated_at))
    except ValueError:
        return None
    return max(0.0, (end - start).total_seconds() * 1000)


def _job_progress(job: dict[str, object]) -> dict[str, object]:
    nodes = job.get("nodes") if isinstance(job.get("nodes"), dict) else {}
    path = _review_progress_path(job)
    total_nodes = len(path)
    completed_nodes = sum(1 for name in path if isinstance(nodes.get(name), dict) and nodes[name].get("status") == "SUCCEEDED")
    status = str(job.get("status") or "")
    terminal = status in {ReviewJobStatus.SUCCEEDED.value, ReviewJobStatus.FAILED.value, ReviewJobStatus.CANCELED.value}
    # 终态 job 可能保留最后一个 RUNNING 快照；API 层要以 job.status 为准，避免前端误判还在执行。
    active_nodes = [] if terminal else [name for name in path if isinstance(nodes.get(name), dict) and nodes[name].get("status") == "RUNNING"]
    next_node = None
    if not terminal:
        next_node = next(
            (
                name
                for name in path
                if not isinstance(nodes.get(name), dict) or nodes[name].get("status") not in {"SUCCEEDED", "FAILED"}
            ),
            None,
        )
    percent = 100 if status == ReviewJobStatus.SUCCEEDED.value else round((completed_nodes / total_nodes) * 100) if total_nodes else 0
    return {
        "percent": int(max(0, min(100, percent))),
        "completed_nodes": completed_nodes,
        "total_nodes": total_nodes,
        "active_nodes": active_nodes,
        "next_node": next_node,
        "elapsed_ms": _elapsed_ms(job.get("created_at"), job.get("updated_at")),
    }


def _job_response(job: object) -> dict[str, object]:
    data = to_jsonable(job)
    data["progress"] = _job_progress(data)
    return data


def create_app():
    settings = load_settings()
    app = FastAPI(title="Paper Review Agent")
    # 默认开放本地 Vite 开发服务器；部署时用 APP_CORS_ORIGINS 指向真实前端域名。
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.api_cors_origins),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/health", response_model=HealthResponse)
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/api/config", response_model=AppConfigResponse)
    def app_config() -> dict[str, object]:
        return {
            "supported_upload_extensions": list(settings.supported_upload_extensions),
            "max_upload_bytes": settings.max_upload_bytes,
            "default_output_language": OutputLanguage.ZH.value,
            "default_review_mode": ReviewMode.FULL_REVIEW.value,
        }

    @app.get("/api/llm-config", response_model=LLMRuntimeConfigResponse)
    def llm_config() -> dict[str, object]:
        return build_llm_runtime_config(settings)

    @app.get("/api/venues", response_model=VenueCodesResponse)
    def venues() -> dict[str, object]:
        settings = load_settings()
        codes = VenueRepository(settings.venues_dir, legacy_reference_dir=settings.legacy_reference_dir).list_codes()
        return {"count": len(codes), "codes": codes}

    @app.get("/api/venue-catalog", response_model=VenueCatalogResponse)
    def venue_catalog() -> dict[str, object]:
        settings = load_settings()
        catalog = VenueCatalogRepository(settings.venues_dir)
        items = catalog.list_items()
        return {"count": len(items), "catalog": catalog.grouped()}

    @app.post("/api/paper-sources/arxiv", response_model=FetchedPaperResponse)
    def fetch_arxiv_source(payload: ArxivFetchCreate) -> dict[str, object]:
        try:
            paper = fetch_arxiv_pdf(
                payload.arxiv_id,
                uploads_dir=settings.uploads_dir,
                max_bytes=settings.max_upload_bytes,
            )
        except PaperSourceTooLargeError as exc:
            raise HTTPException(status_code=413, detail=str(exc)) from exc
        except PaperSourceFetchError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return to_jsonable(paper)

    @app.get("/api/presets", response_model=ReviewPresetsResponse)
    def list_presets(limit: int = 50) -> dict[str, object]:
        safe_limit = max(1, min(limit, 200))
        presets = build_preset_store().list(limit=safe_limit)
        return {"count": len(presets), "presets": to_jsonable(presets)}

    @app.post("/api/presets", status_code=201, response_model=ReviewPresetResponse)
    def create_preset(payload: ReviewPresetCreate) -> dict[str, object]:
        preset = build_preset_store().create(
            ReviewPresetInput(
                name=payload.name,
                review_mode=payload.review_mode,
                output_language=payload.output_language,
                venue_domain=payload.venue_domain,
                venue_collection=payload.venue_collection,
                venue_code=payload.venue_code,
            )
        )
        return to_jsonable(preset)

    def _review_request_from_payload(payload: ReviewCreate) -> ReviewRequest:
        return ReviewRequest(
            paper_path=payload.paper_path,
            review_mode=payload.review_mode,
            output_language=payload.output_language,
            venue_domain=payload.venue_domain,
            venue_collection=payload.venue_collection,
            venue_code=payload.venue_code,
        )

    def _review_request_from_form(form, saved_paper_path: Path) -> ReviewRequest:
        try:
            return ReviewRequest(
                paper_path=str(saved_paper_path),
                review_mode=ReviewMode(str(form.get("review_mode", ReviewMode.FULL_REVIEW.value))),
                output_language=OutputLanguage(str(form.get("output_language", OutputLanguage.ZH.value))),
                venue_domain=VenueDomain(str(form.get("venue_domain", ""))),
                venue_collection=VenueCollection(str(form.get("venue_collection", ""))),
                venue_code=str(form.get("venue_code", "")),
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=f"invalid review option: {exc}") from exc

    async def _review_request_from_upload(request: Request) -> ReviewRequest:
        form = await request.form()
        upload = form.get("paper")
        if upload is None or not hasattr(upload, "filename") or not hasattr(upload, "read"):
            raise HTTPException(status_code=400, detail="paper file is required")

        filename = _safe_upload_filename(str(upload.filename))
        if Path(filename).suffix.lower() not in settings.supported_upload_extensions:
            await upload.close()
            raise HTTPException(status_code=400, detail=f"unsupported file extension: {Path(filename).suffix or '(none)'}")
        target = settings.uploads_dir / f"{uuid4().hex}_{filename}"
        target.parent.mkdir(parents=True, exist_ok=True)
        # V1 先把浏览器上传稿件落到本地 data/uploads，再复用原来的 ReviewWorkflow。
        try:
            content = await upload.read()
        finally:
            await upload.close()
        if len(content) > settings.max_upload_bytes:
            raise HTTPException(status_code=413, detail=f"file is too large: max {settings.max_upload_bytes} bytes")
        target.write_bytes(content)
        return _review_request_from_form(form, target)

    async def _review_request_from_json(request: Request) -> ReviewRequest:
        try:
            payload = ReviewCreate(**await request.json())
        except ValidationError as exc:
            raise HTTPException(status_code=422, detail=exc.errors()) from exc
        return _review_request_from_payload(payload)

    def _run_review(review_request: ReviewRequest) -> dict[str, object]:
        path = Path(review_request.paper_path)
        if not path.exists():
            raise HTTPException(status_code=400, detail=f"paper_path does not exist: {path}")
        workflow = build_workflow()
        try:
            run = workflow.run(review_request)
        except ReviewSubmissionError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return to_jsonable(run)

    @app.post("/api/reviews", response_model=ReviewRunResponse)
    async def create_review(request: Request) -> dict[str, object]:
        content_type = request.headers.get("content-type", "").split(";", 1)[0].lower()
        if content_type == "multipart/form-data":
            return _run_review(await _review_request_from_upload(request))
        if content_type in {"application/json", ""}:
            return _run_review(await _review_request_from_json(request))
        raise HTTPException(status_code=415, detail=f"unsupported content type: {content_type}")

    @app.post("/api/jobs", status_code=202, response_model=ReviewJobResponse)
    async def create_job(request: Request, background_tasks: BackgroundTasks) -> dict[str, object]:
        content_type = request.headers.get("content-type", "").split(";", 1)[0].lower()
        if content_type == "multipart/form-data":
            review_request = await _review_request_from_upload(request)
        elif content_type in {"application/json", ""}:
            review_request = await _review_request_from_json(request)
        else:
            raise HTTPException(status_code=415, detail=f"unsupported content type: {content_type}")

        runner = build_job_runner()
        job = runner.create_job(review_request)
        background_tasks.add_task(runner.run_job, job.job_id)
        return _job_response(job)

    def _job_status_filter(status: str = "ALL") -> set[ReviewJobStatus] | None:
        normalized = status.strip().upper()
        if normalized in {"", "ALL"}:
            return None
        if normalized == "ACTIVE":
            return {ReviewJobStatus.QUEUED, ReviewJobStatus.RUNNING}
        try:
            return {ReviewJobStatus(normalized)}
        except ValueError as exc:
            allowed = "ALL, ACTIVE, QUEUED, RUNNING, SUCCEEDED, FAILED, CANCELED"
            raise HTTPException(status_code=400, detail=f"invalid job status filter: {status}. Allowed: {allowed}") from exc

    @app.get("/api/jobs", response_model=ReviewJobsResponse)
    def list_jobs(limit: int = 50, status: str = "ALL", q: str = "") -> dict[str, object]:
        safe_limit = max(1, min(limit, 200))
        jobs = build_job_runner().list_jobs(limit=safe_limit, statuses=_job_status_filter(status), query=q)
        return {"count": len(jobs), "jobs": [_job_response(job) for job in jobs]}

    @app.get("/api/jobs/summary", response_model=ReviewJobsSummaryResponse)
    def jobs_summary() -> dict[str, object]:
        return to_jsonable(build_job_runner().summarize_jobs(limit=200))

    @app.get("/api/library", response_model=LibraryResponse)
    def library_artifacts(limit: int = 100) -> dict[str, object]:
        safe_limit = max(1, min(limit, 200))
        artifacts = build_job_runner().list_library_artifacts(limit=safe_limit)
        return {"count": len(artifacts), "artifacts": to_jsonable(artifacts)}

    @app.get("/api/library/runs", response_model=LibraryRunsResponse)
    def library_runs(limit: int = 100) -> dict[str, object]:
        safe_limit = max(1, min(limit, 200))
        runs = build_job_runner().list_library_runs(limit=safe_limit)
        return {
            "count": len(runs),
            "artifact_count": sum(int(run["artifact_count"]) for run in runs),
            "runs": to_jsonable(runs),
        }

    @app.delete("/api/library/runs", response_model=RunDeleteResponse)
    def delete_library_runs(payload: RunDeleteCreate) -> dict[str, object]:
        if not payload.job_ids:
            return {"deleted_count": 0, "error_count": 0, "deleted": [], "errors": []}
        runner = build_job_runner()
        return runner.delete_jobs(payload.job_ids)

    @app.delete("/api/library/artifacts", response_model=ArtifactDeleteResponse)
    def delete_library_artifacts(payload: ArtifactDeleteCreate) -> dict[str, object]:
        if not payload.artifacts:
            return {"deleted_count": 0, "error_count": 0, "deleted": [], "errors": []}
        runner = build_job_runner()
        return runner.delete_artifacts([item.model_dump() for item in payload.artifacts])

    @app.get("/api/jobs/{job_id}", response_model=ReviewJobResponse)
    def get_job(job_id: str) -> dict[str, object]:
        runner = build_job_runner()
        try:
            return _job_response(runner.get_job(job_id))
        except ReviewJobNotFoundError as exc:
            raise HTTPException(status_code=404, detail=f"job not found: {job_id}") from exc

    @app.post("/api/jobs/{job_id}/cancel", response_model=ReviewJobResponse)
    def cancel_job(job_id: str) -> dict[str, object]:
        runner = build_job_runner()
        try:
            return _job_response(runner.cancel_job(job_id))
        except ReviewJobNotFoundError as exc:
            raise HTTPException(status_code=404, detail=f"job not found: {job_id}") from exc
        except ReviewJobNotCancelableError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @app.post("/api/jobs/{job_id}/retry", status_code=202, response_model=ReviewJobResponse)
    def retry_job(job_id: str, background_tasks: BackgroundTasks) -> dict[str, object]:
        runner = build_job_runner()
        try:
            job = runner.retry_job(job_id)
        except ReviewJobNotFoundError as exc:
            raise HTTPException(status_code=404, detail=f"job not found: {job_id}") from exc
        except ReviewJobNotRetryableError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        background_tasks.add_task(runner.run_job, job.job_id)
        return _job_response(job)

    @app.get("/api/jobs/{job_id}/artifacts", response_model=ReviewArtifactsResponse)
    def get_job_artifacts(job_id: str) -> dict[str, object]:
        runner = build_job_runner()
        try:
            return {"job_id": job_id, "artifacts": runner.list_artifacts(job_id)}
        except ReviewJobNotFoundError as exc:
            raise HTTPException(status_code=404, detail=f"job not found: {job_id}") from exc
        except ReviewJobArtifactsUnavailableError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except ReviewJobArtifactNotFoundError as exc:
            raise HTTPException(status_code=404, detail=f"artifact not found: {exc}") from exc

    @app.get("/api/jobs/{job_id}/report", response_model=ReviewReportResponse)
    def get_job_report(job_id: str) -> dict[str, object]:
        runner = build_job_runner()
        try:
            return {"job_id": job_id, **runner.read_report(job_id)}
        except ReviewJobNotFoundError as exc:
            raise HTTPException(status_code=404, detail=f"job not found: {job_id}") from exc
        except ReviewJobArtifactsUnavailableError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except ReviewJobArtifactNotFoundError as exc:
            raise HTTPException(status_code=404, detail=f"artifact not found: {exc}") from exc

    @app.get("/api/jobs/{job_id}/diagnostics", response_model=ReviewDiagnosticsResponse)
    def get_job_diagnostics(job_id: str) -> dict[str, object]:
        runner = build_job_runner()
        try:
            return {"job_id": job_id, "diagnostics": runner.read_diagnostics(job_id)}
        except ReviewJobNotFoundError as exc:
            raise HTTPException(status_code=404, detail=f"job not found: {job_id}") from exc
        except ReviewJobArtifactsUnavailableError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except ReviewJobArtifactNotFoundError as exc:
            raise HTTPException(status_code=404, detail=f"artifact not found: {exc}") from exc

    @app.get("/api/jobs/{job_id}/llm-calls", response_model=ReviewLLMCallsResponse)
    def get_job_llm_calls(job_id: str) -> dict[str, object]:
        runner = build_job_runner()
        try:
            events = runner.read_llm_calls(job_id)
            return {"job_id": job_id, "count": len(events), "events": events}
        except ReviewJobNotFoundError as exc:
            raise HTTPException(status_code=404, detail=f"job not found: {job_id}") from exc
        except ReviewJobArtifactsUnavailableError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except ReviewJobArtifactNotFoundError as exc:
            raise HTTPException(status_code=404, detail=f"artifact not found: {exc}") from exc

    @app.get("/api/jobs/{job_id}/artifacts/{artifact_name}")
    def download_job_artifact(job_id: str, artifact_name: str) -> FileResponse:
        runner = build_job_runner()
        try:
            path = runner.artifact_path(job_id, artifact_name)
        except ReviewJobNotFoundError as exc:
            raise HTTPException(status_code=404, detail=f"job not found: {job_id}") from exc
        except ReviewJobArtifactsUnavailableError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except ReviewJobArtifactNotFoundError as exc:
            raise HTTPException(status_code=404, detail=f"artifact not found: {exc}") from exc
        return FileResponse(
            path=path,
            media_type="application/octet-stream",
            filename=path.name,
        )

    @app.delete("/api/jobs/{job_id}/artifacts/{artifact_name}", response_model=ArtifactDeleteResponse)
    def delete_job_artifact(job_id: str, artifact_name: str) -> dict[str, object]:
        runner = build_job_runner()
        try:
            deleted = runner.delete_artifact(job_id, artifact_name)
            return {"deleted_count": 1, "error_count": 0, "deleted": [deleted], "errors": []}
        except ReviewJobNotFoundError as exc:
            raise HTTPException(status_code=404, detail=f"job not found: {job_id}") from exc
        except ReviewJobArtifactsUnavailableError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except ReviewJobArtifactNotFoundError as exc:
            raise HTTPException(status_code=404, detail=f"artifact not found: {exc}") from exc

    return app


app = create_app()
