import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src.core.errors import ConfigurationError, ErrorContext, ModelOutputValidationError
from src.services.review_service import ReviewSubmissionError
from src.services.review_service import ReviewWorkflow, build_workflow
from src.core.models import FinalDecision, OutputLanguage, ParsedPaper, ReviewMode, ReviewRequest, VenueCollection, VenueDomain
from src.graphs.nodes.final_artifact_render_node import final_artifact_render_node
from src.graphs.runtime import get_review_nodes
from src.infra.llm_diagnostics import record_llm_event, record_model_output_error
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
        self.assertIn("ae_decision", run.stage_outputs)
        self.assertIn("ae_report", run.stage_outputs)
        self.assertIn("ae_finalize", run.stage_outputs)
        self.assertNotIn("ae_final", run.stage_outputs)
        self.assertIn("final_artifact_render", run.stage_outputs)
        self.assertTrue((Path(run.artifact_dir) / "ae_decision.json").exists())
        self.assertTrue((Path(run.artifact_dir) / "ae_report.json").exists())
        self.assertTrue((Path(run.artifact_dir) / "ae_finalize.json").exists())
        self.assertTrue((Path(run.artifact_dir) / "author_report.md").exists())
        self.assertTrue((Path(run.artifact_dir) / "internal_audit.md").exists())
        final_report = Path(run.artifact_dir) / "final_report.md"
        report_text = final_report.read_text(encoding="utf-8")
        self.assertIn("审稿报告", report_text)
        self.assertNotIn("Decision Letter", report_text)
        self.assertNotIn("Dear Author(s)", report_text)
        self.assertNotIn("AE 终审综合意见", report_text)
        self.assertNotIn("R&R 可追踪矩阵", report_text)
        internal_audit = (Path(run.artifact_dir) / "internal_audit.md").read_text(encoding="utf-8")
        self.assertIn("内部审计报告", internal_audit)
        self.assertIn("AE 终审综合意见", internal_audit)
        self.assertIn("R&R 可追踪矩阵", internal_audit)
        self.assertLess(report_text.index("### 审稿人 1：方法与实验"), report_text.index("### 反方辩护人"))
        self.assertIn("##### 主要意见", report_text)
        self.assertIn("##### 次要意见", report_text)
        self.assertIn("##### 给作者的问题", report_text)
        self.assertIn("##### 评分", report_text)
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

    def test_non_paper_markdown_routes_to_invalid_submission(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            paper = Path(tmp) / "recipe.md"
            paper.write_text(
                "# 周末番茄牛肉面\n\n"
                "今天的计划是先炒番茄，再加入牛肉和面条。"
                "配料包括番茄、牛肉、葱姜蒜和盐。"
                "这是一份家庭菜谱，不包含摘要、方法、实验或参考文献。",
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

        self.assertEqual("INVALID_SUBMISSION", run.final_decision.value)
        self.assertIn("content_check", run.stage_outputs)
        self.assertIn("invalid_file", run.stage_outputs)
        self.assertIn("final_artifact_render", run.stage_outputs)
        self.assertNotIn("journal_req_collector", run.stage_outputs)
        self.assertNotIn("field_analysis", run.stage_outputs)
        self.assertNotIn("single_reviewer", run.stage_outputs)
        self.assertEqual([], run.reviewer_reports)
        final_report = Path(run.artifact_dir) / "final_report.md"
        report_text = final_report.read_text(encoding="utf-8")
        self.assertIn("上传内容不是学术论文", report_text)
        self.assertNotIn("MAJOR_REVISION", report_text)
        self.assertNotIn("DESK_REJECT", report_text)

    def test_non_paper_tex_routes_to_invalid_submission(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            paper = Path(tmp) / "diary.tex"
            paper.write_text(
                "\\section{今天的心情}\n"
                "今天去咖啡店写日记，记录天气、早餐和旅行计划。"
                "这不是论文手稿，也没有摘要、研究问题、实验或参考文献。",
                encoding="utf-8",
            )
            run = build_workflow().run(
                ReviewRequest(
                    paper_path=str(paper),
                    review_mode=ReviewMode.SINGLE_AGENT_REVIEW,
                    venue_domain=VenueDomain.CS,
                    venue_collection=VenueCollection.CCFA,
                    venue_code="AAAI",
                )
            )

        self.assertEqual(FinalDecision.INVALID_SUBMISSION, run.final_decision)
        self.assertIn("content_check", run.stage_outputs)
        self.assertIn("invalid_file", run.stage_outputs)
        self.assertNotIn("single_reviewer", run.stage_outputs)

    def test_non_paper_pdf_parse_result_routes_to_invalid_submission(self) -> None:
        class FakePDFParser:
            def parse(self, path):
                return ParsedPaper(
                    source_path=str(path),
                    title="旅行攻略",
                    abstract="",
                    full_text=(
                        "旅行攻略\n\n"
                        "第一天安排酒店入住和晚餐，第二天安排景点参观。"
                        "这是一份行程安排和旅游攻略，不是学术论文。"
                    ),
                    sections=[],
                    pages=[],
                )

        with tempfile.TemporaryDirectory() as tmp:
            paper = Path(tmp) / "travel.pdf"
            paper.write_bytes(b"%PDF-1.4 fake pdf placeholder")
            nodes = get_review_nodes()
            original_parser = nodes.parser
            nodes.parser = FakePDFParser()
            try:
                run = build_workflow().run(
                    ReviewRequest(
                        paper_path=str(paper),
                        review_mode=ReviewMode.SINGLE_AGENT_REVIEW,
                        venue_domain=VenueDomain.CS,
                        venue_collection=VenueCollection.CCFA,
                        venue_code="AAAI",
                    )
                )
            finally:
                nodes.parser = original_parser

        self.assertEqual(FinalDecision.INVALID_SUBMISSION, run.final_decision)
        self.assertIn("content_check", run.stage_outputs)
        self.assertIn("invalid_file", run.stage_outputs)
        self.assertNotIn("single_reviewer", run.stage_outputs)

    def test_content_check_rejects_non_boolean_is_paper_output(self) -> None:
        class BadContentCheckLLM:
            def complete_json(self, **kwargs):
                return {"is_paper": "true", "reason": "字符串 true 不是布尔值。"}

            def complete_text(self, **kwargs):
                return ""

        nodes = get_review_nodes()
        original_llm = nodes.llm
        nodes.llm = BadContentCheckLLM()
        try:
            with self.assertRaises(ModelOutputValidationError):
                nodes.content_check(
                    ParsedPaper(
                        source_path="paper.md",
                        title="Paper",
                        abstract="Abstract",
                        full_text="Title\n\nAbstract\nThis paper studies a machine learning method.\n\n1 Introduction\nContent.",
                    )
                )
        finally:
            nodes.llm = original_llm

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
        self.assertIn("桌拒报告", report)
        self.assertNotIn("Decision Letter", report)
        self.assertNotIn("Dear Author(s)", report)
        self.assertIn("venue_fit", report)
        self.assertIn("Venue fit is weak.", report)
        self.assertIn("final_report.md", result["rendered_artifacts"])
        self.assertIn("author_report.md", result["rendered_artifacts"])
        self.assertIn("internal_audit.md", result["rendered_artifacts"])

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

    def test_final_artifact_render_localizes_chinese_decision_letter_prefix(self) -> None:
        result = final_artifact_render_node(
            {
                "parsed_paper": ParsedPaper(
                    source_path="paper.md",
                    title="Chinese Letter Candidate",
                    abstract="",
                    full_text="",
                    sections=[],
                    pages=[],
                ),
                "output_language": OutputLanguage.ZH.value,
                "final_decision": "DESK_REJECT",
                "decision_letter": "Dear Author(s),\n\nPlease revise the manuscript before resubmission.",
                "reviewer_reports": [],
                "stage_outputs": {},
            }
        )

        report = result["final_report_md"]
        self.assertIn("## 决定信", report)
        self.assertIn("尊敬的作者：", report)
        self.assertNotIn("Dear Author(s)", report)

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
                        "input_tokens": 100,
                        "output_tokens": 20,
                        "total_tokens": 120,
                    },
                )
                invalid_output_fields = record_model_output_error(
                    "validation_error",
                    {
                        "kind": "json",
                        "prompt": "reviewer2",
                        "provider": "fake_provider",
                        "model": "fake_model",
                        "attempt": 1,
                        "error_type": "ModelOutputValidationError",
                        "error_message": "strengths.0: Input should be a valid string",
                    },
                    {"invalid_output": {"summary": "bad", "strengths": [{"text": "not a string"}]}},
                )
                record_llm_event(
                    "error",
                    {
                        "kind": "json",
                        "prompt": "reviewer2",
                        "provider": "fake_provider",
                        "model": "fake_model",
                        "attempt": 1,
                        "error_type": "ModelOutputValidationError",
                        "error_message": "strengths.0: Input should be a valid string",
                        "retryable": "true",
                        "next_action": "retry_same_model",
                        **invalid_output_fields,
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
            usage_summary = json.loads((Path(run.artifact_dir) / "usage_summary.json").read_text(encoding="utf-8"))
            llm_lines = (Path(run.artifact_dir) / "llm_calls.jsonl").read_text(encoding="utf-8").splitlines()
            validation_error = json.loads(
                (Path(run.artifact_dir) / "model_output_errors" / "validation_error_001.json").read_text(
                    encoding="utf-8"
                )
            )

        self.assertEqual("succeeded", diagnostics["status"])
        self.assertEqual({"event_count": 3, "call_count": 1, "error_count": 1, "fallback_count": 0}, diagnostics["llm_calls"])
        self.assertEqual("review_usage_summary_v1", usage_summary["schema"])
        self.assertEqual(run.run_id, usage_summary["run_id"])
        self.assertEqual(100, usage_summary["input_tokens"])
        self.assertEqual(20, usage_summary["output_tokens"])
        self.assertEqual(120, usage_summary["total_tokens"])
        self.assertEqual(1, usage_summary["missing_pricing_count"])
        self.assertEqual(usage_summary["total_tokens"], diagnostics["usage"]["total_tokens"])
        self.assertEqual(1, diagnostics["model_output_errors"]["count"])
        self.assertEqual(["model_output_errors/validation_error_001.json"], diagnostics["model_output_errors"]["files"])
        self.assertEqual(1, diagnostics["llm_retry_timeline"]["event_count"])
        self.assertEqual("error", diagnostics["llm_retry_timeline"]["events"][0]["event"])
        self.assertEqual("retry_same_model", diagnostics["llm_retry_timeline"]["events"][0]["next_action"])
        self.assertEqual(
            "model_output_errors/validation_error_001.json",
            diagnostics["llm_retry_timeline"]["events"][0]["model_output_error_ref"],
        )
        self.assertEqual(3, len(llm_lines))
        first_event = json.loads(llm_lines[0])
        self.assertEqual("start", first_event["event"])
        self.assertEqual("reviewer1", first_event["prompt"])
        self.assertEqual("fake_provider", first_event["provider"])
        self.assertEqual(12, first_event["system_chars"])
        self.assertEqual(34, first_event["user_chars"])
        self.assertNotIn("unsafe_prompt", first_event)
        self.assertNotIn("must not be written", "\n".join(llm_lines))
        done_event = json.loads(llm_lines[1])
        self.assertEqual(100, done_event["input_tokens"])
        self.assertEqual(20, done_event["output_tokens"])
        error_event = json.loads(llm_lines[2])
        self.assertEqual("validation_error", error_event["model_output_error_kind"])
        self.assertEqual("model_output_errors/validation_error_001.json", error_event["model_output_error_ref"])
        self.assertEqual({"summary": "bad", "strengths": [{"text": "not a string"}]}, validation_error["invalid_output"])

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
                        "next_action": "fallback_model",
                    },
                )
                record_llm_event(
                    "fallback",
                    {
                        "prompt": "reviewer2",
                        "from_model": "fake_model",
                        "to_model": "backup_model",
                        "reason": "ProviderTransientError",
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
            usage_summary = json.loads((run_dir / "usage_summary.json").read_text(encoding="utf-8"))
            llm_lines = (run_dir / "llm_calls.jsonl").read_text(encoding="utf-8").splitlines()

        self.assertEqual("failed", diagnostics["status"])
        self.assertEqual({"event_count": 2, "call_count": 0, "error_count": 1, "fallback_count": 1}, diagnostics["llm_calls"])
        self.assertEqual(2, diagnostics["llm_retry_timeline"]["event_count"])
        self.assertEqual(["error", "fallback"], [event["event"] for event in diagnostics["llm_retry_timeline"]["events"]])
        self.assertEqual("fallback_model", diagnostics["llm_retry_timeline"]["events"][0]["next_action"])
        self.assertEqual("backup_model", diagnostics["llm_retry_timeline"]["events"][1]["to_model"])
        self.assertEqual("review_usage_summary_v1", usage_summary["schema"])
        self.assertEqual(1, usage_summary["error_calls"])
        self.assertEqual(1, usage_summary["retry_error_count"])
        self.assertEqual(2, len(llm_lines))
        error_event = json.loads(llm_lines[0])
        self.assertEqual("error", error_event["event"])
        self.assertEqual("reviewer2", error_event["prompt"])
        self.assertEqual("ProviderTransientError", error_event["error_type"])


if __name__ == "__main__":
    unittest.main()
