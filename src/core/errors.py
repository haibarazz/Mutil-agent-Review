from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ErrorContext:
    """跨 LLM/router/node 共用的错误上下文；后续会直接落盘到 diagnostics。"""

    node: str = ""
    prompt_name: str = ""
    provider: str = ""
    model: str = ""
    attempt: int = 0
    elapsed_ms: int | None = None
    details: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "node": self.node,
            "prompt_name": self.prompt_name,
            "provider": self.provider,
            "model": self.model,
            "attempt": self.attempt,
        }
        if self.elapsed_ms is not None:
            payload["elapsed_ms"] = self.elapsed_ms
        if self.details:
            payload["details"] = self.details
        return {key: value for key, value in payload.items() if value not in ("", None, {})}


class ReviewAgentError(Exception):
    """审稿系统的可分类基础异常。"""

    code = "review_agent_error"
    recoverable = False
    retryable = False

    def __init__(self, message: str, *, context: ErrorContext | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.context = context or ErrorContext()

    def to_dict(self) -> dict[str, Any]:
        return {
            "error_type": self.__class__.__name__,
            "code": self.code,
            "message": self.message,
            "recoverable": self.recoverable,
            "retryable": self.retryable,
            **self.context.to_dict(),
        }


class ProviderTransientError(ReviewAgentError):
    """供应商临时错误：timeout、连接失败、429、5xx。"""

    code = "provider_transient_error"
    recoverable = True
    retryable = True


class ProviderFatalError(ReviewAgentError):
    """供应商不可重试错误：401、403、模型不存在、API key 错。"""

    code = "provider_fatal_error"
    recoverable = False
    retryable = False


class ConfigurationError(ReviewAgentError):
    """本地配置错误：.env、llm.yaml 或 prompt model id 配置不完整/不匹配。"""

    code = "configuration_error"
    recoverable = False
    retryable = False


class ProviderCapabilityError(ReviewAgentError):
    """供应商能力不匹配：不支持 json_object、schema output 或工具调用等。"""

    code = "provider_capability_error"
    recoverable = True
    retryable = False


class ModelOutputParseError(ReviewAgentError):
    """模型输出无法解析成目标结构，例如 JSON 严重损坏。"""

    code = "model_output_parse_error"
    recoverable = True
    retryable = True


class ModelOutputValidationError(ReviewAgentError):
    """模型输出结构合法，但缺字段或违反业务数量约束。"""

    code = "model_output_validation_error"
    recoverable = True
    retryable = True


class NodeRecoverableError(ReviewAgentError):
    """节点失败但可通过 retry、fallback 或 partial report 恢复。"""

    code = "node_recoverable_error"
    recoverable = True
    retryable = True


class NodeFatalError(ReviewAgentError):
    """节点失败且继续运行无意义，例如本地配置损坏或 renderer 代码错误。"""

    code = "node_fatal_error"
    recoverable = False
    retryable = False
