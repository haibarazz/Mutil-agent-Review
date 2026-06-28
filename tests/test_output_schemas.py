from __future__ import annotations

import unittest

from src.core.errors import ErrorContext, ModelOutputValidationError
from src.core.output_schemas import (
    validate_ae_decision_output,
    validate_ae_final_output,
    validate_ae_report_output,
    validate_reviewer_output,
)


def _comment(index: int, severity: str = "major") -> dict[str, str]:
    return {
        "title": f"Comment {index}",
        "comment": "具体问题说明",
        "evidence": "Section 1",
        "severity": severity,
        "suggested_fix": "补充实验或解释。",
    }


def _valid_reviewer_output() -> dict:
    return {
        "summary": "论文摘要。",
        "strengths": ["优点一", "优点二"],
        "major_comments": [_comment(1), _comment(2), _comment(3)],
        "minor_comments": [_comment(4, "minor"), _comment(5, "minor")],
        "questions_for_authors": ["问题一？", "问题二？"],
        "scores": {"rating": 6, "confidence": 4},
    }


def _valid_ae_final_output() -> dict:
    return {
        "final_decision": "MAJOR_REVISION",
        "decision_letter": "Dear Author(s), please revise.",
        "revision_checklist": ["补充实验"],
        "rr_traceability_matrix": [],
        "revision_roadmap": {
            "must_fix": ["公平对比"],
            "should_fix": ["补充消融"],
            "nice_to_fix": ["优化图表"],
        },
    }


def _valid_ae_decision_output() -> dict:
    return {
        "final_decision": "MAJOR_REVISION",
        "decision_rationale": "核心实验仍需补强，但问题可修。",
        "consensus_disagreement": {
            "consensus": [],
            "disagreement": [],
            "da_critical_flagged": False,
            "da_critical_impact": "无",
        },
        "critical_issues": [
            {
                "issue_id": "AE-01",
                "source": "reviewer1",
                "severity": "major",
                "summary": "实验对比不足。",
                "evidence": "Reviewer 1 major comment.",
                "salvageability": "可修",
                "impact_on_decision": "需要大修。",
            }
        ],
    }


def _valid_ae_report_output() -> dict:
    return {
        "decision_letter": "尊敬的作者：请根据审稿意见完成大修。",
        "revision_checklist": ["补充实验", "增强消融", "解释适用边界"],
        "rr_traceability_matrix": [
            {
                "issue_id": "R1-01",
                "source": "reviewer1",
                "category": "实验",
                "description": "缺少关键基线。",
                "salvageability": "可修",
                "author_must_address": True,
                "verification_criteria": "新增公平对比实验。",
            }
        ],
        "revision_roadmap": {
            "must_fix": ["公平对比"],
            "should_fix": ["补充消融"],
            "nice_to_fix": ["优化图表"],
            "rebuttal_strategy": "优先回应实验充分性。",
        },
    }


class OutputSchemaTests(unittest.TestCase):
    def test_valid_reviewer_output_passes(self) -> None:
        payload = _valid_reviewer_output()

        result = validate_reviewer_output(payload)

        self.assertIs(result, payload)

    def test_reviewer_output_requires_major_minor_questions_and_rating(self) -> None:
        payload = _valid_reviewer_output()
        payload["major_comments"] = [_comment(1)]
        payload["minor_comments"] = []
        payload["questions_for_authors"] = ["问题一？"]
        payload["scores"] = {}

        with self.assertRaises(ModelOutputValidationError) as exc:
            validate_reviewer_output(payload, context=ErrorContext(prompt_name="reviewer1"))

        error = exc.exception.to_dict()
        self.assertEqual(error["code"], "model_output_validation_error")
        self.assertEqual(error["prompt_name"], "reviewer1")
        self.assertIn("major_comments", error["message"])
        self.assertIn("scores.rating", error["message"])

    def test_valid_ae_final_output_passes(self) -> None:
        payload = _valid_ae_final_output()

        result = validate_ae_final_output(payload)

        self.assertIs(result, payload)

    def test_ae_final_output_rejects_missing_decision_letter_and_bad_decision(self) -> None:
        payload = _valid_ae_final_output()
        payload["final_decision"] = "DESK_REJECT"
        payload["decision_letter"] = ""

        with self.assertRaises(ModelOutputValidationError) as exc:
            validate_ae_final_output(payload, context=ErrorContext(prompt_name="ae_final"))

        error = exc.exception.to_dict()
        self.assertEqual(error["prompt_name"], "ae_final")
        self.assertIn("decision_letter", error["message"])
        self.assertIn("final_decision", error["message"])

    def test_valid_ae_decision_output_passes(self) -> None:
        payload = _valid_ae_decision_output()

        result = validate_ae_decision_output(payload)

        self.assertIs(result, payload)

    def test_ae_decision_output_rejects_report_fields_and_desk_reject(self) -> None:
        payload = _valid_ae_decision_output()
        payload["final_decision"] = "DESK_REJECT"
        payload["decision_letter"] = "这个字段应该由 ae_report 负责。"

        with self.assertRaises(ModelOutputValidationError) as exc:
            validate_ae_decision_output(payload, context=ErrorContext(prompt_name="ae_decision"))

        error = exc.exception.to_dict()
        self.assertEqual(error["prompt_name"], "ae_decision")
        self.assertIn("final_decision", error["message"])
        self.assertIn("decision_letter", error["message"])

    def test_ae_decision_and_ae_final_reject_invalid_submission_decision(self) -> None:
        ae_decision = _valid_ae_decision_output()
        ae_decision["final_decision"] = "INVALID_SUBMISSION"
        ae_final = _valid_ae_final_output()
        ae_final["final_decision"] = "INVALID_SUBMISSION"

        with self.assertRaises(ModelOutputValidationError):
            validate_ae_decision_output(ae_decision, context=ErrorContext(prompt_name="ae_decision"))
        with self.assertRaises(ModelOutputValidationError):
            validate_ae_final_output(ae_final, context=ErrorContext(prompt_name="ae_final"))

    def test_valid_ae_report_output_passes(self) -> None:
        payload = _valid_ae_report_output()

        result = validate_ae_report_output(payload)

        self.assertIs(result, payload)

    def test_ae_report_output_rejects_decision_fields_and_short_checklist(self) -> None:
        payload = _valid_ae_report_output()
        payload["final_decision"] = "MAJOR_REVISION"
        payload["revision_checklist"] = ["补充实验"]

        with self.assertRaises(ModelOutputValidationError) as exc:
            validate_ae_report_output(payload, context=ErrorContext(prompt_name="ae_report"))

        error = exc.exception.to_dict()
        self.assertEqual(error["prompt_name"], "ae_report")
        self.assertIn("final_decision", error["message"])
        self.assertIn("revision_checklist", error["message"])


if __name__ == "__main__":
    unittest.main()
