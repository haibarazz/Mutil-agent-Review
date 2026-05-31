from __future__ import annotations

import unittest

from src.core.errors import ErrorContext, ProviderFatalError, ProviderTransientError


class ErrorTypeTests(unittest.TestCase):
    def test_error_context_omits_empty_fields(self) -> None:
        context = ErrorContext(node="reviewer2", provider="deepseek", attempt=2)

        self.assertEqual(
            context.to_dict(),
            {"node": "reviewer2", "provider": "deepseek", "attempt": 2},
        )

    def test_transient_provider_error_is_retryable(self) -> None:
        error = ProviderTransientError(
            "provider timed out",
            context=ErrorContext(node="reviewer2", model="deepseek-v4-pro", attempt=1),
        )

        self.assertTrue(error.recoverable)
        self.assertTrue(error.retryable)
        self.assertEqual(error.to_dict()["code"], "provider_transient_error")
        self.assertEqual(error.to_dict()["node"], "reviewer2")

    def test_fatal_provider_error_is_not_retryable(self) -> None:
        error = ProviderFatalError("invalid api key")

        self.assertFalse(error.recoverable)
        self.assertFalse(error.retryable)
        self.assertEqual(error.to_dict()["error_type"], "ProviderFatalError")


if __name__ == "__main__":
    unittest.main()
