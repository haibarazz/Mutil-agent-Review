import os
import tempfile
import unittest
from pathlib import Path

from src.services.review_service import ReviewSubmissionError
from src.services.review_service import build_workflow
from src.core.models import ReviewMode, ReviewRequest, VenueCollection, VenueDomain
from src.graphs.runtime import get_review_nodes


class WorkflowTests(unittest.TestCase):
    def setUp(self) -> None:
        os.environ["LLM_PROVIDER"] = "mock"
        get_review_nodes.cache_clear()

    def test_quick_review_writes_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            paper = Path(tmp) / "paper.md"
            paper.write_text(
                "Test Paper\n\nAbstract\nA manuscript for local framework smoke testing.\n\n1 Introduction\nContent.",
                encoding="utf-8",
            )
            workflow = build_workflow()
            run = workflow.run(
                ReviewRequest(
                    paper_path=str(paper),
                    review_mode=ReviewMode.QUICK_REVIEW,
                    venue_domain=VenueDomain.CS,
                    venue_collection=VenueCollection.CCFA,
                    venue_code="AAAI",
                )
            )

        self.assertEqual(run.request.review_mode, ReviewMode.QUICK_REVIEW)
        self.assertGreaterEqual(len(run.reviewer_reports), 4)
        self.assertTrue(Path(run.artifact_dir).exists())
        self.assertTrue((Path(run.artifact_dir) / "final_report.md").exists())

    def test_full_review_runs_editorial_screening(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            paper = Path(tmp) / "paper.md"
            paper.write_text(
                "Test Paper\n\nAbstract\nA manuscript for full workflow smoke testing.\n\n1 Introduction\nContent.",
                encoding="utf-8",
            )
            workflow = build_workflow()
            run = workflow.run(
                ReviewRequest(
                    paper_path=str(paper),
                    review_mode=ReviewMode.FULL_REVIEW,
                    venue_domain=VenueDomain.CS,
                    venue_collection=VenueCollection.CCFA,
                    venue_code="AAAI",
                )
            )

        self.assertIn("content_check", run.stage_outputs)
        self.assertIn("se_check", run.stage_outputs)
        self.assertIn("ae_check", run.stage_outputs)
        self.assertIn("ae_final", run.stage_outputs)
        self.assertEqual([r.reviewer_key for r in run.reviewer_reports], [
            "reviewer1",
            "reviewer2",
            "reviewer3",
            "devils_advocate",
        ])

    def test_rejects_mismatched_venue_selection_before_graph(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            paper = Path(tmp) / "paper.md"
            paper.write_text("Test Paper\n\nAbstract\nA manuscript.\n\n1 Introduction\nContent.", encoding="utf-8")
            workflow = build_workflow()

            with self.assertRaises(ReviewSubmissionError):
                workflow.run(
                    ReviewRequest(
                        paper_path=str(paper),
                        review_mode=ReviewMode.QUICK_REVIEW,
                        venue_domain=VenueDomain.IS,
                        venue_collection=VenueCollection.FT50,
                        venue_code="AAAI",
                    )
                )


if __name__ == "__main__":
    unittest.main()
