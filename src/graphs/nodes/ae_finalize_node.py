from __future__ import annotations

from typing import Any

from src.core.errors import ErrorContext, NodeFatalError
from src.graphs.state import GlobalState


_REPORT_FORBIDDEN_DECISION_FIELDS = {
    "final_decision",
    "decision_rationale",
    "consensus_disagreement",
    "critical_issues",
}


def ae_finalize_node(state: GlobalState) -> GlobalState:
    """确定性合并节点：把 AE 裁决和报告正文合成旧版 ae_final 结构。"""
    decision = dict(state.get("ae_decision_result", {}))
    report = dict(state.get("ae_report", {}))
    _ensure_report_did_not_redecide(report)

    final_decision = str(decision.get("final_decision") or "MAJOR_REVISION")
    decision_letter = str(report.get("decision_letter") or "")
    ae_final = {
        "final_decision": final_decision,
        "decision_rationale": decision.get("decision_rationale", ""),
        "decision_letter": decision_letter,
        "revision_checklist": report.get("revision_checklist", []),
        "consensus_disagreement": decision.get("consensus_disagreement", {}),
        "critical_issues": decision.get("critical_issues", []),
        "rr_traceability_matrix": report.get("rr_traceability_matrix", []),
        "revision_roadmap": report.get("revision_roadmap", {}),
        "raw_result": {
            "ae_decision": _raw_or_self(decision),
            "ae_report": _raw_or_self(report),
        },
    }
    return {
        "ae_final": ae_final,
        "final_decision": final_decision,
        "decision_letter": decision_letter,
        "stage_outputs": {"ae_finalize": ae_final},
    }


def _ensure_report_did_not_redecide(report: dict[str, Any]) -> None:
    present = sorted(field for field in _REPORT_FORBIDDEN_DECISION_FIELDS if field in report)
    if not present:
        return
    raise NodeFatalError(
        "ae_report must not output frozen decision fields",
        context=ErrorContext(
            node="ae_finalize",
            details={"forbidden_fields": present},
        ),
    )


def _raw_or_self(value: dict[str, Any]) -> dict[str, Any]:
    raw = value.get("raw_result")
    return raw if isinstance(raw, dict) else value
