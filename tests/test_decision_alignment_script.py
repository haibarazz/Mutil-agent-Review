import json
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path

from scripts.decision_alignment import evaluate_alignment, load_jsonl, main


class DecisionAlignmentScriptTests(unittest.TestCase):
    def test_evaluate_alignment_reports_bucket_accuracy_and_confusion_matrix(self) -> None:
        gold_rows = [
            {"paper_id": "p1", "title": "Paper 1", "decision": "Accept", "decision_bucket": "accept_like"},
            {"paper_id": "p2", "title": "Paper 2", "decision": "Reject", "decision_bucket": "reject_like"},
            {"paper_id": "p3", "title": "Paper 3", "decision": "Reject", "decision_bucket": "reject_like"},
        ]
        prediction_rows = [
            {"paper_id": "p1", "status": "succeeded", "final_decision": "MINOR_REVISION"},
            {"paper_id": "p2", "status": "succeeded", "final_decision": "MAJOR_REVISION"},
            {"paper_id": "p3", "status": "succeeded", "final_decision": "ACCEPT"},
            {"paper_id": "p4", "status": "succeeded", "final_decision": "REJECT"},
        ]

        summary, details = evaluate_alignment(gold_rows, prediction_rows)

        self.assertEqual(3, summary["comparable_count"])
        self.assertEqual(2, summary["correct_count"])
        self.assertAlmostEqual(2 / 3, summary["accuracy"])
        self.assertEqual(1, summary["extra_prediction_count"])
        self.assertEqual(0, summary["missing_prediction_count"])
        self.assertEqual(1, summary["confusion_matrix"]["reject_like"]["accept_like"])
        self.assertEqual("wrong", details[2]["alignment"])

    def test_main_writes_summary_and_detail_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            gold_manifest = root / "gold.jsonl"
            batch_manifest = root / "batch.jsonl"
            output_dir = root / "out"
            gold_manifest.write_text(
                "\n".join(
                    [
                        json.dumps({"paper_id": "p1", "decision_bucket": "accept_like"}),
                        json.dumps({"paper_id": "p2", "decision_bucket": "reject_like"}),
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            batch_manifest.write_text(
                "\n".join(
                    [
                        json.dumps({"paper_id": "p1", "status": "succeeded", "final_decision": "ACCEPT"}),
                        json.dumps({"paper_id": "p2", "status": "failed", "error_type": "ProviderTransientError"}),
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            with redirect_stdout(StringIO()):
                exit_code = main(
                    [
                        "--gold-manifest",
                        str(gold_manifest),
                        "--batch-manifest",
                        str(batch_manifest),
                        "--output-dir",
                        str(output_dir),
                    ]
                )

            self.assertEqual(0, exit_code)
            summary = json.loads((output_dir / "alignment_summary.json").read_text(encoding="utf-8"))
            self.assertEqual("decision_alignment_v1", summary["schema"])
            self.assertEqual(1, summary["comparable_count"])
            self.assertEqual(0, summary["missing_prediction_count"])
            self.assertEqual(1, summary["failed_prediction_count"])
            self.assertTrue((output_dir / "alignment_details.csv").exists())

    def test_load_jsonl_ignores_blank_lines(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "rows.jsonl"
            path.write_text('\n{"paper_id": "p1"}\n\n', encoding="utf-8")

            self.assertEqual([{"paper_id": "p1"}], load_jsonl(path))


if __name__ == "__main__":
    unittest.main()
