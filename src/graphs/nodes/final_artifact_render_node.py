from __future__ import annotations

from src.graphs.state import GlobalState
from src.infra.renderers import ReviewArtifactRenderer


def final_artifact_render_node(state: GlobalState) -> GlobalState:
    """最后统一出口：把不同审稿路径都渲染成用户可下载/展示的报告。"""
    final_report_md = ReviewArtifactRenderer().render_markdown(
        parsed_paper=state.get("parsed_paper"),
        venue_profile=state.get("venue_profile"),
        final_decision=state.get("final_decision", "REJECT"),
        decision_letter=state.get("decision_letter", ""),
        reviewer_reports=state.get("reviewer_reports", []),
        ae_final=state.get("ae_final", {}),
        stage_outputs=state.get("stage_outputs", {}),
        output_language=state.get("output_language", "zh"),
    )
    return {
        "final_report_md": final_report_md,
        "rendered_artifacts": {"final_report.md": final_report_md},
        "stage_outputs": {
            "final_artifact_render": {
                "formats": ["md"],
                "files": ["final_report.md"],
            }
        },
    }
