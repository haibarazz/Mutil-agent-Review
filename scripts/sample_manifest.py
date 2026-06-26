from __future__ import annotations

import argparse
import json
import random
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


SCHEMA = "sample_manifest_v1"
DEFAULT_MANIFEST = PROJECT_ROOT / "data" / "corpora" / "openreview_mineru_iclr2025" / "manifest.jsonl"
DEFAULT_OUTPUT_ROOT = PROJECT_ROOT / "data" / "eval_sets"


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


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


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as file:
        for row in rows:
            file.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def default_output_name(manifest_path: Path, sample_size: int, seed: int) -> str:
    source_name = manifest_path.parent.name or manifest_path.stem
    return f"{source_name}_random{sample_size}_seed{seed}"


def sample_rows(rows: list[dict[str, Any]], sample_size: int, seed: int) -> list[dict[str, Any]]:
    if sample_size < 1:
        raise ValueError("--sample-size must be >= 1")
    if sample_size > len(rows):
        raise ValueError(f"--sample-size {sample_size} is larger than manifest row count {len(rows)}")
    rng = random.Random(seed)
    selected_indexes = sorted(rng.sample(range(len(rows)), sample_size))
    sampled: list[dict[str, Any]] = []
    for sample_index, source_index in enumerate(selected_indexes):
        row = dict(rows[source_index])
        # 保留原始行号，后面 single/full 对齐或追溯回全量 corpus 会用到。
        row["_sample"] = {
            "schema": SCHEMA,
            "sample_index": sample_index,
            "source_index": source_index,
        }
        sampled.append(row)
    return sampled


def with_resolved_file_paths(row: dict[str, Any], manifest_path: Path) -> dict[str, Any]:
    resolved = dict(row)
    files = resolved.get("files")
    if not isinstance(files, dict):
        return resolved

    resolved_files: dict[str, Any] = {}
    for key, value in files.items():
        if not isinstance(value, str):
            resolved_files[key] = value
            continue
        path = Path(value).expanduser()
        if not path.is_absolute():
            path = manifest_path.parent / path
        resolved_files[key] = path.resolve().as_posix()
    # eval set manifest 可能放在任意目录；文件路径写成绝对路径，避免后续 batch 误按 eval set 目录解析。
    resolved["files"] = resolved_files
    return resolved


def build_summary(
    *,
    manifest_path: Path,
    output_dir: Path,
    seed: int,
    sample_size: int,
    total_rows: int,
    sampled: list[dict[str, Any]],
) -> dict[str, Any]:
    decision_counts = Counter(str(row.get("decision_bucket") or row.get("decision") or "unknown") for row in sampled)
    year_counts = Counter(str(row.get("year") or "unknown") for row in sampled)
    return {
        "schema": SCHEMA,
        "generated_at": utc_now(),
        "source_manifest": str(manifest_path),
        "output_dir": str(output_dir),
        "seed": seed,
        "sample_size": sample_size,
        "source_row_count": total_rows,
        "decision_counts": dict(decision_counts),
        "year_counts": dict(year_counts),
        "sample_paper_ids": [str(row.get("paper_id") or "") for row in sampled[:20]],
    }


def run_sample(
    *,
    manifest_path: Path,
    output_dir: Path | None,
    sample_size: int,
    seed: int,
    overwrite: bool = False,
) -> dict[str, Any]:
    manifest_path = manifest_path.expanduser().resolve()
    if not manifest_path.is_file():
        raise FileNotFoundError(f"manifest not found: {manifest_path}")

    rows = read_jsonl(manifest_path)
    sampled = [with_resolved_file_paths(row, manifest_path) for row in sample_rows(rows, sample_size, seed)]
    output_dir = output_dir or (DEFAULT_OUTPUT_ROOT / default_output_name(manifest_path, sample_size, seed))
    if output_dir.exists() and any(output_dir.iterdir()) and not overwrite:
        raise FileExistsError(f"output dir already exists: {output_dir}")
    output_dir.mkdir(parents=True, exist_ok=True)

    write_jsonl(output_dir / "manifest.jsonl", sampled)
    summary = build_summary(
        manifest_path=manifest_path,
        output_dir=output_dir,
        seed=seed,
        sample_size=sample_size,
        total_rows=len(rows),
        sampled=sampled,
    )
    write_json(output_dir / "sample_summary.json", summary)
    return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create a fixed random eval-set manifest from a JSONL corpus manifest.")
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--output-dir", type=Path, default=None)
    parser.add_argument("--sample-size", type=int, default=100)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--overwrite", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    summary = run_sample(
        manifest_path=args.manifest,
        output_dir=args.output_dir,
        sample_size=args.sample_size,
        seed=args.seed,
        overwrite=args.overwrite,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
