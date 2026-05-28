"""审稿人3节点 - v3.0 写作表达专家(0-100评分+引用段落+非重叠视角+动态persona)"""
import os
import json
import re
import logging
from jinja2 import Template
from langchain_core.runnables import RunnableConfig
from langgraph.runtime import Runtime
from coze_coding_utils.runtime_ctx.context import Context
from coze_coding_dev_sdk import LLMClient
from langchain_core.messages import SystemMessage, HumanMessage

from graphs.state import ReviewerInput, Reviewer3Output

logger = logging.getLogger(__name__)

# 默认persona（reviewer_config为空时使用）
_DEFAULT_PERSONA = "跨学科视角专家 - 专注跨学科连接、实践影响与基本假设挑战"


def _get_persona(reviewer_config: dict, key: str, default: str) -> str:
    """从动态审稿人配置中提取指定审稿人的persona。"""
    if not reviewer_config:
        return default
    persona = reviewer_config.get(key, "")
    if isinstance(persona, str) and persona.strip():
        return persona.strip()
    if isinstance(persona, dict):
        name = persona.get("name", persona.get("role", ""))
        expertise = persona.get("expertise", persona.get("focus", ""))
        if name and expertise:
            return f"{name} - {expertise}"
        if name:
            return name
    return default


def reviewer3_node(
    state: ReviewerInput,
    config: RunnableConfig,
    runtime: Runtime[Context]
) -> Reviewer3Output:
    """
    title: 审稿人3-写作表达专家
    desc: 从论文写作质量、逻辑结构和表达清晰度角度评审论文，使用0-100校准评分
    integrations: 大语言模型
    """
    ctx = runtime.context

    cfg_path = os.path.join(
        os.getenv("COZE_WORKSPACE_PATH"),
        config.get("metadata", {}).get("llm_cfg", "config/reviewer3_llm_cfg.json")
    )

    with open(cfg_path, 'r', encoding='utf-8') as f:
        cfg_data = json.load(f)

    llm_config = cfg_data.get("config", {})
    sp_template = cfg_data.get("sp", "")
    up_template = cfg_data.get("up", "")

    # 从reviewer_config中提取当前审稿人的persona（修复P0数据流断裂）
    reviewer_key = state.reviewer_key or "reviewer_3"
    persona = _get_persona(state.reviewer_config, reviewer_key, _DEFAULT_PERSONA)

    up_renderer = Template(up_template)
    user_prompt = up_renderer.render(
        journal_requirements=state.journal_requirements,
        review_focus_points=str(state.review_focus_points),
        paper_content=state.paper_content,
        ae_assessment=state.ae_assessment,
        paper_rubric=json.dumps(state.paper_rubric, ensure_ascii=False, indent=2) if state.paper_rubric else "",
        reviewer_persona=persona,
        venue_profile_text=state.venue_profile_text or "未提供目标期刊画像。"
    )

    messages = [
        SystemMessage(content=sp_template),
        HumanMessage(content=user_prompt)
    ]

    client = LLMClient(ctx=ctx)
    response = client.invoke(
        messages=messages,
        model=llm_config.get("model", "glm-4-7-251222"),
        temperature=llm_config.get("temperature", 0.6),
        top_p=llm_config.get("top_p", 0.95),
        max_completion_tokens=llm_config.get("max_completion_tokens", 3000),
        thinking=llm_config.get("thinking", "disabled")
    )

    content = response.content
    if isinstance(content, list):
        text_parts: list[str] = []
        for item in content:
            if isinstance(item, dict) and item.get("type") == "text":
                text_parts.append(item.get("text", ""))
            elif isinstance(item, str):
                text_parts.append(item)
        content_str = " ".join(text_parts).strip()
    else:
        content_str = str(content).strip()

    try:
        # 去除thinking模式的思考内容
        think_pattern = re.compile(r'<think[^>]*>.*?</think\s*>', re.DOTALL)
        content_str = think_pattern.sub('', content_str).strip()

        if "```json" in content_str:
            content_str = content_str.split("```json")[1].split("```")[0].strip()
        elif "```" in content_str:
            content_str = content_str.split("```")[1].split("```")[0].strip()

        # 尝试找到第一个 { 和最后一个 } 之间的内容
        first_brace = content_str.find('{')
        last_brace = content_str.rfind('}')
        if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
            content_str = content_str[first_brace:last_brace + 1]

        result = json.loads(content_str)

        return Reviewer3Output(
            review3_result={
                "summary": result.get("summary", ""),
                "strengths": result.get("strengths", []),
                "weaknesses": result.get("weaknesses", []),
                "rating": result.get("rating", 5),
                "rating_justification": result.get("rating_justification", ""),
                "strategic_advice": result.get("strategic_advice", {}),
                "recommendation": result.get("recommendation", "MAJOR_REVISION"),
                "evidence_citations": result.get("evidence_citations", [])
            }
        )
    except (json.JSONDecodeError, ValueError) as e:
        logger.error(f"Failed to parse reviewer3 result: {e}")
        return Reviewer3Output(
            review3_result={
                "summary": "",
                "strengths": [],
                "weaknesses": ["JSON解析失败，请重新评审"],
                "rating": 5,
                "rating_justification": "解析失败",
                "strategic_advice": {},
                "recommendation": "MAJOR_REVISION",
                "evidence_citations": []
            }
        )
