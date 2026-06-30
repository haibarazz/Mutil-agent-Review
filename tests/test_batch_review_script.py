import json
import tempfile
import threading
import time
import unittest
from pathlib import Path

from scripts.batch_review import BatchConfig, run_batch
from src.core.errors import ErrorContext, ModelOutputValidationError
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


class DiagnosticFailingWorkflow:
    def __init__(self, runs_dir: Path) -> None:
        self.runs_dir = runs_dir

    def run(self, request):
        run_id = "diagnostic-fail-run"
        run_dir = self.runs_dir / run_id
        run_dir.mkdir(parents=True, exist_ok=True)
        diagnostics = {
            "status": "failed",
            "errors": [
                {
                    "error_type": "ModelOutputValidationError",
                    "node": "reviewer2",
                    "model": "xopqwen36v35b",
                    "details": {
                        "run_id": run_id,
                        "artifact_dir": str(run_dir),
                        "errors": [
                            {
                                "error_type": "ModelOutputValidationError",
                                "prompt_name": "reviewer2",
                                "provider": "xunfeid",
                                "model": "xopqwen36v35b",
                                "attempt": 1,
                                "message": "strengths.0: Input should be a valid string",
                            },
                            {
                                "error_type": "ModelOutputValidationError",
                                "prompt_name": "reviewer2",
                                "provider": "xunfeid",
                                "model": "xopqwen36v35b",
                                "attempt": 2,
                                "message": "strengths.1: Input should be a valid string",
                            },
                        ],
                    },
                }
            ],
            "llm_calls": {
                "event_count": 4,
                "call_count": 2,
                "error_count": 2,
                "fallback_count": 0,
            },
            "llm_attempts": {
                "retry_error_count": 2,
                "last_error": {
                    "prompt": "reviewer2",
                    "model": "xopqwen36v35b",
                    "provider": "xunfeid",
                    "attempt": 2,
                    "error_type": "ModelOutputValidationError",
                    "error_message": "strengths.1: Input should be a valid string",
                    "next_action": "exhausted",
                    "model_output_error_kind": "validation_error",
                    "model_output_error_ref": "model_output_errors/validation_error_002.json",
                },
            },
            "llm_retry_timeline": {
                "event_count": 3,
                "truncated_count": 0,
                "events": [
                    {
                        "event": "error",
                        "prompt": "reviewer2",
                        "provider": "xunfeid",
                        "model": "xopqwen36v35b",
                        "attempt": 1,
                        "max_attempts": 2,
                        "error_type": "ModelOutputValidationError",
                        "error_message": "strengths.0: Input should be a valid string",
                        "next_action": "retry_same_model",
                        "model_output_error_kind": "validation_error",
                        "model_output_error_ref": "model_output_errors/validation_error_001.json",
                    },
                    {
                        "event": "fallback",
                        "prompt": "reviewer2",
                        "from_model": "xopqwen36v35b",
                        "to_model": "sf/deepseek-v4-pro",
                        "reason": "ModelOutputValidationError",
                    },
                    {
                        "event": "error",
                        "prompt": "reviewer2",
                        "provider": "siliconflow",
                        "model": "sf/deepseek-v4-pro",
                        "attempt": 1,
                        "max_attempts": 1,
                        "error_type": "ModelOutputValidationError",
                        "error_message": "decision_letter: Field required",
                        "next_action": "exhausted",
                        "model_output_error_kind": "validation_error",
                        "model_output_error_ref": "model_output_errors/validation_error_002.json",
                    },
                ],
            },
            "model_output_errors": {
                "count": 2,
                "files": [
                    "model_output_errors/validation_error_001.json",
                    "model_output_errors/validation_error_002.json",
                ],
            },
        }
        (run_dir / "diagnostics.json").write_text(json.dumps(diagnostics, ensure_ascii=False), encoding="utf-8")
        raise ModelOutputValidationError(
            "LLM route exhausted for xopqwen36v35b",
            context=ErrorContext(
                node="reviewer2",
                model="xopqwen36v35b",
                details={"run_id": run_id, "artifact_dir": str(run_dir), "errors": diagnostics["errors"][0]["details"]["errors"]},
            ),
        )


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

    def test_failed_batch_row_includes_retry_diagnostics_summary(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            paper = root / "papers" / "fail" / "paper.md"
            paper.parent.mkdir(parents=True)
            paper.write_text("paper", encoding="utf-8")
            manifest = write_manifest(
                root,
                [{"paper_id": "fail", "title": "Fail Paper", "files": {"paper_md": "papers/fail/paper.md"}}],
            )

            summary = run_batch(
                BatchConfig(
                    manifest_path=manifest,
                    batch_output_root=root / "batch_runs",
                    batch_id="diagnostic-batch",
                ),
                workflow_factory=lambda: DiagnosticFailingWorkflow(root / "runs"),
                progress=lambda _message: None,
            )

            failure = read_jsonl(root / "batch_runs" / "diagnostic-batch" / "failures.jsonl")[0]

        self.assertEqual({"failed": 1}, summary["status_counts"])
        self.assertEqual("ModelOutputValidationError", failure["error_type"])
        self.assertEqual("reviewer2", failure["failed_node"])
        self.assertEqual("reviewer2", failure["failed_prompt"])
        self.assertEqual("sf/deepseek-v4-pro", failure["failed_model"])
        self.assertEqual("siliconflow", failure["failed_provider"])
        self.assertEqual(2, failure["attempts_exhausted"])
        self.assertEqual(2, failure["llm_error_count"])
        self.assertEqual(0, failure["llm_fallback_count"])
        self.assertEqual(3, failure["retry_timeline_event_count"])
        self.assertEqual("exhausted", failure["last_retry_next_action"])
        self.assertEqual("model_output_errors/validation_error_002.json", failure["model_output_error_ref"])
        self.assertEqual(2, failure["model_output_error_count"])
        self.assertEqual("sf/deepseek-v4-pro", failure["fallback_models_tried"])
        self.assertTrue(failure["artifact_dir"].endswith("diagnostic-fail-run"))


if __name__ == "__main__":
    unittest.main()
