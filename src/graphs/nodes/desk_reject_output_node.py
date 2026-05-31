from __future__ import annotations

from src.graphs.state import GlobalState


def desk_reject_output_node(state: GlobalState) -> GlobalState:
    se_result = state.get("se_result", {})
    ae_result = state.get("ae_result", {})
    fallback = "The manuscript was desk rejected."
    if state.get("output_language", "zh") != "en":
        fallback = "稿件未通过编辑初筛，建议修改后选择更匹配的目标 venue 再投稿。"
    letter = (
        se_result.get("se_rejection_letter")
        or ae_result.get("ae_rejection_letter")
        or fallback
    )
    return {
        "final_decision": "DESK_REJECT",
        "decision_letter": letter,
        "stage_outputs": {"desk_reject_output": {"decision_letter": letter}},
    }
