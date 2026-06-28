from __future__ import annotations

import os
import unittest

from src.core.errors import NodeFatalError
from src.core.models import ParsedPaper, ReviewerReport, VenueProfile
from src.graphs.nodes.ae_decision_node import ae_decision_node
from src.graphs.nodes.ae_finalize_node import ae_finalize_node
from src.graphs.nodes.ae_report_node import ae_report_node
from src.graphs.runtime import get_review_nodes


class AESplitNodeTests(unittest.TestCase):
    def setUp(self) -> None:
        os.environ["LLM_PROVIDER"] = "mock"
        get_review_nodes.cache_clear()

    def tearDown(self) -> None:
        get_review_nodes.cache_clear()

    def test_ae_decision_node_returns_frozen_decision(self) -> None:
        result = ae_decision_node(_base_state())

        self.assertEqual("MAJOR_REVISION", result["ae_decision_result"]["final_decision"])
        self.assertTrue(result["ae_decision_result"]["decision_rationale"])
        self.assertIn("consensus_disagreement", result["ae_decision_result"])
        self.assertIn("critical_issues", result["ae_decision_result"])
        self.assertIn("ae_decision", result["stage_outputs"])

    def test_ae_report_node_returns_report_without_redeciding(self) -> None:
        state = _base_state()
        state["ae_decision_result"] = {
            "final_decision": "MAJOR_REVISION",
            "decision_rationale": "核心问题可修，但需要大修。",
            "consensus_disagreement": {"consensus": []},
            "critical_issues": [{"issue_id": "AE-01"}],
        }

        result = ae_report_node(state)

        self.assertTrue(result["ae_report"]["decision_letter"])
        self.assertGreaterEqual(len(result["ae_report"]["revision_checklist"]), 3)
        self.assertGreaterEqual(len(result["ae_report"]["rr_traceability_matrix"]), 1)
        self.assertIn("revision_roadmap", result["ae_report"])
        self.assertNotIn("final_decision", result["ae_report"])
        self.assertIn("ae_report", result["stage_outputs"])

    def test_ae_finalize_node_merges_decision_and_report(self) -> None:
        result = ae_finalize_node(
            {
                "ae_decision_result": {
                    "final_decision": "MAJOR_REVISION",
                    "decision_rationale": "核心问题可修，但需要大修。",
                    "consensus_disagreement": {"consensus": []},
                    "critical_issues": [{"issue_id": "AE-01"}],
                },
                "ae_report": {
                    "decision_letter": "尊敬的作者：请完成大修。",
                    "revision_checklist": ["补充实验", "补充消融", "解释边界"],
                    "rr_traceability_matrix": [{"issue_id": "AE-01"}],
                    "revision_roadmap": {"must_fix": ["补充实验"]},
                },
            }
        )

        self.assertEqual("MAJOR_REVISION", result["final_decision"])
        self.assertEqual("尊敬的作者：请完成大修。", result["decision_letter"])
        self.assertEqual("MAJOR_REVISION", result["ae_final"]["final_decision"])
        self.assertEqual([{"issue_id": "AE-01"}], result["ae_final"]["critical_issues"])
        self.assertIn("ae_finalize", result["stage_outputs"])

    def test_ae_finalize_node_rejects_report_that_redecides(self) -> None:
        with self.assertRaises(NodeFatalError) as exc:
            ae_finalize_node(
                {
                    "ae_decision_result": {
                        "final_decision": "MAJOR_REVISION",
                        "decision_rationale": "核心问题可修，但需要大修。",
                        "consensus_disagreement": {},
                        "critical_issues": [],
                    },
                    "ae_report": {
                        "final_decision": "ACCEPT",
                        "decision_letter": "尊敬的作者：请完成大修。",
                        "revision_checklist": ["补充实验", "补充消融", "解释边界"],
                        "rr_traceability_matrix": [],
                        "revision_roadmap": {},
                    },
                }
            )

        self.assertEqual("ae_finalize", exc.exception.context.node)
        self.assertEqual(["final_decision"], exc.exception.context.details["forbidden_fields"])

def _base_state() -> dict:
    return {
        "parsed_paper": ParsedPaper(
            source_path="paper.md",
            title="AE Split Test Paper",
            abstract="A test abstract.",
            full_text="Abstract\nA test paper.\n\n1 Introduction\nContent.",
            sections=[],
            pages=[],
        ),
        "journal_requirements": "AAAI-style research contribution and rigorous evaluation.",
        "venue_profile": VenueProfile(
            code="AAAI",
            name="AAAI",
            source_path="venues/ccfa/AAAI_CCFA.md",
            journal_requirements_text="AAAI requirements",
            profile_text="AAAI values clear contribution and rigorous experiments.",
        ),
        "ae_result": {
            "ae_assessment": "送外审。",
            "paper_rubric": {"dimensions": []},
        },
        "reviewer_reports": [
            _reviewer_report("reviewer1", "Reviewer 1"),
            _reviewer_report("reviewer2", "Reviewer 2"),
            _reviewer_report("reviewer3", "Reviewer 3"),
            _reviewer_report("devils_advocate", "Devil's Advocate"),
        ],
        "output_language": "zh",
    }


def _reviewer_report(key: str, role: str) -> ReviewerReport:
    raw_result = {
        "summary": f"{role} summary.",
        "major_comments": [
            {
                "title": "证据链不足",
                "comment": "需要补充实验。",
                "evidence": "experiments",
                "severity": "major",
                "suggested_fix": "补充对照实验。",
            }
        ],
        "minor_comments": [],
        "strategic_advice": {"salvageability": "可修"},
    }
    return ReviewerReport(
        reviewer_key=key,
        role=role,
        summary=f"{role} summary.",
        strengths=["结构清晰"],
        weaknesses=[],
        rating=5,
        raw_result=raw_result,
    )


if __name__ == "__main__":
    unittest.main()
