from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DEFAULT_SOURCE_DATASET = Path("/Users/Zhuanz/Documents/code/论文浮现/Mutil-agent-review/openreview_dataset")
DEFAULT_OUTPUT_DIR = Path("data/corpora/openreview_mineru_iclr2025")
SCHEMA = "openreview_mineru_iclr2025_v1"


@dataclass(frozen=True)
class ImportItem:
    paper_id: str
    year: str
    source_paper_dir: Path
    source_review_dir: Path
    parsed_md_path: Path
    parsed_json_path: Path
    reviews_path: Path
    decision_path: Path
    source_manifest_path: Path | None
    title: str
    content_chars: int
    review_count: int
    decision: str
    decision_bucket: str
    raw_parser_keys: list[str]


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as file:
        for row in rows:
            file.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def relative_to_cwd(path: Path) -> str:
    try:
        return path.resolve().relative_to(Path.cwd().resolve()).as_posix()
    except ValueError:
        return path.resolve().as_posix()


def find_review_dir(review_root: Path, paper_id: str) -> Path | None:
    matches = sorted(path for path in review_root.glob(f"*/{paper_id}") if path.is_dir())
    return matches[0] if matches else None


def build_source_manifest(item: ImportItem, source_dataset: Path) -> dict[str, Any]:
    if item.source_manifest_path and item.source_manifest_path.is_file():
        source_manifest = read_json(item.source_manifest_path)
    else:
        source_manifest = {}

    # 这里保留旧数据来源，同时补充本次导入自己的可追踪字段。
    return {
        "schema": SCHEMA,
        "imported_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "paper_id": item.paper_id,
        "venue": "ICLR",
        "year": item.year,
        "source_dataset": source_dataset.resolve().as_posix(),
        "source_paper_dir": item.source_paper_dir.resolve().as_posix(),
        "source_review_dir": item.source_review_dir.resolve().as_posix(),
        "raw_parser_keys": item.raw_parser_keys,
        "original_source_manifest": source_manifest,
    }


def collect_items(source_dataset: Path) -> tuple[list[ImportItem], Counter[str]]:
    papers_root = source_dataset / "papers"
    review_root = source_dataset / "review_decision" / "iclr"
    skipped: Counter[str] = Counter()
    items: list[ImportItem] = []

    for parsed_md_path in sorted(papers_root.glob("*/paper_parsed.md")):
        paper_dir = parsed_md_path.parent
        paper_id = paper_dir.name
        parsed_json_path = paper_dir / "paper_parsed.json"
        source_manifest_path = paper_dir / "source_manifest.json"

        if not parsed_md_path.is_file() or not parsed_json_path.is_file():
            skipped["broken_or_missing_parsed_files"] += 1
            continue

        try:
            parsed_json = read_json(parsed_json_path)
        except (OSError, json.JSONDecodeError):
            skipped["invalid_parsed_json"] += 1
            continue

        raw = (parsed_json.get("other") or {}).get("raw") or {}
        raw_parser_keys = sorted(raw.keys()) if isinstance(raw, dict) else []
        if "mineru_standard" not in raw_parser_keys:
            skipped["not_mineru_standard"] += 1
            continue

        review_dir = find_review_dir(review_root, paper_id)
        if review_dir is None:
            skipped["missing_review_dir"] += 1
            continue

        reviews_path = review_dir / "reviews.json"
        decision_path = review_dir / "decision.json"
        if not reviews_path.is_file() or not decision_path.is_file():
            skipped["missing_gold_files"] += 1
            continue

        try:
            reviews = read_json(reviews_path)
            decision = read_json(decision_path)
        except (OSError, json.JSONDecodeError):
            skipped["invalid_gold_json"] += 1
            continue

        content = parsed_json.get("content") or parsed_md_path.read_text(encoding="utf-8", errors="replace")
        items.append(
            ImportItem(
                paper_id=paper_id,
                year=review_dir.parent.name,
                source_paper_dir=paper_dir,
                source_review_dir=review_dir,
                parsed_md_path=parsed_md_path,
                parsed_json_path=parsed_json_path,
                reviews_path=reviews_path,
                decision_path=decision_path,
                source_manifest_path=source_manifest_path if source_manifest_path.is_file() else None,
                title=str(parsed_json.get("title") or ""),
                content_chars=len(content),
                review_count=int(reviews.get("review_count") or len(reviews.get("reviews") or [])),
                decision=str(decision.get("decision") or ""),
                decision_bucket=str(decision.get("decision_bucket") or ""),
                raw_parser_keys=raw_parser_keys,
            )
        )

    return items, skipped


def manifest_record(item: ImportItem, output_dir: Path, *, include_hashes: bool) -> dict[str, Any]:
    paper_dir = output_dir / "papers" / item.paper_id
    files = {
        "paper_md": paper_dir / "paper.md",
        "mineru_json": paper_dir / "mineru.json",
        "gold_reviews_json": paper_dir / "gold_reviews.json",
        "gold_decision_json": paper_dir / "gold_decision.json",
        "source_manifest_json": paper_dir / "source_manifest.json",
    }
    record: dict[str, Any] = {
        "schema": SCHEMA,
        "paper_id": item.paper_id,
        "venue": "ICLR",
        "year": int(item.year) if item.year.isdigit() else item.year,
        "title": item.title,
        "decision": item.decision,
        "decision_bucket": item.decision_bucket,
        "review_count": item.review_count,
        "content_chars": item.content_chars,
        "raw_parser_keys": item.raw_parser_keys,
        "files": {name: path.relative_to(output_dir).as_posix() for name, path in files.items()},
        "source": {
            "paper_parsed_md": item.parsed_md_path.resolve().as_posix(),
            "paper_parsed_json": item.parsed_json_path.resolve().as_posix(),
            "reviews_json": item.reviews_path.resolve().as_posix(),
            "decision_json": item.decision_path.resolve().as_posix(),
        },
    }
    if include_hashes:
        record["sha256"] = {
            "paper_md": sha256_file(files["paper_md"]),
            "mineru_json": sha256_file(files["mineru_json"]),
            "gold_reviews_json": sha256_file(files["gold_reviews_json"]),
            "gold_decision_json": sha256_file(files["gold_decision_json"]),
        }
    return record


def copy_item(item: ImportItem, output_dir: Path, source_dataset: Path, *, overwrite: bool) -> None:
    paper_dir = output_dir / "papers" / item.paper_id
    paper_dir.mkdir(parents=True, exist_ok=True)
    targets = {
        item.parsed_md_path: paper_dir / "paper.md",
        item.parsed_json_path: paper_dir / "mineru.json",
        item.reviews_path: paper_dir / "gold_reviews.json",
        item.decision_path: paper_dir / "gold_decision.json",
    }
    for source_path, target_path in targets.items():
        if target_path.exists() and not overwrite:
            continue
        shutil.copy2(source_path, target_path)
    source_manifest = build_source_manifest(item, source_dataset)
    write_json(paper_dir / "source_manifest.json", source_manifest)


def build_summary(
    *,
    source_dataset: Path,
    output_dir: Path,
    items: list[ImportItem],
    skipped: Counter[str],
    dry_run: bool,
    limit: int | None,
    copied_count: int,
) -> dict[str, Any]:
    decision_counts = Counter(item.decision_bucket for item in items)
    year_counts = Counter(item.year for item in items)
    review_count_distribution = Counter(str(item.review_count) for item in items)
    content_lengths = sorted(item.content_chars for item in items)
    return {
        "schema": SCHEMA,
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "dry_run": dry_run,
        "source_dataset": source_dataset.resolve().as_posix(),
        "output_dir": relative_to_cwd(output_dir),
        "limit": limit,
        "valid_item_count": len(items),
        "copied_item_count": copied_count,
        "skipped": dict(skipped),
        "decision_bucket_counts": dict(decision_counts),
        "year_counts": dict(year_counts),
        "review_count_distribution": dict(sorted(review_count_distribution.items())),
        "total_individual_reviews": sum(item.review_count for item in items),
        "content_chars": {
            "min": content_lengths[0] if content_lengths else 0,
            "p50": content_lengths[len(content_lengths) // 2] if content_lengths else 0,
            "p90": content_lengths[int(len(content_lengths) * 0.9)] if content_lengths else 0,
            "max": content_lengths[-1] if content_lengths else 0,
        },
        "sample_paper_ids": [item.paper_id for item in items[:20]],
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Import MinerU-parsed OpenReview ICLR 2025 corpus into local data/corpora.")
    parser.add_argument("--source-dataset", type=Path, default=DEFAULT_SOURCE_DATASET)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--with-hashes", action="store_true", help="Compute sha256 hashes after copying.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    source_dataset = args.source_dataset.expanduser().resolve()
    output_dir = args.output_dir
    if not source_dataset.exists():
        raise SystemExit(f"source dataset not found: {source_dataset}")

    items, skipped = collect_items(source_dataset)
    if args.limit is not None:
        items = items[: args.limit]

    copied_count = 0
    if not args.dry_run:
        output_dir.mkdir(parents=True, exist_ok=True)
        for item in items:
            copy_item(item, output_dir, source_dataset, overwrite=args.overwrite)
            copied_count += 1
        records = [manifest_record(item, output_dir, include_hashes=args.with_hashes) for item in items]
        write_jsonl(output_dir / "manifest.jsonl", records)
    summary = build_summary(
        source_dataset=source_dataset,
        output_dir=output_dir,
        items=items,
        skipped=skipped,
        dry_run=args.dry_run,
        limit=args.limit,
        copied_count=copied_count,
    )
    if not args.dry_run:
        write_json(output_dir / "import_summary.json", summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
