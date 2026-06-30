import tempfile
import unittest
from pathlib import Path

from src.infra.llm_usage import build_usage_summary, load_pricing_config


class LLMUsageTests(unittest.TestCase):
    def test_build_usage_summary_groups_by_provider_model_and_prompt(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            pricing_path = Path(tmp) / "llm_pricing.yaml"
            pricing_path.write_text(
                """
currency: USD
models:
  xopqwen36v35b:
    input_per_1m: 0.20
    output_per_1m: 0.80
""",
                encoding="utf-8",
            )
            pricing = load_pricing_config(pricing_path)

        events = [
            {
                "event": "done",
                "prompt": "reviewer1",
                "provider": "xunfeid",
                "model": "xopqwen36v35b",
                "provider_model": "xopqwen36v35b",
                "elapsed_ms": 1000,
                "input_tokens": 1000,
                "output_tokens": 200,
                "total_tokens": 1200,
            },
            {
                "event": "done",
                "prompt": "reviewer2",
                "provider": "xunfeid",
                "model": "xopqwen36v35b",
                "provider_model": "xopqwen36v35b",
                "elapsed_ms": 2000,
                "input_tokens": 2000,
                "output_tokens": 300,
                "total_tokens": 2300,
            },
        ]

        summary = build_usage_summary("run-1", events, pricing=pricing)

        self.assertEqual("review_usage_summary_v1", summary["schema"])
        self.assertEqual("run-1", summary["run_id"])
        self.assertEqual("USD", summary["currency"])
        self.assertTrue(summary["known_usage"])
        self.assertEqual(2, summary["total_calls"])
        self.assertEqual(2, summary["successful_calls"])
        self.assertEqual(3000, summary["input_tokens"])
        self.assertEqual(500, summary["output_tokens"])
        self.assertEqual(3500, summary["total_tokens"])
        self.assertGreater(summary["estimated_cost_usd"], 0)
        self.assertEqual(2, summary["by_provider"]["xunfeid"]["calls"])
        self.assertEqual(2, summary["by_model"]["xopqwen36v35b"]["calls"])
        self.assertEqual(1, summary["by_prompt"]["reviewer1"]["calls"])
        self.assertEqual("reviewer2", summary["slowest_call"]["prompt"])

    def test_missing_usage_is_counted_but_not_estimated(self) -> None:
        summary = build_usage_summary(
            "run-1",
            [{"event": "done", "prompt": "reviewer1", "provider": "xunfeid", "model": "xopqwen36v35b"}],
            pricing={"currency": "USD", "models": {}},
        )

        self.assertFalse(summary["known_usage"])
        self.assertEqual(1, summary["missing_usage_count"])
        self.assertEqual(0, summary["estimated_cost_usd"])

    def test_error_retry_and_fallback_counts_are_aggregated(self) -> None:
        summary = build_usage_summary(
            "run-1",
            [
                {"event": "start", "prompt": "reviewer1"},
                {"event": "error", "prompt": "reviewer1", "retryable": "true"},
                {"event": "fallback", "from_model": "a", "to_model": "b"},
                {"event": "error", "prompt": "reviewer1", "retryable": "false"},
            ],
            pricing={"currency": "USD", "models": {}},
        )

        self.assertEqual(1, summary["total_calls"])
        self.assertEqual(0, summary["successful_calls"])
        self.assertEqual(2, summary["error_calls"])
        self.assertEqual(1, summary["retry_error_count"])
        self.assertEqual(1, summary["fallback_count"])


if __name__ == "__main__":
    unittest.main()
