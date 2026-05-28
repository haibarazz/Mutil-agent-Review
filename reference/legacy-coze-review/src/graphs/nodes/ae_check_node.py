"""AE责任编辑筛选节点 - v2.0 融入论文专属评分标准(ReviewGrounder)"""
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

from graphs.state import AECheckInput, AECheckOutput

logger = logging.getLogger(__name__)


def ae_check_node(
    state: AECheckInput,
    config: RunnableConfig,
    runtime: Runtime[Context]
) -> AECheckOutput:
    """
    title: AE责任编辑筛选
    desc: 进一步评估稿件，生成论文专属评分标准(rubric)，判断是否送外审
    integrations: 大语言模型
    """
    ctx = runtime.context

    # 读取配置文件
    cfg_path = os.path.join(
        os.getenv("COZE_WORKSPACE_PATH"),
        config.get("metadata", {}).get("llm_cfg", "config/ae_check_llm_cfg.json")
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
        se_summary=state.se_summary,
        se_concerns=str(state.se_concerns),
        se_quality_score=state.se_quality_score,
        paper_content=state.paper_content,
        field_info=json.dumps(state.field_info, ensure_ascii=False, indent=2) if state.field_info else "",
        reviewer_config=json.dumps(state.reviewer_config, ensure_ascii=False, indent=2) if state.reviewer_config else "",
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
        model=llm_config.get("model", "kimi-k2-5-260127"),
        temperature=llm_config.get("temperature", 0.3),
        top_p=llm_config.get("top_p", 0.95),
        max_completion_tokens=llm_config.get("max_completion_tokens", 3000),
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

        return AECheckOutput(
            ae_decision=result.get("decision", "SEND_FOR_REVIEW"),
            ae_assessment=result.get("ae_assessment", ""),
            review_focus_points=result.get("review_focus_points", []),
            ae_rejection_letter=result.get("rejection_letter", ""),
            paper_rubric=result.get("paper_rubric", {}),
            ae_desk_reject_types=result.get("desk_reject_types", [])
        )
    except (json.JSONDecodeError, ValueError) as e:
        logger.error(f"Failed to parse AE check result: {e}")
        logger.error(f"Content: {content_str[:500]}")
        return AECheckOutput(
            ae_decision="SEND_FOR_REVIEW",
            ae_assessment="无法解析评估结果",
            review_focus_points=["请审稿人全面评审"],
            ae_rejection_letter="",
            paper_rubric={},
            ae_desk_reject_types=[]
        )
