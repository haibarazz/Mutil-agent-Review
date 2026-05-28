"""期刊要求收集节点 - v3.0 三路径收集期刊投稿要求(上传文档/联网搜索+抓取/默认通用)"""
import os
import json
import logging
from jinja2 import Template
from langchain_core.runnables import RunnableConfig
from langgraph.runtime import Runtime
from coze_coding_utils.runtime_ctx.context import Context
from coze_coding_dev_sdk import LLMClient, SearchClient
from coze_coding_dev_sdk.fetch import FetchClient
from langchain_core.messages import SystemMessage, HumanMessage
from utils.file.file import FileOps

from graphs.state import JournalReqCollectorInput, JournalReqCollectorOutput

logger = logging.getLogger(__name__)

# 默认通用学术审稿标准
DEFAULT_JOURNAL_REQUIREMENTS = """## 通用学术期刊审稿标准

1. **原创性与创新性**：论文应提出新的研究问题、新的方法或有意义的新发现
2. **方法论严谨性**：研究方法应合理、可重复，实验设计严谨
3. **文献综述**：应充分覆盖相关领域文献，清晰定位研究贡献
4. **结果与分析**：实验结果应充分支持结论，数据分析严谨
5. **写作质量**：论文应逻辑清晰、表达准确、结构完整
6. **伦理合规**：研究应符合学术伦理规范

**格式要求**：一般要求双栏排版，8-10页正文，含摘要、关键词、参考文献。"""


def _extract_from_uploaded_file(file_obj, ctx) -> str:
    """路径1: 从用户上传的期刊要求文档中提取文本。"""
    try:
        text = FileOps.extract_text(file_obj)
        if text and not text.startswith("[FileOps Error]"):
            return text
    except Exception as e:
        logger.warning(f"Failed to extract journal requirements from uploaded file: {e}")
    return ""


def _search_and_fetch_journal_requirements(journal_name: str, ctx) -> str:
    """路径2: 搜索期刊投稿指南页面并抓取完整内容。"""
    search_query = f"{journal_name} author guidelines submission requirements 投稿指南"

    try:
        search_client = SearchClient(ctx=ctx)
        response = search_client.search(
            query=search_query,
            search_type="web",
            count=5,
            need_url=True,
            need_summary=True,
        )

        target_url = ""
        for item in response.web_items:
            if item.url and ("author" in item.url.lower() or "submit" in item.url.lower() or "guideline" in item.url.lower()):
                target_url = item.url
                break

        if not target_url and response.web_items:
            target_url = response.web_items[0].url

        if not target_url:
            return ""

        # 用FetchClient抓取完整页面内容
        fetch_client = FetchClient(ctx=ctx)
        fetch_response = fetch_client.fetch(url=target_url)

        if fetch_response.status_code and fetch_response.status_code >= 400:
            logger.warning(f"Fetch failed with status {fetch_response.status_code}")
            return ""

        if fetch_response.content:
            text_parts: list[str] = []
            for item in fetch_response.content:
                if item.type == "text" and item.text:
                    text_parts.append(item.text)
            full_text = "\n".join(text_parts)
            if len(full_text) > 5000:
                full_text = full_text[:5000]
            return full_text

    except Exception as e:
        logger.warning(f"Failed to search/fetch journal requirements: {e}")

    return ""


def _load_venue_profile(venue_code: str) -> str:
    """根据venue_code加载期刊/会议画像文件，提取智能体提示词片段。"""
    if not venue_code:
        return ""

    base_path = os.getenv("COZE_WORKSPACE_PATH", "")
    candidates = [
        os.path.join(base_path, "CCFA", f"{venue_code}_CCFA.md"),
        os.path.join(base_path, "ut d", f"{venue_code}_UTD_FT50.md"),
        os.path.join(base_path, "ut d", f"{venue_code}_UTD.md"),
        os.path.join(base_path, "ut d", f"{venue_code}_FT50.md"),
    ]

    file_path = ""
    for c in candidates:
        if os.path.isfile(c):
            file_path = c
            break

    if not file_path:
        logger.warning(f"[VenueProfile] 未找到venue_code='{venue_code}'对应的画像文件")
        return ""

    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
    except Exception as e:
        logger.warning(f"[VenueProfile] 读取文件失败: {file_path}, error={e}")
        return ""

    # 提取 "## 智能体提示词片段" section
    marker = "## 智能体提示词片段"
    idx = content.find(marker)
    if idx == -1:
        # 如果没找到标记，取前3000字符作为兜底
        profile = content[:3000]
    else:
        start = idx + len(marker)
        # 找到下一个 ## 开头的行作为结束
        next_header = content.find("\n## ", start)
        if next_header == -1:
            profile = content[start:].strip()
        else:
            profile = content[start:next_header].strip()

    # 清理 ```text 和 ``` 代码块标记
    profile = profile.replace("```text", "").replace("```", "").strip()

    # 截断到合理长度
    if len(profile) > 4000:
        profile = profile[:4000] + "\n...[画像内容截断]"

    logger.info(f"[VenueProfile] 成功加载 '{venue_code}' 画像，长度={len(profile)}")
    return profile


def _llm_extract_requirements(raw_text: str, journal_name: str, ctx, cfg_data: dict) -> str:
    """用LLM从原始文本中提取结构化的期刊要求。"""
    sp = cfg_data.get("sp", "")
    up_template = cfg_data.get("up", "")

    up_renderer = Template(up_template)
    user_prompt = up_renderer.render(
        journal_name=journal_name or "未指定",
        raw_text=raw_text[:6000]
    )

    llm_config = cfg_data.get("config", {})
    messages = [
        SystemMessage(content=sp),
        HumanMessage(content=user_prompt)
    ]

    client = LLMClient(ctx=ctx)
    response = client.invoke(
        messages=messages,
        model=llm_config.get("model", "doubao-seed-2-0-lite-260215"),
        temperature=llm_config.get("temperature", 0.2),
        top_p=llm_config.get("top_p", 0.95),
        max_completion_tokens=llm_config.get("max_completion_tokens", 2000),
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
        return " ".join(text_parts).strip()
    return str(content).strip()


def journal_req_collector_node(
    state: JournalReqCollectorInput,
    config: RunnableConfig,
    runtime: Runtime[Context]
) -> JournalReqCollectorOutput:
    """
    title: 期刊要求收集
    desc: 三路径收集期刊投稿要求：上传文档提取/联网搜索+抓取/默认通用标准
    integrations: 大语言模型, 网络搜索, URL内容抓取
    """
    ctx = runtime.context

    cfg_path = os.path.join(
        os.getenv("COZE_WORKSPACE_PATH"),
        config.get("metadata", {}).get("llm_cfg", "config/journal_req_collector_llm_cfg.json")
    )

    with open(cfg_path, 'r', encoding='utf-8') as f:
        cfg_data = json.load(f)

    # 步骤0: 加载预设期刊/会议画像（如果有venue_code）
    venue_profile_text = ""
    if state.venue_code:
        venue_profile_text = _load_venue_profile(state.venue_code)
    elif state.journal_name:
        # 如果用户手动输入了期刊名，尝试用它作为venue_code匹配
        venue_profile_text = _load_venue_profile(state.journal_name)

    raw_text = ""

    # 路径1: 用户上传了期刊要求文档
    if state.journal_requirements_file is not None:
        logger.info("[JournalReq] 路径1: 从上传文档提取期刊要求")
        raw_text = _extract_from_uploaded_file(state.journal_requirements_file, ctx)
        if raw_text:
            extracted = _llm_extract_requirements(raw_text, state.journal_name, ctx, cfg_data)
            if extracted:
                return JournalReqCollectorOutput(journal_requirements=extracted, venue_profile_text=venue_profile_text)

    # 路径2: 用户提供了期刊名，联网搜索+抓取
    if state.journal_name:
        logger.info(f"[JournalReq] 路径2: 搜索期刊'{state.journal_name}'的投稿指南")
        raw_text = _search_and_fetch_journal_requirements(state.journal_name, ctx)
        if raw_text:
            extracted = _llm_extract_requirements(raw_text, state.journal_name, ctx, cfg_data)
            if extracted:
                return JournalReqCollectorOutput(journal_requirements=extracted, venue_profile_text=venue_profile_text)

    # 路径3: 默认通用学术审稿标准
    logger.info("[JournalReq] 路径3: 使用默认通用学术审稿标准")
    return JournalReqCollectorOutput(journal_requirements=DEFAULT_JOURNAL_REQUIREMENTS, venue_profile_text=venue_profile_text)
