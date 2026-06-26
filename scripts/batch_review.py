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
            progress(f"[{position}/{len(items)}] {row['status']} {item.paper_id} in {row['elapsed_sec']}s")
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
                progress(f"[{completed}/{len(items)}] {row['status']} {item.paper_id} in {row['elapsed_sec']}s")

    write_final_decisions_csv(batch_dir / "final_decisions.csv", sorted(final_rows, key=lambda row: int(row["index"])))
    summary = {
        "schema": SCHEMA,
        "batch_id": batch_dir.name,
        "status": "dry_run" if config.dry_run else "completed",
        "started_at": started_at,
        "finished_at": utc_now(),
        "batch_dir": str(batch_dir),
        "manifest_path": str(config.manifest_path),
        "total_selected": len(items),
        "concurrency": config.concurrency,
        "status_counts": dict(status_counts),
        "decision_counts": dict(decision_counts),
    }
    write_json(batch_dir / "summary.json", summary)
    progress(json.dumps(summary, ensure_ascii=False, indent=2))
    return summary


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
