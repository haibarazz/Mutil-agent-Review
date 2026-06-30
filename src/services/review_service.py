from __future__ import annotations

from pathlib import Path
from collections.abc import Callable
from uuid import uuid4
from typing import Any

from src.core.errors import ErrorContext, NodeFatalError, ReviewAgentError
from src.infra.storage import LocalArtifactStore
from src.core.models import FinalDecision, OutputLanguage, ParsedPaper, ReviewRequest, ReviewRun
from src.core.venue_catalog import VenueCatalogRepository
from src.graphs.graph import main_graph
from src.infra.llm_diagnostics import LLMCallCollector, llm_diagnostics_run, start_llm_call_collection, stop_llm_call_collection
from src.infra.llm_usage import build_usage_summary, load_pricing_config
from src.infra.settings import Settings, load_settings


ALLOWED_SUBMISSION_SUFFIXES = {".pdf", ".md", ".tex"}


class ReviewSubmissionError(ValueError):
    pass


def build_workflow(settings: Settings | None = None) -> "ReviewWorkflow":
    settings = settings or load_settings()
    return ReviewWorkflow(
        store=LocalArtifactStore(settings.runs_dir),
        venue_catalog=VenueCatalogRepository(settings.venues_dir),
    )


class ReviewWorkflow:
    """Thin application wrapper around the active LangGraph graph."""

    def __init__(self, *, store: LocalArtifactStore, venue_catalog: VenueCatalogRepository) -> None:
        self.store = store
        self.venue_catalog = venue_catalog

    def run(self, request: ReviewRequest, node_progress_callback: Callable[[dict[str, Any]], None] | None = None) -> ReviewRun:
        self._validate_submission(request)
        run_id = uuid4().hex
        initial_state = {
            "run_id": run_id,
            "paper_path": request.paper_path,
            "review_mode": request.review_mode.value,
            "output_language": request.output_language.value,
            "venue_domain": request.venue_domain.value if request.venue_domain else "",
            "venue_collection": request.venue_collection.value if request.venue_collection else "",
            "venue_code": request.venue_code,
        }
        if node_progress_callback:
            initial_state["node_progress_callback"] = node_progress_callback

        start_llm_call_collection(run_id)
        try:
            with llm_diagnostics_run(run_id):
                result = main_graph.invoke(initial_state)
        except ReviewAgentError as exc:
            llm_calls = stop_llm_call_collection(run_id)
            self._write_failure_artifacts(run_id, request, exc, llm_calls)
            raise
        except Exception as exc:
            error = NodeFatalError(
                str(exc),
                context=ErrorContext(details={"original_error_type": exc.__class__.__name__}),
            )
            llm_calls = stop_llm_call_collection(run_id)
            self._write_failure_artifacts(run_id, request, error, llm_calls)
            raise error from exc
        else:
            llm_calls = stop_llm_call_collection(run_id)

        usage_summary = self._usage_summary(run_id, llm_calls)
        diagnostics = self._success_diagnostics(result, llm_calls, usage_summary)
        stage_outputs = dict(result.get("stage_outputs", {}))
        reviewer_reports = self._sort_reports(list(result.get("reviewer_reports", [])))
        parsed_paper = result.get("parsed_paper") or ParsedPaper(
            source_path=request.paper_path,
            title="Unparsed manuscript",
            abstract="",
            full_text="",
            sections=[],
            pages=[],
        )
        final_decision = self._final_decision(result.get("final_decision", "REJECT"))
        decision_letter = str(result.get("decision_letter", ""))
        final_report_md = str(result.get("final_report_md", ""))
        rendered_artifacts = dict(result.get("rendered_artifacts", {}))

        self._write_artifacts(
            run_id=run_id,
            request=request,
            parsed_paper=parsed_paper,
            venue_profile=result.get("venue_profile"),
            stage_outputs=stage_outputs,
            reviewer_reports=reviewer_reports,
            final_decision=final_decision,
            decision_letter=decision_letter,
            final_report_md=final_report_md,
            rendered_artifacts=rendered_artifacts,
            diagnostics=diagnostics,
            usage_summary=usage_summary,
            llm_calls=llm_calls,
        )

        return ReviewRun(
            run_id=run_id,
            request=request,
            parsed_paper=parsed_paper,
            venue_profile=result.get("venue_profile"),
            stage_outputs=stage_outputs,
            reviewer_reports=reviewer_reports,
            final_decision=final_decision,
            decision_letter=decision_letter,
            artifact_dir=str(self.store.run_dir(run_id)),
            diagnostics=diagnostics,
        )

    def _write_artifacts(
        self,
        *,
        run_id: str,
        request: ReviewRequest,
        parsed_paper,
        venue_profile,
        stage_outputs: dict,
        reviewer_reports: list,
        final_decision: FinalDecision,
        decision_letter: str,
        final_report_md: str,
        rendered_artifacts: dict[str, str],
        diagnostics: dict,
        usage_summary: dict[str, Any],
        llm_calls: LLMCallCollector,
    ) -> None:
        self.store.write_json(run_id, "request.json", request)
        self.store.write_json(run_id, "parsed_paper.json", parsed_paper)
        self.store.write_json(run_id, "venue_profile.json", venue_profile)
        self.store.write_json(run_id, "diagnostics.json", diagnostics)
        self.store.write_json(run_id, "usage_summary.json", usage_summary)

        artifact_names = {
            "doc_parse": "doc_parse.json",
            "content_check": "content_check.json",
            "journal_requirements": "journal_requirements.json",
            "field_analysis": "field_analysis.json",
            "se_check": "se_check.json",
            "ae_check": "ae_check.json",
            "review_dispatch": "review_dispatch.json",
            "reviewer1": "reviewer1.json",
            "reviewer2": "reviewer2.json",
            "reviewer3": "reviewer3.json",
            "devils_advocate": "devils_advocate.json",
            "single_reviewer": "single_reviewer.json",
            "ae_decision": "ae_decision.json",
            "ae_report": "ae_report.json",
            "ae_finalize": "ae_finalize.json",
            "ae_final": "ae_final.json",
            "desk_reject_output": "desk_reject_output.json",
            "parse_fail_output": "parse_fail_output.json",
            "invalid_file": "invalid_file.json",
            "final_artifact_render": "final_artifact_render.json",
        }
        for key, filename in artifact_names.items():
            if key in stage_outputs:
                self.store.write_json(run_id, filename, stage_outputs[key])

        self.store.write_json(run_id, "stage_outputs.json", stage_outputs)
        self.store.write_json(run_id, "reviewer_reports.json", reviewer_reports)
        self.store.write_json(
            run_id,
            "final_decision.json",
            {"final_decision": final_decision, "decision_letter": decision_letter},
        )
        artifacts = rendered_artifacts or ({"final_report.md": final_report_md} if final_report_md else {})
        for filename, content in artifacts.items():
            # 文件名来自 graph 内部 renderer；落盘前仍收敛成 basename，避免未来误传路径。
            self.store.write_text(run_id, Path(filename).name, str(content))
        self._write_model_output_error_artifacts(run_id, llm_calls)
        self._write_llm_calls_artifact(run_id, llm_calls)

    def _success_diagnostics(self, result: dict, llm_calls: LLMCallCollector, usage_summary: dict[str, Any]) -> dict:
        # diagnostics.json 放汇总；完整逐行事件写在 llm_calls.jsonl，避免主诊断文件膨胀。
        return {
            "status": "succeeded",
            "errors": list(result.get("node_errors", [])),
            "fallback_events": list(result.get("fallback_events", [])),
            "llm_calls": llm_calls.summary(),
            "llm_attempts": llm_calls.attempt_summary(),
            "usage": self._compact_usage_summary(usage_summary),
            "model_output_errors": self._model_output_error_summary(llm_calls),
        }

    def _write_failure_artifacts(
        self,
        run_id: str,
        request: ReviewRequest,
        error: ReviewAgentError,
        llm_calls: LLMCallCollector,
    ) -> None:
        error = self._attach_failure_run_context(run_id, error)
        usage_summary = self._usage_summary(run_id, llm_calls)
        diagnostics = {
            "status": "failed",
            "errors": [error.to_dict()],
            "fallback_events": [],
            "llm_calls": llm_calls.summary(),
            "llm_attempts": llm_calls.attempt_summary(),
            "usage": self._compact_usage_summary(usage_summary),
            "model_output_errors": self._model_output_error_summary(llm_calls),
        }
        self.store.write_json(run_id, "request.json", request)
        self.store.write_json(run_id, "diagnostics.json", diagnostics)
        self.store.write_json(run_id, "usage_summary.json", usage_summary)
        self.store.write_text(run_id, "partial_report.md", self._render_partial_report(run_id, request, error))
        self._write_model_output_error_artifacts(run_id, llm_calls)
        self._write_llm_calls_artifact(run_id, llm_calls)

    def _write_model_output_error_artifacts(self, run_id: str, llm_calls: LLMCallCollector) -> None:
        for item in llm_calls.model_output_errors:
            self.store.write_json(run_id, str(item["path"]), item["payload"])

    def _model_output_error_summary(self, llm_calls: LLMCallCollector) -> dict:
        return {
            "count": len(llm_calls.model_output_errors),
            "files": [str(item["path"]) for item in llm_calls.model_output_errors],
        }

    def _write_llm_calls_artifact(self, run_id: str, llm_calls: LLMCallCollector) -> None:
        if not llm_calls.events:
            return
        self.store.write_text(run_id, "llm_calls.jsonl", llm_calls.to_jsonl() + "\n")

    def _usage_summary(self, run_id: str, llm_calls: LLMCallCollector) -> dict[str, Any]:
        # 观测配置不能影响审稿主流程；价格缺失时仍记录 token 和缺失计数。
        pricing_path = load_settings().project_root / "configs" / "llm_pricing.yaml"
        try:
            pricing = load_pricing_config(pricing_path)
            summary = build_usage_summary(run_id, llm_calls.events, pricing=pricing)
        except Exception as exc:
            summary = build_usage_summary(run_id, llm_calls.events, pricing={"currency": "USD", "models": {}})
            summary["pricing_error"] = f"{exc.__class__.__name__}: {exc}"
        return summary

    def _compact_usage_summary(self, usage_summary: dict[str, Any]) -> dict[str, Any]:
        keys = (
            "schema",
            "known_usage",
            "total_calls",
            "successful_calls",
            "error_calls",
            "fallback_count",
            "retry_error_count",
            "input_tokens",
            "output_tokens",
            "total_tokens",
            "estimated_cost_usd",
            "missing_usage_count",
            "missing_pricing_count",
        )
        return {key: usage_summary[key] for key in keys if key in usage_summary}

    def _attach_failure_run_context(self, run_id: str, error: ReviewAgentError) -> ReviewAgentError:
        # 失败 run 也会有本地产物目录；把目录挂到错误上下文，job 层才能继续暴露 partial_report。
        details = dict(error.context.details or {})
        details.update({"run_id": run_id, "artifact_dir": str(self.store.run_dir(run_id))})
        error.context = ErrorContext(
            node=error.context.node,
            prompt_name=error.context.prompt_name,
            provider=error.context.provider,
            model=error.context.model,
            attempt=error.context.attempt,
            elapsed_ms=error.context.elapsed_ms,
            details=details,
        )
        return error

    def _render_partial_report(self, run_id: str, request: ReviewRequest, error: ReviewAgentError) -> str:
        error_payload = error.to_dict()
        node = str(error_payload.get("node") or "-")
        provider = str(error_payload.get("provider") or "-")
        model = str(error_payload.get("model") or "-")
        if request.output_language == OutputLanguage.EN:
            return (
                "# Partial Review Report\n\n"
                "This run did not reach the final review renderer. The system saved this partial report so the failure can be inspected from the UI.\n\n"
                "## Run\n"
                f"- Run ID: `{run_id}`\n"
                f"- Paper: `{request.paper_path}`\n"
                f"- Venue: `{request.venue_domain.value if request.venue_domain else '-'} / {request.venue_collection.value if request.venue_collection else '-'} / {request.venue_code or '-'}`\n"
                f"- Review mode: `{request.review_mode.value}`\n\n"
                "## Failure\n"
                f"- Error type: `{error_payload.get('error_type', 'Unknown')}`\n"
                f"- Node: `{node}`\n"
                f"- Provider: `{provider}`\n"
                f"- Model: `{model}`\n"
                f"- Message: {error.message}\n\n"
                "## Next Steps\n"
                "- Check `diagnostics.json` for the structured error payload.\n"
                "- If the error is retryable, rerun the job after the provider or model recovers.\n"
                "- If the error is configuration-related, check `.env`, `configs/llm.yaml`, and the node prompt model id.\n"
            )
        return (
            "# Partial Review Report\n\n"
            "本次审稿没有走到最终报告渲染节点。系统先保存这个 partial report，方便你在前端或本地产物目录里查看失败位置。\n\n"
            "## Run\n"
            f"- Run ID: `{run_id}`\n"
            f"- Paper: `{request.paper_path}`\n"
            f"- Venue: `{request.venue_domain.value if request.venue_domain else '-'} / {request.venue_collection.value if request.venue_collection else '-'} / {request.venue_code or '-'}`\n"
            f"- Review mode: `{request.review_mode.value}`\n\n"
            "## Failure\n"
            f"- Error type: `{error_payload.get('error_type', 'Unknown')}`\n"
            f"- Node: `{node}`\n"
            f"- Provider: `{provider}`\n"
            f"- Model: `{model}`\n"
            f"- Message: {error.message}\n\n"
            "## Next Steps\n"
            "- 先看 `diagnostics.json`，里面有结构化错误信息。\n"
            "- 如果错误是 retryable，可以等供应商或模型恢复后重新运行。\n"
            "- 如果是配置类错误，检查 `.env`、`configs/llm.yaml` 和节点 prompt 里的 model id。\n"
        )

    def _final_decision(self, value) -> FinalDecision:
        try:
            return FinalDecision(str(value))
        except ValueError:
            return FinalDecision.REJECT

    def _sort_reports(self, reports: list) -> list:
        order = {
            "reviewer1": 0,
            "reviewer2": 1,
            "reviewer3": 2,
            "devils_advocate": 3,
        }
        return sorted(reports, key=lambda report: order.get(getattr(report, "reviewer_key", ""), 99))

    def _validate_submission(self, request: ReviewRequest) -> None:
        path = Path(request.paper_path)
        if not path.exists():
            raise ReviewSubmissionError(f"paper_path does not exist: {path}")
        if path.suffix.lower() not in ALLOWED_SUBMISSION_SUFFIXES:
            supported = ", ".join(sorted(ALLOWED_SUBMISSION_SUFFIXES))
            raise ReviewSubmissionError(f"unsupported paper file type: {path.suffix or '<none>'}; supported: {supported}")
        if not request.venue_code:
            raise ReviewSubmissionError("venue_code is required")
        if request.venue_domain is None or request.venue_collection is None:
            raise ReviewSubmissionError("venue_domain, venue_collection, and venue_code are required")
        if not self.venue_catalog.contains(
            domain=request.venue_domain,
            venue_collection=request.venue_collection,
            code=request.venue_code,
        ):
            raise ReviewSubmissionError(
                "venue selection does not match catalog: "
                f"{request.venue_domain.value}/{request.venue_collection.value}/{request.venue_code}"
            )
