"""AE终审节点 - v2.0 融入共识分歧识别+DA CRITICAL铁律+R&R追溯矩阵"""
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

from graphs.state import AEFinalInput, AEFinalOutput

logger = logging.getLogger(__name__)


def ae_final_node(
    state: AEFinalInput,
    config: RunnableConfig,
    runtime: Runtime[Context]
) -> AEFinalOutput:
    """
    title: AE综合评审决策
    desc: 综合所有审稿人和反方辩护人意见，识别共识与分歧，遵循DA CRITICAL铁律，生成R&R追溯矩阵
    integrations: 大语言模型
    """
    ctx = runtime.context

    cfg_path = os.path.join(
        os.getenv("COZE_WORKSPACE_PATH"),
        config.get("metadata", {}).get("llm_cfg", "config/ae_final_llm_cfg.json")
    )

    with open(cfg_path, 'r', encoding='utf-8') as f:
        cfg_data = json.load(f)

    llm_config = cfg_data.get("config", {})
    sp_template = cfg_data.get("sp", "")
    up_template = cfg_data.get("up", "")

    up_renderer = Template(up_template)
    user_prompt = up_renderer.render(
        journal_requirements=state.journal_requirements,
        ae_assessment=state.ae_assessment,
        review1_result=json.dumps(state.review1_result, ensure_ascii=False, indent=2) if state.review1_result else "{}",
        review2_result=json.dumps(state.review2_result, ensure_ascii=False, indent=2) if state.review2_result else "{}",
        review3_result=json.dumps(state.review3_result, ensure_ascii=False, indent=2) if state.review3_result else "{}",
        da_result=json.dumps(state.da_result, ensure_ascii=False, indent=2) if state.da_result else "{}",
        paper_rubric=json.dumps(state.paper_rubric, ensure_ascii=False, indent=2) if state.paper_rubric else "{}",
        venue_profile_text=state.venue_profile_text or "未提供目标期刊画像。"
    )

    messages = [
        SystemMessage(content=sp_template),
        HumanMessage(content=user_prompt)
    ]

    client = LLMClient(ctx=ctx)
    response = client.invoke(
        messages=messages,
        model=llm_config.get("model", "kimi-k2-5-260127"),
        temperature=llm_config.get("temperature", 0.3),
        top_p=llm_config.get("top_p", 0.95),
        max_completion_tokens=llm_config.get("max_completion_tokens", 4000),
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

        return AEFinalOutput(
            final_decision=result.get("final_decision", "MAJOR_REVISION"),
            decision_letter=result.get("decision_letter", ""),
            revision_checklist=result.get("revision_checklist", []),
            consensus_disagreement=result.get("consensus_disagreement", {}),
            rr_traceability_matrix=result.get("rr_traceability_matrix", []),
            revision_roadmap=result.get("revision_roadmap", {})
        )
    except (json.JSONDecodeError, ValueError) as e:
        logger.error(f"Failed to parse AE final result: {e}")
        logger.error(f"Content: {content_str[:500]}")
        return AEFinalOutput(
            final_decision="MAJOR_REVISION",
            decision_letter=content_str,
            revision_checklist=[],
            consensus_disagreement={},
            rr_traceability_matrix=[],
            revision_roadmap={}
        )
