from __future__ import annotations

from src.graphs.runtime import get_review_nodes
from src.graphs.state import GlobalState

# 通用的这个审稿人审稿节点
def run_reviewer(
    state: GlobalState,
    *,
    prompt_name: str,
    reviewer_key: str,
    legacy_reviewer_key: str,
    role: str,
) -> GlobalState:
    report = get_review_nodes().reviewer(
        prompt_name=prompt_name,
        reviewer_key=reviewer_key,
        role=role,
        legacy_reviewer_key=legacy_reviewer_key,
        paper=state["parsed_paper"],
        journal_requirements=state["journal_requirements"],
        venue_profile=state.get("venue_profile"),
        reviewer_config=state.get("reviewer_config", {}),
        ae_result=state.get("ae_result", {}),
        output_language=state.get("output_language", "zh"),
    )
    return {
        "reviewer_reports": [report],
        "stage_outputs": {reviewer_key: report},
    }
