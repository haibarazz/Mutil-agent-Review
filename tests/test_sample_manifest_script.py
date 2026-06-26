import json
import tempfile
import unittest
from pathlib import Path

from scripts.sample_manifest import run_sample


def write_manifest(path: Path, count: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as file:
        for index in range(count):
            row = {
                "paper_id": f"paper-{index}",
                "title": f"Paper {index}",
                "year": 2025,
                "decision_bucket": "accept_like" if index % 2 else "reject_like",
                "files": {"paper_md": f"papers/paper-{index}/paper.md"},
            }
            file.write(json.dumps(row, ensure_ascii=False) + "\n")


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


class SampleManifestScriptTests(unittest.TestCase):
    def test_run_sample_writes_reproducible_eval_set(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest = root / "corpus" / "manifest.jsonl"
            write_manifest(manifest, 10)

            summary1 = run_sample(
                manifest_path=manifest,
                output_dir=root / "eval1",
                sample_size=4,
                seed=7,
            )
            summary2 = run_sample(
                manifest_path=manifest,
                output_dir=root / "eval2",
                sample_size=4,
                seed=7,
            )

            rows1 = read_jsonl(root / "eval1" / "manifest.jsonl")
            rows2 = read_jsonl(root / "eval2" / "manifest.jsonl")
            self.assertEqual([row["paper_id"] for row in rows1], [row["paper_id"] for row in rows2])
            self.assertTrue(Path(rows1[0]["files"]["paper_md"]).is_absolute())
            self.assertIn(str((root / "corpus").resolve()), rows1[0]["files"]["paper_md"])
            self.assertEqual([0, 1, 2, 3], [row["_sample"]["sample_index"] for row in rows1])
            self.assertEqual(4, summary1["sample_size"])
            self.assertEqual(10, summary1["source_row_count"])
            self.assertEqual(summary1["sample_paper_ids"], summary2["sample_paper_ids"])
            self.assertEqual(4, len(read_json(root / "eval1" / "sample_summary.json")["sample_paper_ids"]))

    def test_run_sample_refuses_to_overwrite_existing_output_by_default(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest = root / "manifest.jsonl"
            write_manifest(manifest, 3)
            output_dir = root / "eval"
            run_sample(manifest_path=manifest, output_dir=output_dir, sample_size=2, seed=1)

            with self.assertRaises(FileExistsError):
                run_sample(manifest_path=manifest, output_dir=output_dir, sample_size=2, seed=1)


if __name__ == "__main__":
    unittest.main()
