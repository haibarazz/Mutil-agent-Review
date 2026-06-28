from __future__ import annotations

from src.graphs.state import GlobalState


def invalid_file_node(state: GlobalState) -> GlobalState:
    fallback = (
        "The uploaded content is not an academic manuscript. The review workflow did not continue."
    )
    if state.get("output_language", "zh") != "en":
        fallback = "上传内容不是学术论文。系统没有进入正式审稿流程，请上传论文手稿。"
    detail = state.get("intent_detail") or ""
    message = f"{fallback}\n\n{detail}".strip() if detail else fallback
    return {
        "final_decision": "INVALID_SUBMISSION",
        "decision_letter": message,
        "stop_reason": "not_academic_paper",
        "stage_outputs": {"invalid_file": {"message": message, "stop_reason": "not_academic_paper"}},
    }
