from __future__ import annotations

import json
import mimetypes
import shutil
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Callable
from urllib.parse import quote
from uuid import uuid4

from src.core.errors import ReviewAgentError
from src.core.models import FinalDecision, OutputLanguage, ReviewMode, ReviewRequest, VenueCollection, VenueDomain
from src.core.models import to_jsonable
from src.infra.settings import Settings, load_settings
from src.services.review_service import ReviewSubmissionError, ReviewWorkflow, build_workflow


class ReviewJobStatus(str, Enum):
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    CANCELED = "CANCELED"


class ReviewJobNotFoundError(KeyError):
    pass


class ReviewJobArtifactsUnavailableError(RuntimeError):
    pass


class ReviewJobArtifactNotFoundError(FileNotFoundError):
    pass


class ReviewJobNotCancelableError(RuntimeError):
    pass


class ReviewJobNotRetryableError(RuntimeError):
    pass


class ReviewJobNotDeletableError(RuntimeError):
    pass


class ReviewJobCanceledError(RuntimeError):
    pass


@dataclass(frozen=True)
class ReviewJobSnapshot:
    job_id: str
    status: ReviewJobStatus
    request: ReviewRequest
    created_at: str
    updated_at: str
    run_id: str = ""
    artifact_dir: str = ""
    final_decision: FinalDecision | None = None
    nodes: dict[str, dict[str, Any]] = field(default_factory=dict)
    node_events: list[dict[str, Any]] = field(default_factory=list)
    error: dict[str, Any] | None = None


class LocalReviewJobStore:
    def __init__(self, root: Path) -> None:
        self.root = root
        self._lock = threading.RLock()

    def create(self, request: ReviewRequest) -> ReviewJobSnapshot:
        now = _utc_now()
        snapshot = ReviewJobSnapshot(
            job_id=uuid4().hex,
            status=ReviewJobStatus.QUEUED,
            request=request,
            created_at=now,
            updated_at=now,
        )
        return self.write(snapshot)

    def get(self, job_id: str) -> ReviewJobSnapshot:
        with self._lock:
            path = self._path(job_id)
            if not path.exists():
                raise ReviewJobNotFoundError(job_id)
            return _snapshot_from_dict(json.loads(path.read_text(encoding="utf-8")))

    def list(
        self,
        limit: int = 50,
        statuses: set[ReviewJobStatus] | None = None,
        query: str = "",
    ) -> list[ReviewJobSnapshot]:
        with self._lock:
            if not self.root.exists():
                return []
            jobs: list[ReviewJobSnapshot] = []
            for path in self.root.glob("*.json"):
                if path.is_file():
                    snapshot = _snapshot_from_dict(json.loads(path.read_text(encoding="utf-8")))
                    if (statuses is None or snapshot.status in statuses) and _job_matches_query(snapshot, query):
                        jobs.append(snapshot)
            jobs.sort(key=lambda job: job.updated_at, reverse=True)
            return jobs[:limit]

    def write(self, snapshot: ReviewJobSnapshot) -> ReviewJobSnapshot:
        with self._lock:
            self.root.mkdir(parents=True, exist_ok=True)
            self._path(snapshot.job_id).write_text(
                json.dumps(to_jsonable(snapshot), ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            return snapshot

    def delete(self, job_id: str) -> None:
        with self._lock:
            path = self._path(job_id)
            if not path.exists():
                raise ReviewJobNotFoundError(job_id)
            path.unlink()

    def update(self, job_id: str, *, status: ReviewJobStatus, **changes: Any) -> ReviewJobSnapshot:
        with self._lock:
            current = self.get(job_id)
            snapshot = ReviewJobSnapshot(
                job_id=current.job_id,
                status=status,
                request=current.request,
                created_at=current.created_at,
                updated_at=_utc_now(),
                run_id=str(changes.get("run_id", current.run_id)),
                artifact_dir=str(changes.get("artifact_dir", current.artifact_dir)),
                final_decision=changes.get("final_decision", current.final_decision),
                nodes=changes.get("nodes", current.nodes),
                node_events=changes.get("node_events", current.node_events),
                error=changes.get("error", current.error),
            )
            return self.write(snapshot)

    def append_node_event(self, job_id: str, event: dict[str, Any]) -> ReviewJobSnapshot:
        with self._lock:
            current = self.get(job_id)
            nodes = dict(current.nodes or {})
            node_events = list(current.node_events or [])
            normalized = _normalize_node_event(event)
            node_events.append(normalized)

            node_name = normalized["node"]
            previous = dict(nodes.get(node_name, {}))
            status = _node_status_from_event(normalized["event"])
            updated = {
                **previous,
                "node": node_name,
                "status": status,
                "updated_at": normalized["timestamp"],
            }
            if normalized["event"] == "start":
                updated.setdefault("started_at", normalized["timestamp"])
            if normalized["event"] in {"done", "error"}:
                updated["finished_at"] = normalized["timestamp"]
            if "elapsed_ms" in normalized:
                updated["elapsed_ms"] = normalized["elapsed_ms"]
            if "error_type" in normalized:
                updated["error_type"] = normalized["error_type"]

            nodes[node_name] = updated
            return self.update(job_id, status=current.status, nodes=nodes, node_events=node_events)

    def _path(self, job_id: str) -> Path:
        # job_id 只作为本地文件名使用，收敛为 uuid 风格字符，避免路径穿越。
        safe_job_id = "".join(ch for ch in job_id if ch.isalnum() or ch in {"-", "_"})
        return self.root / f"{safe_job_id}.json"


class ReviewJobRunner:
    def __init__(
        self,
        *,
        store: LocalReviewJobStore,
        workflow_factory: Callable[[], ReviewWorkflow] = build_workflow,
    ) -> None:
        self.store = store
        self.workflow_factory = workflow_factory

    def create_job(self, request: ReviewRequest) -> ReviewJobSnapshot:
        return self.store.create(request)

    def get_job(self, job_id: str) -> ReviewJobSnapshot:
        return self.store.get(job_id)

    def list_jobs(
        self,
        limit: int = 50,
        statuses: set[ReviewJobStatus] | None = None,
        query: str = "",
    ) -> list[ReviewJobSnapshot]:
        return self.store.list(limit=limit, statuses=statuses, query=query)

    def summarize_jobs(self, limit: int = 200) -> dict[str, Any]:
        jobs = self.list_jobs(limit=limit)
        counts = {status.value: 0 for status in ReviewJobStatus}
        for job in jobs:
            counts[job.status.value] += 1
        latest = jobs[0] if jobs else None
        # 顶部状态栏只需要轻量汇总，避免前端为了一个数字反复拉完整历史列表。
        return {
            "count": len(jobs),
            "active_count": counts[ReviewJobStatus.QUEUED.value] + counts[ReviewJobStatus.RUNNING.value],
            "queued_count": counts[ReviewJobStatus.QUEUED.value],
            "running_count": counts[ReviewJobStatus.RUNNING.value],
            "succeeded_count": counts[ReviewJobStatus.SUCCEEDED.value],
            "failed_count": counts[ReviewJobStatus.FAILED.value],
            "canceled_count": counts[ReviewJobStatus.CANCELED.value],
            "latest_job_id": latest.job_id if latest else "",
            "latest_status": latest.status if latest else None,
            "updated_at": latest.updated_at if latest else "",
        }

    def cancel_job(self, job_id: str) -> ReviewJobSnapshot:
        job = self.get_job(job_id)
        if job.status in {ReviewJobStatus.SUCCEEDED, ReviewJobStatus.FAILED, ReviewJobStatus.CANCELED}:
            raise ReviewJobNotCancelableError(f"job is already finished: {job.status.value}")
        return self.store.update(job_id, status=ReviewJobStatus.CANCELED, error=_canceled_error_payload())

    def retry_job(self, job_id: str) -> ReviewJobSnapshot:
        source = self.get_job(job_id)
        if source.status in {ReviewJobStatus.QUEUED, ReviewJobStatus.RUNNING}:
            raise ReviewJobNotRetryableError(f"job is still active: {source.status.value}")
        return self.create_job(source.request)

    def list_library_artifacts(self, limit: int = 50) -> list[dict[str, Any]]:
        artifacts: list[dict[str, Any]] = []
        for job in self.list_jobs(limit=limit):
            if len(artifacts) >= limit:
                break
            if job.status not in {ReviewJobStatus.SUCCEEDED, ReviewJobStatus.FAILED} or not job.artifact_dir:
                continue
            try:
                job_artifacts = self.list_artifacts(job.job_id)
            except (ReviewJobArtifactsUnavailableError, ReviewJobArtifactNotFoundError):
                # Library 是本地产物索引：单个旧 run 的产物丢失时跳过，不影响整页可用。
                continue
            for artifact in job_artifacts:
                artifacts.append(
                    {
                        **artifact,
                        "job_id": job.job_id,
                        "job_status": job.status,
                        "run_id": job.run_id,
                        "paper_path": job.request.paper_path,
                        "venue_domain": job.request.venue_domain,
                        "venue_collection": job.request.venue_collection,
                        "venue_code": job.request.venue_code,
                        "review_mode": job.request.review_mode,
                        "output_language": job.request.output_language,
                        "final_decision": job.final_decision,
                        "updated_at": job.updated_at,
                        "download_url": f"/api/jobs/{job.job_id}/artifacts/{quote(str(artifact['name']))}",
                    }
                )
                if len(artifacts) >= limit:
                    break
        return artifacts

    def list_library_runs(self, limit: int = 50) -> list[dict[str, Any]]:
        runs: list[dict[str, Any]] = []
        for job in self.list_jobs(limit=limit):
            if job.status not in {ReviewJobStatus.SUCCEEDED, ReviewJobStatus.FAILED} or not job.artifact_dir:
                continue
            try:
                artifacts = self.list_artifacts(job.job_id)
            except (ReviewJobArtifactsUnavailableError, ReviewJobArtifactNotFoundError):
                # Library 主视图按 run 聚合；旧 run 的产物目录损坏时跳过，避免整页失败。
                continue

            artifact_items = [
                {
                    **artifact,
                    "download_url": f"/api/jobs/{job.job_id}/artifacts/{quote(str(artifact['name']))}",
                }
                for artifact in artifacts
            ]
            primary_report = _primary_report_artifact(artifact_items)
            runs.append(
                {
                    "job_id": job.job_id,
                    "job_status": job.status,
                    "run_id": job.run_id,
                    "paper_path": job.request.paper_path,
                    "venue_domain": job.request.venue_domain,
                    "venue_collection": job.request.venue_collection,
                    "venue_code": job.request.venue_code,
                    "review_mode": job.request.review_mode,
                    "output_language": job.request.output_language,
                    "final_decision": job.final_decision,
                    "created_at": job.created_at,
                    "updated_at": job.updated_at,
                    "artifact_count": len(artifact_items),
                    "report_count": sum(1 for artifact in artifact_items if _is_report_artifact(str(artifact["name"]))),
                    "total_size_bytes": sum(int(artifact["size_bytes"]) for artifact in artifact_items),
                    "primary_report_name": str(primary_report.get("name", "")) if primary_report else "",
                    "primary_report_download_url": str(primary_report.get("download_url", "")) if primary_report else "",
                    "artifacts": artifact_items,
                }
            )
            if len(runs) >= limit:
                break
        return runs

    def list_artifacts(self, job_id: str) -> list[dict[str, Any]]:
        artifact_dir = _artifact_dir_for(self.get_job(job_id))
        artifacts: list[dict[str, Any]] = []
        for path in sorted(artifact_dir.iterdir(), key=lambda item: item.name):
            if path.is_file():
                artifacts.append(
                    {
                        "name": path.name,
                        "size_bytes": path.stat().st_size,
                        "content_type": mimetypes.guess_type(path.name)[0] or "application/octet-stream",
                    }
                )
        return artifacts

    def artifact_path(self, job_id: str, artifact_name: str) -> Path:
        artifact_dir = _artifact_dir_for(self.get_job(job_id))
        # 前端只能按 artifact 文件名下载，避免把本地任意路径暴露成下载接口。
        if artifact_name != Path(artifact_name).name or artifact_name in {"", ".", ".."}:
            raise ReviewJobArtifactNotFoundError(artifact_name)
        path = artifact_dir / artifact_name
        if not path.exists() or not path.is_file():
            raise ReviewJobArtifactNotFoundError(artifact_name)
        return path

    def delete_artifact(self, job_id: str, artifact_name: str) -> dict[str, Any]:
        path = self.artifact_path(job_id, artifact_name)
        path.unlink()
        return {"job_id": job_id, "name": artifact_name, "deleted": True}

    def delete_artifacts(self, items: list[dict[str, str]]) -> dict[str, Any]:
        deleted: list[dict[str, Any]] = []
        errors: list[dict[str, Any]] = []
        for item in items:
            job_id = str(item.get("job_id", ""))
            artifact_name = str(item.get("name", ""))
            try:
                deleted.append(self.delete_artifact(job_id, artifact_name))
            except Exception as exc:
                # 批量删除尽量完成其它文件；失败项返回给前端展示，不中断整个请求。
                errors.append(
                    {
                        "job_id": job_id,
                        "name": artifact_name,
                        "error_type": exc.__class__.__name__,
                        "message": str(exc),
                    }
                )
        return {"deleted_count": len(deleted), "error_count": len(errors), "deleted": deleted, "errors": errors}

    def delete_job(self, job_id: str) -> dict[str, Any]:
        job = self.get_job(job_id)
        if job.status in {ReviewJobStatus.QUEUED, ReviewJobStatus.RUNNING}:
            raise ReviewJobNotDeletableError(f"active job cannot be deleted: {job.status.value}")

        artifact_count = 0
        artifact_dir = _safe_artifact_dir_for_delete(job, self.store.root.parent / "runs")
        if artifact_dir is not None and artifact_dir.exists():
            artifact_count = sum(1 for item in artifact_dir.rglob("*") if item.is_file())
            shutil.rmtree(artifact_dir)

        self.store.delete(job_id)
        return {"job_id": job_id, "deleted": True, "artifact_count": artifact_count}

    def delete_jobs(self, job_ids: list[str]) -> dict[str, Any]:
        deleted: list[dict[str, Any]] = []
        errors: list[dict[str, Any]] = []
        for job_id in job_ids:
            try:
                deleted.append(self.delete_job(str(job_id)))
            except Exception as exc:
                # 批量删除按 run 尽量完成其它项；失败项交给前端明确展示。
                errors.append(
                    {
                        "job_id": str(job_id),
                        "error_type": exc.__class__.__name__,
                        "message": str(exc),
                    }
                )
        return {"deleted_count": len(deleted), "error_count": len(errors), "deleted": deleted, "errors": errors}

    def read_report(self, job_id: str) -> dict[str, str]:
        artifact_dir = _artifact_dir_for(self.get_job(job_id))
        report_path = _primary_report_path(artifact_dir)
        return {
            "name": report_path.name,
            "content_type": "text/markdown; charset=utf-8",
            "content": report_path.read_text(encoding="utf-8"),
        }

    def read_diagnostics(self, job_id: str) -> dict[str, Any]:
        artifact_dir = _artifact_dir_for(self.get_job(job_id))
        diagnostics_path = artifact_dir / "diagnostics.json"
        if not diagnostics_path.exists() or not diagnostics_path.is_file():
            raise ReviewJobArtifactNotFoundError("diagnostics.json")
        diagnostics = json.loads(diagnostics_path.read_text(encoding="utf-8"))
        if not isinstance(diagnostics, dict):
            return {"status": "unknown", "raw": diagnostics}
        return diagnostics

    def read_llm_calls(self, job_id: str) -> list[dict[str, Any]]:
        artifact_dir = _artifact_dir_for(self.get_job(job_id))
        llm_calls_path = artifact_dir / "llm_calls.jsonl"
        if not llm_calls_path.exists() or not llm_calls_path.is_file():
            return []
        events: list[dict[str, Any]] = []
        for line in llm_calls_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            item = json.loads(line)
            if isinstance(item, dict):
                events.append(item)
        return events

    def run_job(self, job_id: str) -> None:
        # 后台任务只写状态，不把异常重新抛给 HTTP 层；前端通过 GET /api/jobs/{id} 查看失败原因。
        try:
            self._raise_if_canceled(job_id)
        except ReviewJobCanceledError:
            return
        job = self.store.update(job_id, status=ReviewJobStatus.RUNNING)
        try:
            run = self.workflow_factory().run(
                job.request,
                node_progress_callback=lambda event: self._append_node_event_unless_canceled(job_id, event),
            )
        except ReviewJobCanceledError:
            current = self.store.get(job_id)
            if current.status != ReviewJobStatus.CANCELED:
                self.store.update(job_id, status=ReviewJobStatus.CANCELED, error=_canceled_error_payload())
            return
        except Exception as exc:
            error = _error_payload(exc)
            failure_metadata = _failure_run_metadata(error)
            self.store.update(
                job_id,
                status=ReviewJobStatus.FAILED,
                error=error,
                **failure_metadata,
            )
            return

        try:
            self._raise_if_canceled(job_id)
        except ReviewJobCanceledError:
            return
        self.store.update(
            job_id,
            status=ReviewJobStatus.SUCCEEDED,
            run_id=run.run_id,
            artifact_dir=run.artifact_dir,
            final_decision=run.final_decision,
            error=None,
        )

    def _append_node_event_unless_canceled(self, job_id: str, event: dict[str, Any]) -> ReviewJobSnapshot:
        # 运行中的任务无法强杀正在执行的单个 LLM 请求，但每个节点进度回调都会检查取消状态。
        self._raise_if_canceled(job_id)
        snapshot = self.store.append_node_event(job_id, event)
        self._raise_if_canceled(job_id)
        return snapshot

    def _raise_if_canceled(self, job_id: str) -> None:
        if self.store.get(job_id).status == ReviewJobStatus.CANCELED:
            raise ReviewJobCanceledError(f"job canceled: {job_id}")


def build_job_runner(settings: Settings | None = None) -> ReviewJobRunner:
    settings = settings or load_settings()
    return ReviewJobRunner(store=LocalReviewJobStore(settings.jobs_dir))


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _error_payload(exc: Exception) -> dict[str, Any]:
    if isinstance(exc, ReviewAgentError):
        return exc.to_dict()
    if isinstance(exc, ReviewSubmissionError):
        return {"error_type": "ReviewSubmissionError", "message": str(exc)}
    return {
        "error_type": exc.__class__.__name__,
        "message": str(exc),
    }


def _job_matches_query(job: ReviewJobSnapshot, query: str) -> bool:
    needle = query.strip().lower()
    if not needle:
        return True
    request = job.request
    fields = [
        job.job_id,
        job.status.value,
        job.run_id,
        job.artifact_dir,
        str(job.final_decision or ""),
        request.paper_path,
        Path(request.paper_path).name,
        request.review_mode.value,
        request.output_language.value,
        request.venue_domain.value if request.venue_domain else "",
        request.venue_collection.value if request.venue_collection else "",
        request.venue_code,
    ]
    return any(needle in value.lower() for value in fields if value)


def _canceled_error_payload() -> dict[str, str]:
    return {
        "error_type": "ReviewJobCanceled",
        "message": "Review job was canceled by user.",
    }


def _failure_run_metadata(error: dict[str, Any]) -> dict[str, str]:
    details = error.get("details") if isinstance(error.get("details"), dict) else {}
    metadata: dict[str, str] = {}
    if details.get("run_id"):
        metadata["run_id"] = str(details["run_id"])
    if details.get("artifact_dir"):
        metadata["artifact_dir"] = str(details["artifact_dir"])
    return metadata


def _snapshot_from_dict(data: dict[str, Any]) -> ReviewJobSnapshot:
    request = data["request"]
    final_decision = data.get("final_decision")
    return ReviewJobSnapshot(
        job_id=str(data["job_id"]),
        status=ReviewJobStatus(str(data["status"])),
        request=ReviewRequest(
            paper_path=str(request["paper_path"]),
            review_mode=ReviewMode(str(request.get("review_mode", ReviewMode.FULL_REVIEW.value))),
            output_language=OutputLanguage(str(request.get("output_language", OutputLanguage.ZH.value))),
            venue_domain=VenueDomain(str(request["venue_domain"])) if request.get("venue_domain") else None,
            venue_collection=VenueCollection(str(request["venue_collection"])) if request.get("venue_collection") else None,
            venue_code=str(request.get("venue_code", "")),
        ),
        created_at=str(data["created_at"]),
        updated_at=str(data["updated_at"]),
        run_id=str(data.get("run_id", "")),
        artifact_dir=str(data.get("artifact_dir", "")),
        final_decision=FinalDecision(str(final_decision)) if final_decision else None,
        nodes=data.get("nodes") or {},
        node_events=list(data.get("node_events") or []),
        error=data.get("error"),
    )


def _normalize_node_event(event: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(event)
    normalized["event"] = str(normalized.get("event", ""))
    normalized["node"] = str(normalized.get("node", ""))
    normalized["timestamp"] = str(normalized.get("timestamp") or _utc_now())
    return normalized


def _node_status_from_event(event: str) -> str:
    if event == "start":
        return "RUNNING"
    if event == "done":
        return "SUCCEEDED"
    if event == "error":
        return "FAILED"
    return "UNKNOWN"


def _artifact_dir_for(job: ReviewJobSnapshot) -> Path:
    if job.status not in {ReviewJobStatus.SUCCEEDED, ReviewJobStatus.FAILED} or not job.artifact_dir:
        raise ReviewJobArtifactsUnavailableError(f"job artifacts are not available yet: {job.job_id}")
    path = Path(job.artifact_dir)
    if not path.exists() or not path.is_dir():
        raise ReviewJobArtifactNotFoundError(str(path))
    return path


def _primary_report_path(artifact_dir: Path) -> Path:
    # 成功 run 读 final_report；失败 run 读 partial_report，给前端同一个 report endpoint。
    for name in ("final_report.md", "partial_report.md"):
        path = artifact_dir / name
        if path.exists() and path.is_file():
            return path
    raise ReviewJobArtifactNotFoundError("final_report.md or partial_report.md")


def _primary_report_artifact(artifacts: list[dict[str, Any]]) -> dict[str, Any] | None:
    by_name = {str(artifact.get("name", "")): artifact for artifact in artifacts}
    for name in ("final_report.md", "partial_report.md", "desk_reject_report.md", "parse_failure_report.md", "invalid_file_report.md"):
        if name in by_name:
            return by_name[name]
    return next((artifact for artifact in artifacts if _is_report_artifact(str(artifact.get("name", "")))), None)


def _is_report_artifact(name: str) -> bool:
    return name.endswith(".md")


def _safe_artifact_dir_for_delete(job: ReviewJobSnapshot, runs_root: Path) -> Path | None:
    if not job.artifact_dir:
        return None
    path = Path(job.artifact_dir)
    if not path.exists():
        return None
    if not path.is_dir():
        raise ReviewJobArtifactsUnavailableError(f"artifact path is not a directory: {job.artifact_dir}")

    resolved = path.resolve()
    root = runs_root.resolve()
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        # 删除整次 run 会递归移除目录，必须限制在 data/runs 下面。
        raise ReviewJobArtifactsUnavailableError(f"refusing to delete artifact dir outside runs: {job.artifact_dir}") from exc
    return resolved
