from __future__ import annotations

import json
from pathlib import Path
from uuid import uuid4

from src.infra.storage import LocalArtifactStore
from src.core.models import FinalDecision, ParsedPaper, ReviewMode, ReviewRequest, ReviewRun
from src.core.models import to_jsonable
from src.core.venue_catalog import VenueCatalogRepository
from src.graphs.graph import main_graph
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

    def run(self, request: ReviewRequest) -> ReviewRun:
        self._validate_submission(request)
        run_id = uuid4().hex
        initial_state = {
            "run_id": run_id,
            "paper_path": request.paper_path,
            "review_mode": request.review_mode.value,
            "venue_domain": request.venue_domain.value if request.venue_domain else "",
            "venue_collection": request.venue_collection.value if request.venue_collection else "",
            "venue_code": request.venue_code,
            "journal_name": request.journal_name,
            "journal_requirements_path": request.journal_requirements_path,
        }

        result = main_graph.invoke(initial_state)
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

        self._write_artifacts(
            run_id=run_id,
            request=request,
            parsed_paper=parsed_paper,
            venue_profile=result.get("venue_profile"),
            stage_outputs=stage_outputs,
            reviewer_reports=reviewer_reports,
            final_decision=final_decision,
            decision_letter=decision_letter,
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
    ) -> None:
        self.store.write_json(run_id, "request.json", request)
        self.store.write_json(run_id, "parsed_paper.json", parsed_paper)
        self.store.write_json(run_id, "venue_profile.json", venue_profile)

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
            "ae_final": "ae_final.json",
            "desk_reject_output": "desk_reject_output.json",
            "parse_fail_output": "parse_fail_output.json",
            "invalid_file": "invalid_file.json",
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
        self.store.write_text(
            run_id,
            "final_report.md",
            self._format_report(
                title=getattr(parsed_paper, "title", "Review Report"),
                decision=final_decision,
                decision_letter=decision_letter,
                reviewer_reports=reviewer_reports,
                stage_outputs=stage_outputs,
            ),
        )

    def _format_report(
        self,
        *,
        title: str,
        decision: FinalDecision,
        decision_letter: str,
        reviewer_reports: list,
        stage_outputs: dict,
    ) -> str:
        lines = [f"# Review Report: {title}", "", f"Final decision: **{decision.value}**", ""]
        if decision_letter:
            lines.extend(["## Decision Letter", "", decision_letter, ""])

        for report in reviewer_reports:
            lines.extend(
                [
                    f"## {report.role}",
                    "",
                    "### Part1 [The Review Report]",
                    "",
                    report.summary,
                    "",
                    f"Rating: {report.rating}/10",
                    "",
                    "#### Strengths",
                ]
            )
            lines.extend(f"- {item}" for item in report.strengths)
            lines.extend(["", "#### Weaknesses"])
            lines.extend(f"- [{item.location}] {item.issue}" for item in report.weaknesses)
            lines.extend(["", "### Part2 [Strategic Advice]", ""])
            if report.strategic_advice:
                lines.append("```json")
                lines.append(json.dumps(to_jsonable(report.strategic_advice), ensure_ascii=False, indent=2))
                lines.append("```")
            else:
                lines.append("No strategic advice was returned.")
            lines.append("")

        if not reviewer_reports and stage_outputs:
            lines.extend(["## Stage Outputs", "", "```json"])
            lines.append(json.dumps(to_jsonable(stage_outputs), ensure_ascii=False, indent=2))
            lines.append("```")
        return "\n".join(lines).strip() + "\n"

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

        if request.venue_domain is None and request.venue_collection is None:
            return
        if request.venue_domain is None or request.venue_collection is None:
            raise ReviewSubmissionError("venue_domain and venue_collection must be provided together")
        if not self.venue_catalog.contains(
            domain=request.venue_domain,
            venue_collection=request.venue_collection,
            code=request.venue_code,
        ):
            raise ReviewSubmissionError(
                "venue selection does not match catalog: "
                f"{request.venue_domain.value}/{request.venue_collection.value}/{request.venue_code}"
            )
