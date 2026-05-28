"""Devil's Advocate节点 - ARS反方辩护人: 挑战核心论点、检测逻辑谬误、提出最强反论"""
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

from graphs.state import DAInput, DAOutput

logger = logging.getLogger(__name__)


def devils_advocate_node(
    state: DAInput,
    config: RunnableConfig,
    runtime: Runtime[Context]
) -> DAOutput:
    """
    title: 反方辩护人(Devil's Advocate)
    desc: 专门挑战论文核心论点、检测逻辑谬误、提出最强反论。如果发现CRITICAL问题，最终决策不能是Accept
    integrations: 大语言模型
    """
    ctx = runtime.context

    cfg_path = os.path.join(
        os.getenv("COZE_WORKSPACE_PATH"),
        config.get("metadata", {}).get("llm_cfg", "config/devils_advocate_llm_cfg.json")
    )

    with open(cfg_path, 'r', encoding='utf-8') as f:
        cfg_data = json.load(f)

    llm_config = cfg_data.get("config", {})
    sp_template = cfg_data.get("sp", "")
    up_template = cfg_data.get("up", "")

    up_renderer = Template(up_template)
    user_prompt = up_renderer.render(
        journal_requirements=state.journal_requirements,
        review_focus_points=str(state.review_focus_points),
        paper_content=state.paper_content,
        ae_assessment=state.ae_assessment,
        paper_rubric=json.dumps(state.paper_rubric, ensure_ascii=False, indent=2) if state.paper_rubric else "",
        venue_profile_text=state.venue_profile_text or "未提供目标期刊画像。"
    )

    messages = [
        SystemMessage(content=sp_template),
        HumanMessage(content=user_prompt)
    ]

    client = LLMClient(ctx=ctx)
    response = client.invoke(
        messages=messages,
        model=llm_config.get("model", "doubao-seed-2-0-pro-260215"),
        temperature=llm_config.get("temperature", 0.7),
        top_p=llm_config.get("top_p", 0.95),
        max_completion_tokens=llm_config.get("max_completion_tokens", 3000),
        thinking=llm_config.get("thinking", "disabled")
    )

    content = response.content
    if isinstance(content, list):
        text_parts = []
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

        return DAOutput(
            da_result={
                "summary": result.get("summary", ""),
                "strengths_conceded": result.get("strengths_conceded", []),
                "weaknesses": result.get("weaknesses", []),
                "rating": result.get("rating", 5),
                "rating_justification": result.get("rating_justification", ""),
                "strategic_advice": result.get("strategic_advice", {}),
                "strongest_counter_argument": result.get("strongest_counter_argument", ""),
                "cherry_picking_evidence": result.get("cherry_picking_evidence", ""),
                "confirmation_bias": result.get("confirmation_bias", ""),
                "logic_chain_issues": result.get("logic_chain_issues", []),
                "ignored_alternatives": result.get("ignored_alternatives", [])
            }
        )
    except (json.JSONDecodeError, ValueError) as e:
        logger.error(f"Failed to parse DA result: {e}")
        logger.error(f"Content: {content_str[:500]}")
        return DAOutput(
            da_result={
                "summary": "",
                "strengths_conceded": [],
                "weaknesses": ["JSON解析失败"],
                "rating": 5,
                "rating_justification": "解析失败",
                "strategic_advice": {},
                "strongest_counter_argument": content_str[:300] if len(content_str) > 300 else content_str,
                "cherry_picking_evidence": "",
                "confirmation_bias": "",
                "logic_chain_issues": [],
                "ignored_alternatives": []
            }
        )
