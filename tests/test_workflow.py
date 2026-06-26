import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src.core.errors import ConfigurationError, ErrorContext
from src.services.review_service import ReviewSubmissionError
from src.services.review_service import ReviewWorkflow, build_workflow
from src.core.models import OutputLanguage, ParsedPaper, ReviewMode, ReviewRequest, VenueCollection, VenueDomain
from src.graphs.nodes.final_artifact_render_node import final_artifact_render_node
from src.graphs.runtime import get_review_nodes
from src.infra.llm_diagnostics import record_llm_event
from src.infra.storage import LocalArtifactStore
from src.core.venue_catalog import VenueCatalogRepository


class WorkflowTests(unittest.TestCase):
    def setUp(self) -> None:
        os.environ["LLM_PROVIDER"] = "mock"
        get_review_nodes.cache_clear()

    def test_quick_review_writes_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            paper = Path(tmp) / "paper.md"
            paper.write_text(
                "Test Paper\n\nAbstract\nA manuscript for local framework smoke testing.\n\n1 Introduction\nContent.",
                encoding="utf-8",
            )
            workflow = build_workflow()
            run = workflow.run(
                ReviewRequest(
                    paper_path=str(paper),
                    review_mode=ReviewMode.QUICK_REVIEW,
                    venue_domain=VenueDomain.CS,
                    venue_collection=VenueCollection.CCFA,
                    venue_code="AAAI",
                )
            )

        self.assertEqual(run.request.review_mode, ReviewMode.QUICK_REVIEW)
        self.assertGreaterEqual(len(run.reviewer_reports), 4)
        self.assertTrue(Path(run.artifact_dir).exists())
        self.assertTrue((Path(run.artifact_dir) / "final_report.md").exists())
        self.assertTrue((Path(run.artifact_dir) / "diagnostics.json").exists())
        self.assertEqual("succeeded", run.diagnostics["status"])

    def test_full_review_runs_editorial_screening(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            paper = Path(tmp) / "paper.md"
            paper.write_text(
                "Test Paper\n\nAbstract\nA manuscript for full workflow smoke testing.\n\n1 Introduction\nContent.",
                encoding="utf-8",
            )
            workflow = build_workflow()
            run = workflow.run(
                ReviewRequest(
                    paper_path=str(paper),
                    review_mode=ReviewMode.FULL_REVIEW,
                    venue_domain=VenueDomain.CS,
                    venue_collection=VenueCollection.CCFA,
                    venue_code="AAAI",
                )
            )

        self.assertIn("content_check", run.stage_outputs)
        self.assertIn("se_check", run.stage_outputs)
        self.assertIn("ae_check", run.stage_outputs)
        self.assertIn("ae_final", run.stage_outputs)
        self.assertIn("final_artifact_render", run.stage_outputs)
        final_report = Path(run.artifact_dir) / "final_report.md"
        report_text = final_report.read_text(encoding="utf-8")
        self.assertIn("Review Report", report_text)
        self.assertLess(report_text.index("### 审稿人 1：方法与实验"), report_text.index("### 反方辩护人"))
        self.assertIn("##### Major Comments", report_text)
        self.assertIn("##### Minor Comments", report_text)
        self.assertIn("##### Questions for Authors", report_text)
        self.assertIn("##### Scores", report_text)
        self.assertNotIn("```json", report_text)
        self.assertEqual([r.reviewer_key for r in run.reviewer_reports], [
            "reviewer1",
            "reviewer2",
            "reviewer3",
            "devils_advocate",
        ])
        for report in run.reviewer_reports:
            with self.subTest(reviewer=report.reviewer_key):
                self.assertGreaterEqual(len(report.major_comments), 3)
                self.assertGreaterEqual(len(report.minor_comments), 2)
                self.assertGreaterEqual(len(report.questions_for_authors), 2)
                self.assertGreaterEqual(len(report.major_comments) + len(report.minor_comments), 5)
                self.assertTrue(report.scores)

    def test_single_agent_review_skips_editorial_and_multi_reviewer_nodes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            paper = Path(tmp) / "paper.md"
            paper.write_text(
                "Test Paper\n\nAbstract\nA manuscript for single agent smoke testing.\n\n1 Introduction\nContent.",
                encoding="utf-8",
            )
            workflow = build_workflow()
            run = workflow.run(
                ReviewRequest(
                    paper_path=str(paper),
                    review_mode=ReviewMode.SINGLE_AGENT_REVIEW,
                    venue_domain=VenueDomain.CS,
                    venue_collection=VenueCollection.CCFA,
                    venue_code="AAAI",
                )
            )

        self.assertEqual(run.request.review_mode, ReviewMode.SINGLE_AGENT_REVIEW)
        self.assertIn("single_reviewer", run.stage_outputs)
        self.assertIn("final_artifact_render", run.stage_outputs)
        self.assertNotIn("se_check", run.stage_outputs)
        self.assertNotIn("ae_check", run.stage_outputs)
        self.assertNotIn("review_dispatch", run.stage_outputs)
        self.assertNotIn("reviewer1", run.stage_outputs)
        self.assertNotIn("devils_advocate", run.stage_outputs)
        self.assertEqual(["single_reviewer"], [report.reviewer_key for report in run.reviewer_reports])
        self.assertTrue((Path(run.artifact_dir) / "final_report.md").exists())
        self.assertTrue((Path(run.artifact_dir) / "single_reviewer.json").exists())

    def test_rejects_mismatched_venue_selection_before_graph(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            paper = Path(tmp) / "paper.md"
            paper.write_text("Test Paper\n\nAbstract\nA manuscript.\n\n1 Introduction\nContent.", encoding="utf-8")
            workflow = build_workflow()

            with self.assertRaises(ReviewSubmissionError):
                workflow.run(
                    ReviewRequest(
                        paper_path=str(paper),
                        review_mode=ReviewMode.QUICK_REVIEW,
                        venue_domain=VenueDomain.IS,
                        venue_collection=VenueCollection.FT50,
                        venue_code="AAAI",
                    )
                )

    def test_final_artifact_render_handles_desk_reject_path(self) -> None:
        result = final_artifact_render_node(
            {
                "parsed_paper": ParsedPaper(
                    source_path="paper.md",
                    title="Desk Reject Candidate",
                    abstract="",
                    full_text="",
                    sections=[],
                    pages=[],
                ),
                "final_decision": "DESK_REJECT",
                "decision_letter": "This manuscript is not ready for external review.",
                "reviewer_reports": [],
                "stage_outputs": {
                    "se_check": {
                        "se_summary": "The topic fit is too weak for the selected venue.",
                        "se_concerns": ["Venue fit is weak.", "Core contribution is unclear."],
                        "se_desk_reject_types": ["venue_fit", "contribution_clarity"],
                    },
                    "desk_reject_output": {
                        "decision_letter": "This manuscript is not ready for external review."
                    },
                },
            }
        )

        report = result["final_report_md"]
        self.assertIn("Desk Reject Report", report)
        self.assertIn("venue_fit", report)
        self.assertIn("Venue fit is weak.", report)
        self.assertIn("final_report.md", result["rendered_artifacts"])

    def test_final_artifact_render_supports_english_output(self) -> None:
        result = final_artifact_render_node(
            {
                "parsed_paper": ParsedPaper(
                    source_path="paper.md",
                    title="English Output Candidate",
                    abstract="",
                    full_text="",
                    sections=[],
                    pages=[],
                ),
                "output_language": OutputLanguage.EN.value,
                "final_decision": "DESK_REJECT",
                "decision_letter": "This manuscript is not ready for external review.",
                "reviewer_reports": [],
                "stage_outputs": {
                    "se_check": {
                        "se_summary": "The topic fit is too weak for the selected venue.",
                        "se_concerns": ["Venue fit is weak."],
                        "se_desk_reject_types": ["venue_fit"],
                    },
                },
            }
        )

        report = result["final_report_md"]
        self.assertIn("Desk Reject Report", report)
        self.assertIn("Decision Letter", report)

    def test_rejects_missing_venue_catalog_selection_before_graph(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            paper = Path(tmp) / "paper.md"
            paper.write_text("Test Paper\n\nAbstract\nA manuscript.\n\n1 Introduction\nContent.", encoding="utf-8")
            workflow = build_workflow()

            with self.assertRaises(ReviewSubmissionError):
                workflow.run(
                    ReviewRequest(
                        paper_path=str(paper),
                        review_mode=ReviewMode.QUICK_REVIEW,
                        venue_code="AAAI",
                    )
                )

    def test_workflow_writes_diagnostics_when_graph_fails(self) -> None:
        class FailingGraph:
            def invoke(self, initial_state):
                raise ConfigurationError(
                    "LLM model is not registered",
                    context=ErrorContext(node="reviewer1", prompt_name="reviewer1", model="missing-model"),
                )

        with tempfile.TemporaryDirectory() as tmp:
            paper = Path(tmp) / "paper.md"
            paper.write_text("Test Paper\n\nAbstract\nA manuscript.\n\n1 Introduction\nContent.", encoding="utf-8")
            runs_dir = Path(tmp) / "runs"
            workflow = ReviewWorkflow(
                store=LocalArtifactStore(runs_dir),
                venue_catalog=VenueCatalogRepository(Path("venues")),
            )

            with patch("src.services.review_service.main_graph", FailingGraph()):
                with self.assertRaises(ConfigurationError):
                    workflow.run(
                        ReviewRequest(
                            paper_path=str(paper),
                            review_mode=ReviewMode.QUICK_REVIEW,
                            venue_domain=VenueDomain.CS,
                            venue_collection=VenueCollection.CCFA,
                            venue_code="AAAI",
                        )
                    )

            run_dirs = list(runs_dir.iterdir())
            self.assertEqual(1, len(run_dirs))
            diagnostics = json.loads((run_dirs[0] / "diagnostics.json").read_text(encoding="utf-8"))
            partial_report = (run_dirs[0] / "partial_report.md").read_text(encoding="utf-8")

        self.assertEqual("failed", diagnostics["status"])
        self.assertEqual("ConfigurationError", diagnostics["errors"][0]["error_type"])
        self.assertEqual("reviewer1", diagnostics["errors"][0]["node"])
        self.assertEqual("missing-model", diagnostics["errors"][0]["model"])
        self.assertEqual(str(run_dirs[0]), diagnostics["errors"][0]["details"]["artifact_dir"])
        self.assertIn("Partial Review Report", partial_report)
        self.assertIn("reviewer1", partial_report)
        self.assertIn("LLM model is not registered", partial_report)

    def test_workflow_writes_llm_call_events_for_successful_run(self) -> None:
        class LLMEventGraph:
            def invoke(self, initial_state):
                record_llm_event(
                    "start",
                    {
                        "kind": "json",
                        "prompt": "reviewer1",
                        "provider": "fake_provider",
                        "model": "fake_model",
                        "attempt": 1,
                        "system_chars": 12,
                        "user_chars": 34,
                        "unsafe_prompt": "must not be written",
                    },
                )
                record_llm_event(
                    "done",
                    {
                        "kind": "json",
                        "prompt": "reviewer1",
                        "provider": "fake_provider",
                        "model": "fake_model",
                        "attempt": 1,
                        "elapsed_ms": 42,
                    },
                )
                return {
                    "parsed_paper": ParsedPaper(
                        source_path=initial_state["paper_path"],
                        title="LLM Diagnostics Paper",
                        abstract="",
                        full_text="",
                    ),
                    "stage_outputs": {},
                    "reviewer_reports": [],
                    "final_decision": "REJECT",
                    "decision_letter": "No decision.",
                    "final_report_md": "# Review Report\n",
                }

        with tempfile.TemporaryDirectory() as tmp:
            paper = Path(tmp) / "paper.md"
            paper.write_text("Test Paper\n\nAbstract\nA manuscript.\n\n1 Introduction\nContent.", encoding="utf-8")
            runs_dir = Path(tmp) / "runs"
            workflow = ReviewWorkflow(
                store=LocalArtifactStore(runs_dir),
                venue_catalog=VenueCatalogRepository(Path("venues")),
            )

            with patch("src.services.review_service.main_graph", LLMEventGraph()):
                run = workflow.run(
                    ReviewRequest(
                        paper_path=str(paper),
                        review_mode=ReviewMode.QUICK_REVIEW,
                        venue_domain=VenueDomain.CS,
                        venue_collection=VenueCollection.CCFA,
                        venue_code="AAAI",
                    )
                )

            diagnostics = json.loads((Path(run.artifact_dir) / "diagnostics.json").read_text(encoding="utf-8"))
            llm_lines = (Path(run.artifact_dir) / "llm_calls.jsonl").read_text(encoding="utf-8").splitlines()

        self.assertEqual("succeeded", diagnostics["status"])
        self.assertEqual({"event_count": 2, "call_count": 1, "error_count": 0, "fallback_count": 0}, diagnostics["llm_calls"])
        self.assertEqual(2, len(llm_lines))
        first_event = json.loads(llm_lines[0])
        self.assertEqual("start", first_event["event"])
        self.assertEqual("reviewer1", first_event["prompt"])
        self.assertEqual("fake_provider", first_event["provider"])
        self.assertEqual(12, first_event["system_chars"])
        self.assertEqual(34, first_event["user_chars"])
        self.assertNotIn("unsafe_prompt", first_event)
        self.assertNotIn("must not be written", "\n".join(llm_lines))

    def test_workflow_writes_llm_call_events_when_graph_fails(self) -> None:
        class FailingLLMEventGraph:
            def invoke(self, initial_state):
                record_llm_event(
                    "error",
                    {
                        "kind": "json",
                        "prompt": "reviewer2",
                        "provider": "fake_provider",
                        "model": "fake_model",
                        "attempt": 1,
                        "elapsed_ms": 99,
                        "error_type": "ProviderTransientError",
                        "retryable": "true",
                    },
                )
                raise ConfigurationError(
                    "LLM model is not registered",
                    context=ErrorContext(node="reviewer2", prompt_name="reviewer2", model="missing-model"),
                )

        with tempfile.TemporaryDirectory() as tmp:
            paper = Path(tmp) / "paper.md"
            paper.write_text("Test Paper\n\nAbstract\nA manuscript.\n\n1 Introduction\nContent.", encoding="utf-8")
            runs_dir = Path(tmp) / "runs"
            workflow = ReviewWorkflow(
                store=LocalArtifactStore(runs_dir),
                venue_catalog=VenueCatalogRepository(Path("venues")),
            )

            with patch("src.services.review_service.main_graph", FailingLLMEventGraph()):
                with self.assertRaises(ConfigurationError):
                    workflow.run(
                        ReviewRequest(
                            paper_path=str(paper),
                            review_mode=ReviewMode.QUICK_REVIEW,
                            venue_domain=VenueDomain.CS,
                            venue_collection=VenueCollection.CCFA,
                            venue_code="AAAI",
                        )
                    )

            run_dir = next(runs_dir.iterdir())
            diagnostics = json.loads((run_dir / "diagnostics.json").read_text(encoding="utf-8"))
            llm_lines = (run_dir / "llm_calls.jsonl").read_text(encoding="utf-8").splitlines()

        self.assertEqual("failed", diagnostics["status"])
        self.assertEqual({"event_count": 1, "call_count": 0, "error_count": 1, "fallback_count": 0}, diagnostics["llm_calls"])
        self.assertEqual(1, len(llm_lines))
        error_event = json.loads(llm_lines[0])
        self.assertEqual("error", error_event["event"])
        self.assertEqual("reviewer2", error_event["prompt"])
        self.assertEqual("ProviderTransientError", error_event["error_type"])


if __name__ == "__main__":
    unittest.main()
