"""
提示词管理模块 - 负责加载和渲染 LLM 提示词模板

核心概念:
- Markdown 文件作为提示词载体 (易读易编辑)
- frontmatter 只保留 prompt 名称和 model id
- 双区块结构: System Prompt + User Prompt Template
- Jinja2 风格的 {{variable}} 模板语法
- 供应商、温度、top_p、max_tokens 等调用参数放在 configs/llm.yaml

文件格式示例:
  ---
  name: reviewer1
  model: gpt-4o-mini
  ---
  # System Prompt
  你是一个资深审稿人...

  # User Prompt Template
  请审阅以下论文: {{paper_title}}
  ...
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class PromptConfig:
    """
    提示词配置数据类

    属性:
        name: 提示词名称 (对应 Markdown 文件名)
        system_prompt: 系统提示词 (定义 AI 角色/行为)
        user_prompt_template: 用户模板 (包含 {{变量}} 占位符)
        model: prompt 声明的模型 ID，由 LLMRouter 查表路由到供应商
        temperature/top_p/max_completion_tokens/thinking: 兼容旧 frontmatter；
            新配置优先放在 configs/llm.yaml
    """
    name: str
    system_prompt: str
    user_prompt_template: str
    model: str
    temperature: float
    top_p: float | None
    max_completion_tokens: int | None
    thinking: str | None


class PromptRepository:
    """
    提示词仓库 - 从 Markdown 文件加载提示词配置

    使用方法:
        repo = PromptRepository(Path("prompts/"))
        config = repo.load("reviewer1")
        prompt_config, rendered = repo.render("reviewer1", {"paper_title": "我的论文"})
    """

    def __init__(self, root: Path) -> None:
        """
        初始化提示词仓库

        Args:
            root: 提示词 Markdown 文件所在目录
        """
        self.root = root

    def load(self, name: str) -> PromptConfig:
        """
        加载指定名称的提示词配置

        Args:
            name: 提示词名称 (不含 .md 后缀)

        Returns:
            PromptConfig: 解析后的提示词配置对象

        Raises:
            FileNotFoundError: 提示词文件不存在
            ValueError: Markdown 格式不合法
        """
        path = self.root / f"{name}.md"
        if not path.exists():
            raise FileNotFoundError(f"prompt markdown not found: {path}")
        # 解析 Markdown 文件的 frontmatter 和内容区块
        metadata, sections = _parse_prompt_markdown(path.read_text(encoding="utf-8"))
        return PromptConfig(
            name=str(metadata.get("name") or name),
            system_prompt=sections["system_prompt"],
            user_prompt_template=sections["user_prompt_template"],
            model=str(metadata.get("model") or ""),
            temperature=float(metadata.get("temperature", 0.2)),
            top_p=_optional_float(metadata.get("top_p")),
            max_completion_tokens=_optional_int(metadata.get("max_completion_tokens")),
            thinking=_optional_str(metadata.get("thinking")),
        )

    def render(self, name: str, context: dict[str, Any]) -> tuple[PromptConfig, str]:
        """
        加载提示词并渲染模板

        Args:
            name: 提示词名称
            context: 模板变量字典

        Returns:
            (PromptConfig, str): 元组 (原始配置, 渲染后的用户提示词)
        """
        prompt = self.load(name)
        return prompt, render_template(prompt.user_prompt_template, context)


def render_template(template: str, context: dict[str, Any]) -> str:
    """
    渲染 Jinja2 风格的提示词模板

    模板语法: {{variable_name}}
    - 简单变量: {{paper_title}} → 替换为 context["paper_title"]
    - 字典/列表: {{keywords}} → 序列化为 JSON 字符串

    Args:
        template: 包含 {{...}} 占位符的模板字符串
        context: 变量名 → 值 的字典

    Returns:
        str: 渲染后的字符串
    """
    def replace(match: re.Match[str]) -> str:
        key = match.group("key").strip()
        value = context.get(key, "")
        # 字典/列表序列化为 JSON，保持结构化数据可读性
        if isinstance(value, (dict, list)):
            return json.dumps(value, ensure_ascii=False, indent=2)
        return str(value)

    return re.sub(r"\{\{\s*(?P<key>[A-Za-z0-9_]+)\s*\}\}", replace, template)


def _parse_prompt_markdown(text: str) -> tuple[dict[str, Any], dict[str, str]]:
    """
    解析提示词 Markdown 文件

    文件格式:
        ---
        name: reviewer1
        temperature: 0.2
        ---
        # System Prompt
        xxx

        # User Prompt Template
        xxx

    Args:
        text: Markdown 文件原始文本

    Returns:
        (metadata, sections):
            - metadata: frontmatter 中的键值对
            - sections: {"system_prompt": xxx, "user_prompt_template": xxx}
    """
    lines = text.splitlines()
    # 检查 frontmatter 开始标记
    if not lines or lines[0].strip() != "---":
        raise ValueError("prompt markdown must start with frontmatter")

    # 找到 frontmatter 结束标记 "---"
    frontmatter_end = next(
        (index for index, line in enumerate(lines[1:], start=1) if line.strip() == "---"),
        None,
    )
    if frontmatter_end is None:
        raise ValueError("prompt markdown frontmatter is not closed")

    # 解析 frontmatter 元数据
    metadata = _parse_frontmatter(lines[1:frontmatter_end])
    # 提取正文中的两个区块
    body = "\n".join(lines[frontmatter_end + 1 :])
    system_prompt = _extract_markdown_section(body, "System Prompt")
    user_prompt_template = _extract_markdown_section(body, "User Prompt Template")
    return metadata, {
        "system_prompt": system_prompt,
        "user_prompt_template": user_prompt_template,
    }


def _parse_frontmatter(lines: list[str]) -> dict[str, Any]:
    """
    解析 YAML-like frontmatter

    支持格式:
        name: reviewer1
        temperature: 0.2
        enabled: true
        options: [a, b, c]

    Args:
        lines: frontmatter 部分的行列表

    Returns:
        dict: 解析后的键值对字典
    """
    metadata: dict[str, Any] = {}
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue  # 跳过空行和注释
        if ":" not in stripped:
            raise ValueError(f"invalid frontmatter line: {line}")
        key, raw_value = stripped.split(":", 1)
        metadata[key.strip()] = _parse_frontmatter_value(raw_value.strip())
    return metadata


def _parse_frontmatter_value(value: str) -> Any:
    """
    解析 frontmatter 中的单个值

    类型推断规则:
    - 空字符串 → None
    - JSON 格式 → 解析为 Python 对象 (true/false/null/数组/对象)
    - 其他 → 字符串

    Args:
        value: 原始值字符串

    Returns:
        Any: 解析后的 Python 对象
    """
    if value == "":
        return None
    try:
        return json.loads(value)  # 尝试解析为 JSON
    except json.JSONDecodeError:
        return value  # 失败则返回原字符串


def _extract_markdown_section(body: str, heading: str) -> str:
    """
    从 Markdown 正文中提取指定标题下的内容

    使用 Markdown 标题 (# heading) 作为区块分隔符

    Args:
        body: Markdown 正文
        heading: 要提取的标题名称

    Returns:
        str: 标题下的内容 (不含标题行)

    Raises:
        ValueError: 标题不存在
    """
    pattern = re.compile(rf"^# {re.escape(heading)}\s*$", re.MULTILINE)
    match = pattern.search(body)
    if match is None:
        raise ValueError(f"missing prompt markdown section: {heading}")

    # 查找下一个区块标题位置
    next_section = re.compile(r"^# (System Prompt|User Prompt Template)\s*$", re.MULTILINE)
    next_match = next_section.search(body, match.end())
    end = next_match.start() if next_match else len(body)
    return body[match.end() : end].strip()


def _optional_float(value: Any) -> float | None:
    """安全转换为 float 或返回 None"""
    if value is None:
        return None
    return float(value)


def _optional_int(value: Any) -> int | None:
    """安全转换为 int 或返回 None"""
    if value is None:
        return None
    return int(value)


def _optional_str(value: Any) -> str | None:
    """安全转换为 str 或返回 None"""
    if value is None:
        return None
    return str(value)
