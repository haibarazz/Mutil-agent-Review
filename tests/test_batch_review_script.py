import json
import tempfile
import threading
import time
import unittest
from pathlib import Path

from scripts.batch_review import BatchConfig, run_batch
from src.core.models import FinalDecision, ReviewMode


class FakeReviewRun:
    def __init__(self, *, run_id: str, final_decision: FinalDecision, artifact_dir: str) -> None:
        self.run_id = run_id
        self.final_decision = final_decision
        self.artifact_dir = artifact_dir


class FakeWorkflow:
    def __init__(self) -> None:
        self.requests = []

    def run(self, request):
        self.requests.append(request)
        if "fail" in request.paper_path:
            raise RuntimeError("synthetic failure")
        return FakeReviewRun(
            run_id=f"run-{len(self.requests)}",
            final_decision=FinalDecision.MAJOR_REVISION,
            artifact_dir=f"/tmp/run-{len(self.requests)}",
        )


class ConcurrentTracker:
    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.active = 0
        self.max_active = 0
        self.calls = 0


class SlowTrackedWorkflow:
    def __init__(self, tracker: ConcurrentTracker) -> None:
        self.tracker = tracker

    def run(self, request):
        with self.tracker.lock:
            self.tracker.calls += 1
            call_no = self.tracker.calls
            self.tracker.active += 1
            self.tracker.max_active = max(self.tracker.max_active, self.tracker.active)
        try:
            time.sleep(0.05)
            return FakeReviewRun(
                run_id=f"parallel-run-{call_no}",
                final_decision=FinalDecision.MINOR_REVISION,
                artifact_dir=f"/tmp/parallel-run-{call_no}",
            )
        finally:
            with self.tracker.lock:
                self.tracker.active -= 1


def write_manifest(root: Path, rows: list[dict]) -> Path:
    manifest = root / "manifest.jsonl"
    with manifest.open("w", encoding="utf-8") as file:
        for row in rows:
            file.write(json.dumps(row, ensure_ascii=False) + "\n")
    return manifest


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


class BatchReviewScriptTests(unittest.TestCase):
    def test_dry_run_writes_planned_manifest_without_calling_workflow(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            paper = root / "papers" / "p1" / "paper.md"
            paper.parent.mkdir(parents=True)
            paper.write_text("paper", encoding="utf-8")
            manifest = write_manifest(
                root,
                [{"paper_id": "p1", "title": "Paper 1", "files": {"paper_md": "papers/p1/paper.md"}}],
            )

            calls = 0

            def factory():
                nonlocal calls
                calls += 1
                return FakeWorkflow()

            summary = run_batch(
                BatchConfig(
                    manifest_path=manifest,
                    batch_output_root=root / "batch_runs",
                    batch_id="dry-run",
                    dry_run=True,
                ),
                workflow_factory=factory,
                progress=lambda _message: None,
            )

            batch_dir = root / "batch_runs" / "dry-run"
            self.assertEqual(0, calls)
            self.assertEqual({"planned": 1}, summary["status_counts"])
            self.assertEqual("dry_run", read_json(batch_dir / "summary.json")["status"])
            self.assertEqual("planned", read_jsonl(batch_dir / "manifest.jsonl")[0]["status"])

    def test_batch_run_records_successes_failures_and_decision_summary(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for paper_id in ("ok", "fail"):
                paper = root / "papers" / paper_id / "paper.md"
                paper.parent.mkdir(parents=True)
                paper.write_text("paper", encoding="utf-8")
            manifest = write_manifest(
                root,
                [
                    {"paper_id": "ok", "title": "OK Paper", "files": {"paper_md": "papers/ok/paper.md"}},
                    {"paper_id": "fail", "title": "Fail Paper", "files": {"paper_md": "papers/fail/paper.md"}},
                ],
            )

            workflow = FakeWorkflow()
            summary = run_batch(
                BatchConfig(
                    manifest_path=manifest,
                    batch_output_root=root / "batch_runs",
                    batch_id="batch-1",
                    review_mode=ReviewMode.SINGLE_AGENT_REVIEW,
                ),
                workflow_factory=lambda: workflow,
                progress=lambda _message: None,
            )

            batch_dir = root / "batch_runs" / "batch-1"
            rows = read_jsonl(batch_dir / "manifest.jsonl")
            failures = read_jsonl(batch_dir / "failures.jsonl")

            self.assertEqual(["succeeded", "failed"], [row["status"] for row in rows])
            self.assertEqual(1, len(failures))
            self.assertEqual("RuntimeError", failures[0]["error_type"])
            self.assertEqual({"succeeded": 1, "failed": 1}, summary["status_counts"])
            self.assertEqual({"MAJOR_REVISION": 1}, summary["decision_counts"])
            self.assertIn("ok", (batch_dir / "final_decisions.csv").read_text(encoding="utf-8"))
            self.assertEqual(2, len(workflow.requests))

    def test_batch_run_can_execute_items_concurrently(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            rows = []
            for index in range(4):
                paper_id = f"p{index}"
                paper = root / "papers" / paper_id / "paper.md"
                paper.parent.mkdir(parents=True)
                paper.write_text("paper", encoding="utf-8")
                rows.append({"paper_id": paper_id, "title": paper_id, "files": {"paper_md": f"papers/{paper_id}/paper.md"}})
            manifest = write_manifest(root, rows)

            tracker = ConcurrentTracker()
            summary = run_batch(
                BatchConfig(
                    manifest_path=manifest,
                    batch_output_root=root / "batch_runs",
                    batch_id="parallel-batch",
                    concurrency=3,
                ),
                workflow_factory=lambda: SlowTrackedWorkflow(tracker),
                progress=lambda _message: None,
            )

            batch_dir = root / "batch_runs" / "parallel-batch"
            manifest_rows = read_jsonl(batch_dir / "manifest.jsonl")

            self.assertGreaterEqual(tracker.max_active, 2)
            self.assertEqual(4, tracker.calls)
            self.assertEqual(3, summary["concurrency"])
            self.assertEqual({"succeeded": 4}, summary["status_counts"])
            self.assertEqual({"MINOR_REVISION": 4}, summary["decision_counts"])
            self.assertEqual(4, len(manifest_rows))


if __name__ == "__main__":
    unittest.main()
