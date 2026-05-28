"""领域分析节点 - ARS Phase 0: 自动识别论文领域并动态配置审稿人"""
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

from graphs.state import FieldAnalystInput, FieldAnalystOutput

logger = logging.getLogger(__name__)


def field_analyst_node(
    state: FieldAnalystInput,
    config: RunnableConfig,
    runtime: Runtime[Context]
) -> FieldAnalystOutput:
    """
    title: 论文领域分析
    desc: 自动识别论文的学科领域、研究范式和方法类型，动态生成审稿人配置卡
    integrations: 大语言模型
    """
    ctx = runtime.context

    # 读取配置文件
    cfg_path = os.path.join(
        os.getenv("COZE_WORKSPACE_PATH"),
        config.get("metadata", {}).get("llm_cfg", "config/field_analyst_llm_cfg.json")
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
        paper_content=state.paper_content
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
        temperature=llm_config.get("temperature", 0.2),
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

        return FieldAnalystOutput(
            field_info=result.get("field_info", {}),
            reviewer_config=result.get("reviewer_config", {})
        )
    except (json.JSONDecodeError, ValueError) as e:
        logger.error(f"Failed to parse field analyst result: {e}")
        logger.error(f"Content: {content_str[:500]}")
        # 返回默认值
        return FieldAnalystOutput(
            field_info={
                "primary_discipline": "未识别",
                "secondary_discipline": "未识别",
                "research_paradigm": "未识别",
                "methodology_type": "未识别",
                "paper_maturity": "unknown"
            },
            reviewer_config={
                "reviewer_1": "方法论专家 - 专注研究设计与统计分析",
                "reviewer_2": "领域专家 - 专注理论框架与文献覆盖",
                "reviewer_3": "跨学科视角专家 - 专注实践影响与基本假设挑战",
                "devils_advocate": "反方辩护人 - 专门挑战核心论点与检测逻辑谬误"
            }
        )
