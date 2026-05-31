from __future__ import annotations

import os
import sys
import time
from collections.abc import Callable
from datetime import datetime, timezone
from typing import Any

from src.core.errors import ErrorContext, NodeFatalError, ReviewAgentError
from src.graphs.state import GlobalState
from src.infra.llm_diagnostics import llm_diagnostics_run


NodeFunc = Callable[[GlobalState], GlobalState]


def with_node_diagnostics(node_name: str, node_func: NodeFunc) -> NodeFunc:
    """给 LangGraph 节点统一补充错误上下文，避免每个节点重复写 try/except。"""

    def wrapped(state: GlobalState) -> GlobalState:
        start = time.perf_counter()
        _emit_node_progress(state, "start", node_name)
        if _verbose_enabled():
            _print_node_event("start", node_name)
        try:
            with llm_diagnostics_run(str(state.get("run_id") or "")):
                result = node_func(state)
            _sleep_for_mock_demo()
            _emit_node_progress(state, "done", node_name, elapsed_ms=_elapsed_ms(start))
            if _verbose_enabled():
                _print_node_event("done", node_name, elapsed_ms=_elapsed_ms(start))
            return result
        except ReviewAgentError as exc:
            error = _with_node_context(exc, node_name)
            _emit_node_progress(
                state,
                "error",
                node_name,
                elapsed_ms=_elapsed_ms(start),
                error_type=error.__class__.__name__,
            )
            if _verbose_enabled():
                _print_node_event(
                    "error",
                    node_name,
                    elapsed_ms=_elapsed_ms(start),
                    error_type=error.__class__.__name__,
                )
            if error is exc:
                raise
            raise error from exc
        except Exception as exc:
            # 非系统内错误也收敛成统一异常，方便 service 层落 diagnostics.json。
            error = NodeFatalError(
                str(exc),
                context=ErrorContext(
                    node=node_name,
                    details={"original_error_type": exc.__class__.__name__},
                ),
            )
            _emit_node_progress(
                state,
                "error",
                node_name,
                elapsed_ms=_elapsed_ms(start),
                error_type=error.__class__.__name__,
            )
            if _verbose_enabled():
                _print_node_event(
                    "error",
                    node_name,
                    elapsed_ms=_elapsed_ms(start),
                    error_type=error.__class__.__name__,
                )
            raise error from exc

    return wrapped


def _with_node_context(error: ReviewAgentError, node_name: str) -> ReviewAgentError:
    if error.context.node:
        return error
    context = error.context
    return error.__class__(
        error.message,
        context=ErrorContext(
            node=node_name,
            prompt_name=context.prompt_name,
            provider=context.provider,
            model=context.model,
            attempt=context.attempt,
            elapsed_ms=context.elapsed_ms,
            details=context.details,
        ),
    )


def _verbose_enabled() -> bool:
    value = os.getenv("REVIEW_VERBOSE", "").strip().lower()
    return value in {"1", "true", "yes", "y", "on"}


def _sleep_for_mock_demo() -> None:
    """mock 模式下给前端舞台留出可观察时间；真实 router 调用不额外等待。"""
    if os.getenv("LLM_PROVIDER", "mock").strip().lower() != "mock":
        return
    # 避免本地单测因为 .env 里的演示延迟被拖慢；这个延迟只服务前端开发演示。
    if _running_under_tests():
        return
    delay_sec = _mock_node_delay_sec()
    if delay_sec > 0:
        time.sleep(delay_sec)


def _mock_node_delay_sec() -> float:
    value = os.getenv("MOCK_NODE_DELAY_SEC", "").strip()
    if not value:
        return 0.0
    try:
        return max(0.0, float(value))
    except ValueError:
        return 0.0


def _running_under_tests() -> bool:
    return any(name == "unittest" or name.startswith("tests.") for name in sys.modules)


def _elapsed_ms(start: float) -> int:
    return int((time.perf_counter() - start) * 1000)


def _print_node_event(event: str, node_name: str, **fields: Any) -> None:
    parts = [f"[review-node:{event}]", node_name]
    parts.extend(f"{key}={value}" for key, value in fields.items())
    print(" ".join(parts), flush=True)


def _emit_node_progress(state: GlobalState, event: str, node_name: str, **fields: Any) -> None:
    callback = state.get("node_progress_callback")
    if not callable(callback):
        return
    payload = {
        "event": event,
        "node": node_name,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        **fields,
    }
    try:
        callback(payload)
    except Exception:
        # 进度记录不能影响审稿主流程；如果写 job 状态失败，workflow 仍应继续运行。
        if _verbose_enabled():
            _print_node_event("progress_error", node_name)
