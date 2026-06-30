from __future__ import annotations

import argparse
import csv
import json
import sys
import time
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from collections import Counter
from collections.abc import Callable
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.core.errors import ReviewAgentError  # noqa: E402
from src.core.models import OutputLanguage, ReviewMode, ReviewRequest, VenueCollection, VenueDomain  # noqa: E402
from src.services.review_service import build_workflow  # noqa: E402


SCHEMA = "batch_review_v1"
DEFAULT_MANIFEST = PROJECT_ROOT / "data" / "corpora" / "openreview_mineru_iclr2025" / "manifest.jsonl"
DEFAULT_BATCH_ROOT = PROJECT_ROOT / "data" / "batch_runs"


@dataclass(frozen=True)
class BatchConfig:
    manifest_path: Path
    batch_output_root: Path = DEFAULT_BATCH_ROOT
    batch_id: str = ""
    offset: int = 0
    limit: int | None = None
    review_mode: ReviewMode = ReviewMode.SINGLE_AGENT_REVIEW
    output_language: OutputLanguage = OutputLanguage.ZH
    venue_domain: VenueDomain = VenueDomain.CS
    venue_collection: VenueCollection = VenueCollection.CCFA
    venue_code: str = "AAAI"
    paper_field: str = "files.paper_md"
    dry_run: bool = False
    fail_fast: bool = False
    concurrency: int = 1


@dataclass(frozen=True)
class BatchItem:
    index: int
    paper_id: str
    title: str
    paper_path: Path
    source_record: dict[str, Any]


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def append_jsonl(path: Path, row: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as file:
        file.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as file:
        for line_no, line in enumerate(file, start=1):
            stripped = line.strip()
            if not stripped:
                continue
            try:
                row = json.loads(stripped)
            except json.JSONDecodeError as exc:
                raise ValueError(f"invalid JSONL at {path}:{line_no}") from exc
            if not isinstance(row, dict):
                raise ValueError(f"manifest row must be an object at {path}:{line_no}")
            rows.append(row)
    return rows


def nested_get(record: dict[str, Any], field_path: str) -> Any:
    current: Any = record
    for part in field_path.split("."):
        if not isinstance(current, dict) or part not in current:
            return None
        current = current[part]
    return current


def resolve_paper_path(record: dict[str, Any], manifest_path: Path, field_path: str) -> Path:
    value = nested_get(record, field_path)
    if not value:
        raise ValueError(f"manifest row missing paper field: {field_path}")
    path = Path(str(value)).expanduser()
    if not path.is_absolute():
        # 导入脚本生成的 files.paper_md 是相对于 corpus 根目录，也就是 manifest 所在目录。
        path = manifest_path.parent / path
    return path.resolve()


def build_batch_items(config: BatchConfig) -> list[BatchItem]:
    records = read_jsonl(config.manifest_path)
    selected = records[config.offset :]
    if config.limit is not None:
        selected = selected[: config.limit]

    items: list[BatchItem] = []
    for relative_index, record in enumerate(selected):
        absolute_index = config.offset + relative_index
        paper_path = resolve_paper_path(record, config.manifest_path, config.paper_field)
        items.append(
            BatchItem(
                index=absolute_index,
                paper_id=str(record.get("paper_id") or paper_path.stem),
                title=str(record.get("title") or ""),
                paper_path=paper_path,
                source_record=record,
            )
        )
    return items


def batch_dir_for(config: BatchConfig) -> Path:
    batch_id = config.batch_id or datetime.now().strftime("%Y%m%d-%H%M%S")
    return config.batch_output_root / batch_id


def value_of(value: Any) -> str:
    return str(getattr(value, "value", value))


def write_batch_request(batch_dir: Path, config: BatchConfig, total_items: int) -> None:
    payload = asdict(config)
    payload.update(
        {
            "schema": SCHEMA,
            "created_at": utc_now(),
            "manifest_path": str(config.manifest_path),
            "batch_output_root": str(config.batch_output_root),
            "review_mode": config.review_mode.value,
            "output_language": config.output_language.value,
            "venue_domain": config.venue_domain.value,
            "venue_collection": config.venue_collection.value,
            "total_items": total_items,
        }
    )
    write_json(batch_dir / "batch_request.json", payload)


def write_final_decisions_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = ["index", "paper_id", "title", "paper_path", "run_id", "final_decision", "artifact_dir", "elapsed_sec"]
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fields})


def build_review_request(config: BatchConfig, item: BatchItem) -> ReviewRequest:
    return ReviewRequest(
        paper_path=str(item.paper_path),
        review_mode=config.review_mode,
        output_language=config.output_language,
        venue_domain=config.venue_domain,
        venue_collection=config.venue_collection,
        venue_code=config.venue_code,
    )


def base_manifest_row(batch_id: str, item: BatchItem) -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "batch_id": batch_id,
        "index": item.index,
        "paper_id": item.paper_id,
        "title": item.title,
        "paper_path": str(item.paper_path),
    }


def failure_diagnostics_fields(exc: Exception) -> dict[str, Any]:
    """把失败 run 的诊断摘要提升到 batch 行，避免批量分析时再逐个翻目录。"""
    fields: dict[str, Any] = {}
    if isinstance(exc, ReviewAgentError):
        fields.update(_fields_from_error_payload(exc.to_dict()))

    artifact_dir = fields.get("artifact_dir")
    if artifact_dir:
        diagnostics = _read_diagnostics(Path(str(artifact_dir)))
        if diagnostics:
            fields.update(_fields_from_diagnostics(diagnostics))

    return {
        key: value
        for key, value in fields.items()
        if value not in ("", None, {}, [])
    }


def _fields_from_diagnostics(diagnostics: dict[str, Any]) -> dict[str, Any]:
    fields: dict[str, Any] = {}
    errors = diagnostics.get("errors")
    if isinstance(errors, list) and errors:
        first_error = errors[0]
        if isinstance(first_error, dict):
            fields.update(_fields_from_error_payload(first_error))

    llm_calls = diagnostics.get("llm_calls")
    if isinstance(llm_calls, dict):
        fields.update(
            {
                "llm_event_count": llm_calls.get("event_count"),
                "llm_call_count": llm_calls.get("call_count"),
                "llm_error_count": llm_calls.get("error_count"),
                "llm_fallback_count": llm_calls.get("fallback_count"),
            }
        )

    llm_attempts = diagnostics.get("llm_attempts")
    if isinstance(llm_attempts, dict):
        fields["retry_error_count"] = llm_attempts.get("retry_error_count")
        last_error = llm_attempts.get("last_error")
        if isinstance(last_error, dict):
            fields.update(_fields_from_llm_event(last_error))

    llm_retry_timeline = diagnostics.get("llm_retry_timeline")
    if isinstance(llm_retry_timeline, dict):
        fields.update(_fields_from_retry_timeline(llm_retry_timeline))

    model_output_errors = diagnostics.get("model_output_errors")
    if isinstance(model_output_errors, dict):
        fields.update(_fields_from_model_output_errors(model_output_errors))

    return fields


def _fields_from_error_payload(error: dict[str, Any]) -> dict[str, Any]:
    fields: dict[str, Any] = {
        "failed_node": error.get("node"),
        "failed_prompt": error.get("prompt_name"),
        "failed_provider": error.get("provider"),
        "failed_model": error.get("model"),
        "failed_attempt": error.get("attempt"),
    }
    details = error.get("details")
    if isinstance(details, dict):
        fields["run_id"] = details.get("run_id")
        fields["artifact_dir"] = details.get("artifact_dir")
        route_errors = details.get("errors")
        if isinstance(route_errors, list) and route_errors:
            fields["attempts_exhausted"] = len(route_errors)
            last_route_error = route_errors[-1]
            if isinstance(last_route_error, dict):
                fields.update(_fields_from_route_error(last_route_error))
    return fields


def _fields_from_route_error(error: dict[str, Any]) -> dict[str, Any]:
    return {
        "failed_prompt": error.get("prompt_name") or error.get("prompt"),
        "failed_provider": error.get("provider"),
        "failed_model": error.get("model"),
        "failed_attempt": error.get("attempt"),
        "last_retry_error_type": error.get("error_type"),
        "last_retry_error_message": _short_text(error.get("message")),
    }


def _fields_from_llm_event(event: dict[str, Any]) -> dict[str, Any]:
    return {
        "failed_prompt": event.get("prompt"),
        "failed_provider": event.get("provider"),
        "failed_model": event.get("model"),
        "failed_attempt": event.get("attempt"),
        "failed_max_attempts": event.get("max_attempts"),
        "last_retry_error_type": event.get("error_type"),
        "last_retry_error_message": _short_text(event.get("error_message")),
        "last_retry_next_action": event.get("next_action"),
        "model_output_error_kind": event.get("model_output_error_kind"),
        "model_output_error_ref": event.get("model_output_error_ref"),
        "model_output_preview": _short_text(event.get("model_output_preview")),
    }


def _fields_from_retry_timeline(timeline: dict[str, Any]) -> dict[str, Any]:
    fields: dict[str, Any] = {
        "retry_timeline_event_count": timeline.get("event_count"),
        "retry_timeline_truncated_count": timeline.get("truncated_count"),
    }
    events = timeline.get("events")
    if not isinstance(events, list):
        return fields

    fallback_models = [
        str(event.get("to_model"))
        for event in events
        if isinstance(event, dict) and event.get("event") == "fallback" and event.get("to_model")
    ]
    if fallback_models:
        # 批量行只放短摘要；完整顺序仍在 diagnostics.json / llm_calls.jsonl。
        fields["fallback_models_tried"] = ",".join(fallback_models)

    error_events = [event for event in events if isinstance(event, dict) and event.get("event") == "error"]
    if error_events:
        fields.update(_fields_from_llm_event(error_events[-1]))
    return fields


def _fields_from_model_output_errors(model_output_errors: dict[str, Any]) -> dict[str, Any]:
    fields: dict[str, Any] = {
        "model_output_error_count": model_output_errors.get("count"),
    }
    files = model_output_errors.get("files")
    if isinstance(files, list) and files:
        fields["model_output_error_files"] = ",".join(str(item) for item in files)
    return fields


def _read_diagnostics(run_dir: Path) -> dict[str, Any]:
    path = run_dir / "diagnostics.json"
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def _short_text(value: Any, *, limit: int = 500) -> str:
    if value in ("", None):
        return ""
    text = str(value).replace("\n", " ").strip()
    if len(text) <= limit:
        return text
    return text[: limit - 3].rstrip() + "..."


def run_one_item(config: BatchConfig, batch_id: str, item: BatchItem, workflow_factory: Callable[[], Any]) -> dict[str, Any]:
    started = time.monotonic()
    row = base_manifest_row(batch_id, item)
    try:
        workflow = workflow_factory()
        run = workflow.run(build_review_request(config, item))
    except Exception as exc:  # noqa: BLE001 - 批量任务需要记录单篇失败后继续跑下一篇。
        return {
            **row,
            "status": "failed",
            "elapsed_sec": round(time.monotonic() - started, 3),
            "error_type": exc.__class__.__name__,
            "error_message": str(exc),
            **failure_diagnostics_fields(exc),
        }

    final_decision = value_of(run.final_decision)
    return {
        **row,
        "status": "succeeded",
        "elapsed_sec": round(time.monotonic() - started, 3),
        "run_id": run.run_id,
        "artifact_dir": run.artifact_dir,
        "final_decision": final_decision,
    }


def run_batch(
    config: BatchConfig,
    *,
    workflow_factory: Callable[[], Any] = build_workflow,
    progress: Callable[[str], None] = print,
) -> dict[str, Any]:
    manifest_path = config.manifest_path.expanduser().resolve()
    config = BatchConfig(**{**asdict(config), "manifest_path": manifest_path})
    if config.concurrency < 1:
        raise ValueError("--concurrency must be >= 1")
    if config.fail_fast and config.concurrency > 1:
        raise ValueError("--fail-fast is only supported when --concurrency 1")
    if not config.manifest_path.is_file():
        raise FileNotFoundError(f"manifest not found: {config.manifest_path}")

    items = build_batch_items(config)
    batch_dir = batch_dir_for(config)
    if batch_dir.exists() and any(batch_dir.iterdir()):
        raise FileExistsError(f"batch dir already exists: {batch_dir}")
    batch_dir.mkdir(parents=True, exist_ok=True)
    write_batch_request(batch_dir, config, len(items))

    started_at = utc_now()
    decision_counts: Counter[str] = Counter()
    status_counts: Counter[str] = Counter()
    final_rows: list[dict[str, Any]] = []
    write_lock = threading.RLock()

    def record_row(row: dict[str, Any]) -> None:
        with write_lock:
            append_jsonl(batch_dir / "manifest.jsonl", row)
            status_counts[str(row.get("status") or "unknown")] += 1
            if row.get("status") == "failed":
                append_jsonl(batch_dir / "failures.jsonl", row)
            if row.get("status") == "succeeded":
                final_rows.append(row)
                decision_counts[str(row.get("final_decision") or "UNKNOWN")] += 1

    if config.dry_run:
        for position, item in enumerate(items, start=1):
            progress(f"[{position}/{len(items)}] planned {item.paper_id} -> {item.paper_path.name}")
            record_row({**base_manifest_row(batch_dir.name, item), "status": "planned", "elapsed_sec": 0})
    elif config.concurrency == 1:
        for position, item in enumerate(items, start=1):
            progress(f"[{position}/{len(items)}] running {item.paper_id} -> {item.paper_path.name}")
            row = run_one_item(config, batch_dir.name, item, workflow_factory)
            record_row(row)
            progress(_progress_message(position, len(items), row, item))
            if config.fail_fast and row.get("status") == "failed":
                break
    else:
        progress(f"running {len(items)} items with concurrency={config.concurrency}")
        with ThreadPoolExecutor(max_workers=config.concurrency) as executor:
            future_to_item = {
                executor.submit(run_one_item, config, batch_dir.name, item, workflow_factory): item
                for item in items
            }
            for completed, future in enumerate(as_completed(future_to_item), start=1):
                item = future_to_item[future]
                try:
                    row = future.result()
                except Exception as exc:  # noqa: BLE001 - 防御 worker 外层异常，避免整个 batch 静默中断。
                    row = {
                        **base_manifest_row(batch_dir.name, item),
                        "status": "failed",
                        "elapsed_sec": 0,
                        "error_type": exc.__class__.__name__,
                        "error_message": str(exc),
                    }
                record_row(row)
                progress(_progress_message(completed, len(items), row, item))

    write_final_decisions_csv(batch_dir / "final_decisions.csv", sorted(final_rows, key=lambda row: int(row["index"])))
    succeeded_count = int(status_counts.get("succeeded", 0))
    failed_count = int(status_counts.get("failed", 0))
    planned_count = int(status_counts.get("planned", 0))
    completed_count = succeeded_count + failed_count
    summary = {
        "schema": SCHEMA,
        "batch_id": batch_dir.name,
        "status": _batch_status(
            dry_run=config.dry_run,
            total_selected=len(items),
            completed_count=completed_count,
            failed_count=failed_count,
            planned_count=planned_count,
        ),
        "started_at": started_at,
        "finished_at": utc_now(),
        "batch_dir": str(batch_dir),
        "manifest_path": str(config.manifest_path),
        "total_selected": len(items),
        "completed_count": completed_count,
        "succeeded_count": succeeded_count,
        "failed_count": failed_count,
        "planned_count": planned_count,
        "concurrency": config.concurrency,
        "status_counts": dict(status_counts),
        "decision_counts": dict(decision_counts),
    }
    write_json(batch_dir / "summary.json", summary)
    progress(json.dumps(summary, ensure_ascii=False, indent=2))
    return summary


def _batch_status(
    *,
    dry_run: bool,
    total_selected: int,
    completed_count: int,
    failed_count: int,
    planned_count: int,
) -> str:
    if dry_run:
        return "DRY_RUN"
    if total_selected == 0:
        return "EMPTY"
    if failed_count > 0 and completed_count < total_selected:
        return "STOPPED_AFTER_FAILURE"
    if failed_count > 0:
        return "COMPLETED_WITH_FAILURES"
    if completed_count == total_selected:
        return "SUCCEEDED"
    if planned_count > 0:
        return "DRY_RUN"
    return "INCOMPLETE"


def _progress_message(position: int, total: int, row: dict[str, Any], item: BatchItem) -> str:
    message = f"[{position}/{total}] {row['status']} {item.paper_id} in {row['elapsed_sec']}s"
    if row.get("status") != "failed":
        return message
    details = []
    if row.get("failed_node"):
        details.append(f"node={row['failed_node']}")
    if row.get("failed_prompt"):
        details.append(f"prompt={row['failed_prompt']}")
    if row.get("attempts_exhausted"):
        details.append(f"attempts={row['attempts_exhausted']}")
    if row.get("error_type"):
        details.append(f"error={row['error_type']}")
    return f"{message} {' '.join(details)}" if details else message


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run local paper review workflow over a JSONL corpus manifest.")
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--batch-output-root", type=Path, default=DEFAULT_BATCH_ROOT)
    parser.add_argument("--batch-id", default="")
    parser.add_argument("--offset", type=int, default=0)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--mode", choices=[mode.value for mode in ReviewMode], default=ReviewMode.SINGLE_AGENT_REVIEW.value)
    parser.add_argument("--output-language", choices=[lang.value for lang in OutputLanguage], default=OutputLanguage.ZH.value)
    parser.add_argument("--venue-domain", choices=[domain.value for domain in VenueDomain], default=VenueDomain.CS.value)
    parser.add_argument(
        "--venue-collection",
        choices=[collection.value for collection in VenueCollection],
        default=VenueCollection.CCFA.value,
    )
    parser.add_argument("--venue-code", default="AAAI")
    parser.add_argument("--paper-field", default="files.paper_md")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--fail-fast", action="store_true")
    parser.add_argument("--concurrency", type=int, default=1)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    config = BatchConfig(
        manifest_path=args.manifest,
        batch_output_root=args.batch_output_root,
        batch_id=args.batch_id,
        offset=args.offset,
        limit=args.limit,
        review_mode=ReviewMode(args.mode),
        output_language=OutputLanguage(args.output_language),
        venue_domain=VenueDomain(args.venue_domain),
        venue_collection=VenueCollection(args.venue_collection),
        venue_code=args.venue_code,
        paper_field=args.paper_field,
        dry_run=args.dry_run,
        fail_fast=args.fail_fast,
        concurrency=args.concurrency,
    )
    run_batch(config)


if __name__ == "__main__":
    main()
