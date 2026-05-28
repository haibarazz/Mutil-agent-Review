"""内容审查节点 - 用LLM判断上传内容是否为学术论文"""
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

from graphs.state import ContentCheckInput, ContentCheckOutput

logger = logging.getLogger(__name__)


def content_check_node(state: ContentCheckInput, config: RunnableConfig, runtime: Runtime[Context]) -> ContentCheckOutput:
    """
    title: 论文内容审查
    desc: 用LLM分析上传文件的内容，判断是否为学术论文，非论文内容提醒用户重新上传
    integrations: 大语言模型
    """
    ctx = runtime.context

    # 截取前2000字作为预览，避免token过多
    content_preview: str = state.paper_content[:2000] if state.paper_content else ""

    if not content_preview.strip():
        return ContentCheckOutput(
            intent="NOT_PAPER",
            content_check_result="内容为空，无法判断",
            formatted_output="⚠️ 上传的文件内容为空，请确认文件是否损坏后重新上传。",
        )

    # 读取LLM配置
    cfg_file: str = os.path.join(os.getenv("COZE_WORKSPACE_PATH", ""), config['metadata']['llm_cfg'])
    with open(cfg_file, 'r', encoding='utf-8') as fd:
        _cfg: dict = json.load(fd)

    llm_config: dict = _cfg.get("config", {})
    sp: str = _cfg.get("sp", "")
    up_tpl_str: str = _cfg.get("up", "")

    # 渲染用户提示词
    up_tpl: Template = Template(up_tpl_str)
    user_prompt: str = up_tpl.render({"content_preview": content_preview})

    # 调用LLM
    try:
        llm_client = LLMClient(ctx=ctx)
        messages = [
            SystemMessage(content=sp),
            HumanMessage(content=user_prompt)
        ]
        response = llm_client.invoke(
            messages=messages,
            model=llm_config.get("model", "doubao-seed-2-0-pro-260215"),
            temperature=llm_config.get("temperature", 0.0),
            top_p=llm_config.get("top_p", 0.9),
            max_completion_tokens=llm_config.get("max_completion_tokens", 256),
            thinking=llm_config.get("thinking", "disabled")
        )

        # 安全提取文本内容
        resp_content = response.content
        if isinstance(resp_content, list):
            text_parts = []
            for item in resp_content:
                if isinstance(item, dict) and item.get("type") == "text":
                    text_parts.append(item.get("text", ""))
                elif isinstance(item, str):
                    text_parts.append(item)
            content_str = " ".join(text_parts).strip()
        else:
            content_str = str(resp_content).strip()

        if not content_str:
            # LLM返回空，默认放行
            return ContentCheckOutput(
                intent="VALID_PAPER",
                content_check_result="LLM返回为空，默认放行",
                formatted_output="",
            )

        # 解析JSON
        # 去除thinking标签
        think_pattern = re.compile(r'<think[^>]*>.*?</think\s*>', re.DOTALL)
        content_str = think_pattern.sub('', content_str).strip()

        if "```json" in content_str:
            content_str = content_str.split("```json")[1].split("```")[0].strip()
        elif "```" in content_str:
            content_str = content_str.split("```")[1].split("```")[0].strip()

        first_brace: int = content_str.find('{')
        last_brace: int = content_str.rfind('}')
        if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
            content_str = content_str[first_brace:last_brace + 1]

        result: dict = json.loads(content_str)
        is_paper: bool = result.get("is_paper", True)
        reason: str = result.get("reason", "")

        if is_paper:
            return ContentCheckOutput(
                intent="VALID_PAPER",
                content_check_result=f"内容审查通过：{reason}",
                formatted_output="",
            )
        else:
            return ContentCheckOutput(
                intent="NOT_PAPER",
                content_check_result=f"非论文内容：{reason}",
                formatted_output=f"⚠️ 上传的内容不是学术论文（{reason}）。请上传您的论文手稿，支持的格式：PDF、Word(docx)、LaTeX(tex)。",
            )

    except (json.JSONDecodeError, ValueError) as e:
        logger.error(f"Content check JSON parse error: {e}")
        # JSON解析失败，默认放行，避免误拦截
        return ContentCheckOutput(
            intent="VALID_PAPER",
            content_check_result=f"JSON解析失败，默认放行: {e}",
            formatted_output="",
        )
    except Exception as e:
        logger.error(f"Content check error: {e}")
        # 异常时默认放行
        return ContentCheckOutput(
            intent="VALID_PAPER",
            content_check_result=f"审查异常，默认放行: {e}",
            formatted_output="",
        )
