import os
import unittest

from src.core.models import ParsedPaper, VenueProfile
from src.graphs.nodes.single_reviewer_node import single_reviewer_node
from src.graphs.runtime import get_review_nodes


class SingleReviewerNodeTests(unittest.TestCase):
    def setUp(self) -> None:
        os.environ["LLM_PROVIDER"] = "mock"
        get_review_nodes.cache_clear()

    def tearDown(self) -> None:
        get_review_nodes.cache_clear()

    def test_single_reviewer_node_returns_review_and_decision(self) -> None:
        result = single_reviewer_node(
            {
                "parsed_paper": ParsedPaper(
                    source_path="paper.md",
                    title="Single Agent Test Paper",
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
                "field_info": {"primary_discipline": "Computer Science"},
                "output_language": "zh",
            }
        )

        self.assertEqual("MAJOR_REVISION", result["final_decision"])
        self.assertTrue(result["decision_letter"])
        self.assertEqual(1, len(result["reviewer_reports"]))
        report = result["reviewer_reports"][0]
        self.assertEqual("single_reviewer", report.reviewer_key)
        self.assertGreaterEqual(len(report.major_comments), 3)
        self.assertGreaterEqual(len(report.minor_comments), 2)
        self.assertIn("single_reviewer", result["stage_outputs"])


if __name__ == "__main__":
    unittest.main()
