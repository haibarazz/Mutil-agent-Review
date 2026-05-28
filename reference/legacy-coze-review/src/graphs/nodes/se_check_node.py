"""SE主编初审节点 - v2.0 融入反谦逊评分+领域感知"""
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

from graphs.state import SECheckInput, SECheckOutput

logger = logging.getLogger(__name__)


def se_check_node(
    state: SECheckInput,
    config: RunnableConfig,
    runtime: Runtime[Context]
) -> SECheckOutput:
    """
    title: SE主编初审
    desc: 对新投稿进行初步桌面审查，融入反谦逊评分和领域感知，判断是否值得进入外审流程
    integrations: 大语言模型
    """
    ctx = runtime.context

    # 读取配置文件
    cfg_path = os.path.join(
        os.getenv("COZE_WORKSPACE_PATH"),
        config.get("metadata", {}).get("llm_cfg", "config/se_check_llm_cfg.json")
    )

    with open(cfg_path, 'r', encoding='utf-8') as f:
        cfg_data = json.load(f)

    llm_config = cfg_data.get("config", {})
    sp_template = cfg_data.get("sp", "")
    up_template = cfg_data.get("up", "")

    # 渲染提示词
    up_renderer = Template(up_template)
    user_prompt = up_renderer.render(
        journal_requirements=state.journal_requirements,
        submission_type=state.submission_type,
        paper_content=state.paper_content,
        field_info=json.dumps(state.field_info, ensure_ascii=False, indent=2) if state.field_info else "领域信息尚未获取",
        venue_profile_text=state.venue_profile_text or "未提供目标期刊画像。"
    )

    # 构建消息
    messages = [
        SystemMessage(content=sp_template),
        HumanMessage(content=user_prompt)
    ]

    # 调用LLM
    client = LLMClient(ctx=ctx)
    response = client.invoke(
        messages=messages,
        model=llm_config.get("model", "doubao-seed-2-0-pro-260215"),
        temperature=llm_config.get("temperature", 0.3),
        top_p=llm_config.get("top_p", 0.95),
        max_completion_tokens=llm_config.get("max_completion_tokens", 2000),
        thinking=llm_config.get("thinking", "disabled")
    )

    # 解析响应
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

    # 尝试解析JSON
    try:
        # 去除thinking模式的思考内容（<think...</think标签）
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

        return SECheckOutput(
            se_decision=result.get("decision", "PASS"),
            se_summary=result.get("summary", ""),
            se_concerns=result.get("concerns", []),
            se_rejection_letter=result.get("rejection_letter", ""),
            se_quality_score=result.get("quality_score", 50),
            se_desk_reject_types=result.get("desk_reject_types", [])
        )
    except (json.JSONDecodeError, ValueError) as e:
        logger.error(f"Failed to parse SE check result: {e}")
        logger.error(f"Content: {content_str[:500]}")
        return SECheckOutput(
            se_decision="PASS",
            se_summary="无法解析审查结果",
            se_concerns=["JSON解析失败"],
            se_rejection_letter="",
            se_quality_score=50,
            se_desk_reject_types=[]
        )
