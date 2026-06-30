from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


SCHEMA = "decision_alignment_v1"
ACCEPT_LIKE = {"ACCEPT", "MINOR_REVISION", "accept", "accepted", "accept_like"}
REJECT_LIKE = {"MAJOR_REVISION", "REJECT", "DESK_REJECT", "INVALID_SUBMISSION", "reject", "rejected", "reject_like"}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as file:
        for line_number, line in enumerate(file, start=1):
            stripped = line.strip()
            if not stripped:
                continue
            value = json.loads(stripped)
            if not isinstance(value, dict):
                raise ValueError(f"{path}:{line_number} must be a JSON object")
            rows.append(value)
    return rows


def evaluate_alignment(
    gold_rows: list[dict[str, Any]],
    prediction_rows: list[dict[str, Any]],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    gold_by_id = {str(row.get("paper_id") or ""): row for row in gold_rows if row.get("paper_id")}
    prediction_by_id = {str(row.get("paper_id") or ""): row for row in prediction_rows if row.get("paper_id")}

    details: list[dict[str, Any]] = []
    confusion: dict[str, Counter[str]] = defaultdict(Counter)
    status_counts: Counter[str] = Counter()
    correct_count = 0
    comparable_count = 0
    missing_prediction_count = 0
    failed_prediction_count = 0

    for paper_id in sorted(gold_by_id):
        gold = gold_by_id[paper_id]
        prediction = prediction_by_id.get(paper_id)
        gold_bucket = normalize_gold_bucket(gold)
        predicted_decision = str((prediction or {}).get("final_decision") or "")
        predicted_bucket = normalize_prediction_bucket(predicted_decision)
        status = str((prediction or {}).get("status") or "missing")
        status_counts[status] += 1

        alignment = "missing_prediction"
        if prediction is None:
            missing_prediction_count += 1
        elif status != "succeeded" or not predicted_bucket:
            failed_prediction_count += 1
            alignment = "not_comparable"
        elif not gold_bucket:
            alignment = "missing_gold"
        else:
            comparable_count += 1
            confusion[gold_bucket][predicted_bucket] += 1
            alignment = "correct" if gold_bucket == predicted_bucket else "wrong"
            if alignment == "correct":
                correct_count += 1

        details.append(
            {
                "paper_id": paper_id,
                "title": str(gold.get("title") or (prediction or {}).get("title") or ""),
                "gold_decision": str(gold.get("decision") or ""),
                "gold_bucket": gold_bucket,
                "predicted_decision": predicted_decision,
                "predicted_bucket": predicted_bucket,
                "prediction_status": status,
                "alignment": alignment,
                "run_id": str((prediction or {}).get("run_id") or ""),
                "artifact_dir": str((prediction or {}).get("artifact_dir") or ""),
            }
        )

    extra_prediction_count = len(set(prediction_by_id) - set(gold_by_id))
    accuracy = correct_count / comparable_count if comparable_count else 0.0
    summary = {
        "schema": SCHEMA,
        "total_gold": len(gold_by_id),
        "total_predictions": len(prediction_by_id),
        "comparable_count": comparable_count,
        "correct_count": correct_count,
        "accuracy": accuracy,
        "missing_prediction_count": missing_prediction_count,
        "failed_prediction_count": failed_prediction_count,
        "extra_prediction_count": extra_prediction_count,
        "prediction_status_counts": dict(status_counts),
        "confusion_matrix": _jsonable_confusion(confusion),
    }
    return summary, details


def normalize_gold_bucket(row: dict[str, Any]) -> str:
    bucket = str(row.get("decision_bucket") or "").strip()
    if bucket:
        return normalize_bucket_name(bucket)
    return normalize_prediction_bucket(str(row.get("decision") or ""))


def normalize_prediction_bucket(decision: str) -> str:
    value = decision.strip()
    if not value:
        return ""
    if value in ACCEPT_LIKE:
        return "accept_like"
    if value in REJECT_LIKE:
        return "reject_like"
    lower = value.lower()
    if "accept" in lower:
        return "accept_like"
    if "reject" in lower:
        return "reject_like"
    return ""


def normalize_bucket_name(value: str) -> str:
    lower = value.strip().lower()
    if lower in {"accept_like", "accepted", "accept"}:
        return "accept_like"
    if lower in {"reject_like", "rejected", "reject"}:
        return "reject_like"
    return lower


def write_outputs(output_dir: Path, summary: dict[str, Any], details: list[dict[str, Any]]) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "alignment_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    fields = [
        "paper_id",
        "title",
        "gold_decision",
        "gold_bucket",
        "predicted_decision",
        "predicted_bucket",
        "prediction_status",
        "alignment",
        "run_id",
        "artifact_dir",
    ]
    with (output_dir / "alignment_details.csv").open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fields)
        writer.writeheader()
        for row in details:
            writer.writerow({field: row.get(field, "") for field in fields})


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Compare batch review decisions against OpenReview gold decision buckets.")
    parser.add_argument("--gold-manifest", type=Path, required=True, help="Corpus manifest with paper_id and decision_bucket fields.")
    parser.add_argument("--batch-manifest", type=Path, required=True, help="Batch review manifest with paper_id and final_decision fields.")
    parser.add_argument("--output-dir", type=Path, required=True, help="Directory for alignment_summary.json and alignment_details.csv.")
    args = parser.parse_args(argv)

    summary, details = evaluate_alignment(load_jsonl(args.gold_manifest), load_jsonl(args.batch_manifest))
    summary.update(
        {
            "gold_manifest": str(args.gold_manifest),
            "batch_manifest": str(args.batch_manifest),
            "output_dir": str(args.output_dir),
        }
    )
    write_outputs(args.output_dir, summary, details)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


def _jsonable_confusion(confusion: dict[str, Counter[str]]) -> dict[str, dict[str, int]]:
    return {gold: dict(predicted_counts) for gold, predicted_counts in sorted(confusion.items())}


if __name__ == "__main__":
    raise SystemExit(main())
