from __future__ import annotations

import json
import threading
from collections import Counter
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Iterator

from src.core.models import to_jsonable


_current_run_id: ContextVar[str] = ContextVar("llm_diagnostics_run_id", default="")
_collectors: dict[str, "LLMCallCollector"] = {}
_lock = threading.RLock()


@dataclass
class LLMCallCollector:
    """收集单个 run 内的 LLM 调用事件；只存安全摘要，不存 prompt 正文。"""

    run_id: str
    events: list[dict[str, Any]] = field(default_factory=list)
    model_output_errors: list[dict[str, Any]] = field(default_factory=list)

    def append(self, event: str, fields: dict[str, Any]) -> None:
        payload = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event": event,
            **_safe_fields(fields),
        }
        self.events.append(payload)

    def summary(self) -> dict[str, int]:
        return {
            "event_count": len(self.events),
            "call_count": sum(1 for event in self.events if event.get("event") == "start"),
            "error_count": sum(1 for event in self.events if event.get("event") == "error"),
            "fallback_count": sum(1 for event in self.events if event.get("event") == "fallback"),
        }

    def attempt_summary(self) -> dict[str, Any]:
        """面向 diagnostics 的轻量重试摘要；完整逐次事件仍以 jsonl 保存。"""
        error_events = [event for event in self.events if event.get("event") == "error"]
        fallback_events = [event for event in self.events if event.get("event") == "fallback"]
        summary: dict[str, Any] = {
            "retry_error_count": sum(1 for event in error_events if _truthy(event.get("retryable"))),
            "fallback_count": len(fallback_events),
            "error_type_counts": dict(Counter(str(event.get("error_type") or "Unknown") for event in error_events)),
        }
        if error_events:
            summary["last_error"] = _compact_event(error_events[-1])
        if fallback_events:
            summary["last_fallback"] = _compact_event(fallback_events[-1])
        return summary

    def to_jsonl(self) -> str:
        return "\n".join(json.dumps(to_jsonable(event), ensure_ascii=False) for event in self.events)

    def append_model_output_error(self, kind: str, fields: dict[str, Any], payload: dict[str, Any]) -> dict[str, str]:
        safe_kind = _safe_artifact_kind(kind)
        index = sum(1 for item in self.model_output_errors if item.get("kind") == safe_kind) + 1
        ref = f"model_output_errors/{safe_kind}_{index:03d}.json"
        # 只把模型输出作为本地 ignored artifact 保存；llm_calls 里保留短 preview 方便快速定位。
        self.model_output_errors.append({
            "kind": safe_kind,
            "path": ref,
            "payload": {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "kind": safe_kind,
                "metadata": _safe_fields(fields),
                **to_jsonable(payload),
            },
        })
        return {
            "model_output_error_kind": safe_kind,
            "model_output_error_ref": ref,
            "model_output_preview": _safe_json_preview(payload),
        }


def start_llm_call_collection(run_id: str) -> LLMCallCollector:
    with _lock:
        collector = LLMCallCollector(run_id=run_id)
        _collectors[run_id] = collector
        return collector


def stop_llm_call_collection(run_id: str) -> LLMCallCollector:
    with _lock:
        return _collectors.pop(run_id, LLMCallCollector(run_id=run_id))


@contextmanager
def llm_diagnostics_run(run_id: str | None) -> Iterator[None]:
    token = _current_run_id.set(str(run_id or ""))
    try:
        yield
    finally:
        _current_run_id.reset(token)


def record_llm_event(event: str, fields: dict[str, Any]) -> None:
    run_id = _current_run_id.get()
    if not run_id:
        return
    with _lock:
        collector = _collectors.get(run_id)
        if collector is None:
            return
        collector.append(event, fields)


def record_model_output_error(kind: str, fields: dict[str, Any], payload: dict[str, Any]) -> dict[str, str]:
    run_id = _current_run_id.get()
    if not run_id:
        return {}
    with _lock:
        collector = _collectors.get(run_id)
        if collector is None:
            return {}
        return collector.append_model_output_error(kind, fields, payload)


def _safe_fields(fields: dict[str, Any]) -> dict[str, Any]:
    # 白名单字段：避免误把 prompt 正文、API key、响应正文写进本地产物。
    allowed = {
        "kind",
        "prompt",
        "requested_model",
        "model",
        "provider",
        "provider_model",
        "attempt",
        "max_attempts",
        "fallback",
        "from_model",
        "to_model",
        "reason",
        "temperature",
        "top_p",
        "max_tokens",
        "system_chars",
        "user_chars",
        "input_tokens",
        "output_tokens",
        "total_tokens",
        "estimated_cost_usd",
        "pricing_source",
        "elapsed_ms",
        "error_type",
        "error_message",
        "retryable",
        "next_action",
        "model_output_error_kind",
        "model_output_error_ref",
        "model_output_preview",
    }
    return {
        key: _safe_text(value) if key in {"error_message", "model_output_preview"} else value
        for key, value in fields.items()
        if key in allowed and value not in ("", None)
    }


def _compact_event(event: dict[str, Any]) -> dict[str, Any]:
    keys = (
        "event",
        "prompt",
        "requested_model",
        "model",
        "provider",
        "provider_model",
        "attempt",
        "max_attempts",
        "fallback",
        "error_type",
        "error_message",
        "retryable",
        "next_action",
        "from_model",
        "to_model",
        "reason",
        "model_output_error_kind",
        "model_output_error_ref",
        "model_output_preview",
    )
    return {key: event[key] for key in keys if key in event}


def _truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "y", "on"}


def _safe_text(value: Any, *, limit: int = 500) -> str:
    text = str(value).replace("\n", " ").strip()
    if len(text) <= limit:
        return text
    return text[: limit - 3].rstrip() + "..."


def _safe_json_preview(value: Any, *, limit: int = 1000) -> str:
    return _safe_text(json.dumps(to_jsonable(value), ensure_ascii=False), limit=limit)


def _safe_artifact_kind(kind: str) -> str:
    return "".join(char if char.isalnum() else "_" for char in kind.strip().lower()).strip("_") or "model_output_error"
