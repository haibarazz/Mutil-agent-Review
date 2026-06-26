from __future__ import annotations

from src.graphs.runtime import get_review_nodes
from src.graphs.state import GlobalState


def single_reviewer_node(state: GlobalState) -> GlobalState:
    # 单 Agent 模式把审稿判断集中到一个综合审稿人，前置解析和 venue context 仍然复用原流程。
    result = get_review_nodes().single_reviewer(
        paper=state["parsed_paper"],
        journal_requirements=state["journal_requirements"],
        venue_profile=state.get("venue_profile"),
        field_info=state.get("field_info", {}),
        output_language=state.get("output_language", "zh"),
    )
    report = result["report"]
    return {
        "reviewer_reports": [report],
        "final_decision": result["final_decision"],
        "decision_letter": result["decision_letter"],
        "stage_outputs": {
            "single_reviewer": {
                "review": report,
                "final_decision": result["final_decision"],
                "decision_letter": result["decision_letter"],
                "raw_result": result["raw_result"],
            }
        },
    }
