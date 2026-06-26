from __future__ import annotations

import io
import os
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

from src.core.errors import ErrorContext, NodeFatalError, ProviderTransientError
from src.graphs.node_diagnostics import with_node_diagnostics


class NodeDiagnosticsTests(unittest.TestCase):
    def test_verbose_off_by_default(self) -> None:
        def ok_node(state):
            return {"ok": True}

        output = io.StringIO()
        wrapped = with_node_diagnostics("content_check", ok_node)

        with patch.dict(os.environ, {}, clear=True), redirect_stdout(output):
            result = wrapped({})

        self.assertEqual({"ok": True}, result)
        self.assertEqual("", output.getvalue())

    def test_verbose_logs_node_start_and_done(self) -> None:
        def ok_node(state):
            return {"ok": True}

        output = io.StringIO()
        wrapped = with_node_diagnostics("content_check", ok_node)

        with patch.dict(os.environ, {"REVIEW_VERBOSE": "true"}), redirect_stdout(output):
            result = wrapped({})

        self.assertEqual({"ok": True}, result)
        text = output.getvalue()
        self.assertIn("[review-node:start] content_check", text)
        self.assertIn("[review-node:done] content_check elapsed_ms=", text)

    def test_progress_callback_receives_node_events(self) -> None:
        def ok_node(state):
            return {"ok": True}

        events = []
        wrapped = with_node_diagnostics("content_check", ok_node)
        result = wrapped({"node_progress_callback": events.append})

        self.assertEqual({"ok": True}, result)
        self.assertEqual("start", events[0]["event"])
        self.assertEqual("content_check", events[0]["node"])
        self.assertEqual("done", events[1]["event"])
        self.assertEqual("content_check", events[1]["node"])
        self.assertIn("elapsed_ms", events[1])

    def test_review_agent_error_gets_node_context(self) -> None:
        def failing_node(state):
            raise ProviderTransientError(
                "provider timed out",
                context=ErrorContext(prompt_name="reviewer1", provider="sf", model="sf/deepseek-v4-pro"),
            )

        wrapped = with_node_diagnostics("reviewer1", failing_node)

        with self.assertRaises(ProviderTransientError) as caught:
            wrapped({})

        self.assertEqual("reviewer1", caught.exception.context.node)
        self.assertEqual("sf", caught.exception.context.provider)
        self.assertEqual("sf/deepseek-v4-pro", caught.exception.context.model)

    def test_verbose_logs_node_error(self) -> None:
        def failing_node(state):
            raise ProviderTransientError("provider timed out")

        output = io.StringIO()
        wrapped = with_node_diagnostics("reviewer1", failing_node)

        with patch.dict(os.environ, {"REVIEW_VERBOSE": "true"}), redirect_stdout(output):
            with self.assertRaises(ProviderTransientError):
                wrapped({})

        text = output.getvalue()
        self.assertIn("[review-node:start] reviewer1", text)
        self.assertIn("[review-node:error] reviewer1 elapsed_ms=", text)
        self.assertIn("error_type=ProviderTransientError", text)

    def test_unexpected_error_becomes_node_fatal_error(self) -> None:
        def failing_node(state):
            raise KeyError("parsed_paper")

        wrapped = with_node_diagnostics("content_check", failing_node)

        with self.assertRaises(NodeFatalError) as caught:
            wrapped({})

        error = caught.exception.to_dict()
        self.assertEqual("content_check", error["node"])
        self.assertEqual("NodeFatalError", error["error_type"])
        self.assertEqual("KeyError", error["details"]["original_error_type"])

    def test_single_reviewer_node_name_can_be_diagnosed(self) -> None:
        def ok_node(state):
            return {"ok": True}

        events = []
        wrapped = with_node_diagnostics("single_reviewer", ok_node)
        wrapped({"node_progress_callback": events.append})

        self.assertEqual("single_reviewer", events[0]["node"])
        self.assertEqual("single_reviewer", events[1]["node"])


if __name__ == "__main__":
    unittest.main()
