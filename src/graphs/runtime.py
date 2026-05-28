"""
运行时模块 - 提供 LangGraph 节点的依赖注入容器

负责初始化 LLM、Parser、Search、Prompts 等核心组件，
并通过 ReviewNodes 统一提供给各个 LangGraph 节点使用。

采用单例模式 (通过 @lru_cache)，确保整个审稿流程复用同一套组件实例。
"""
from __future__ import annotations

from functools import lru_cache

from src.infra.llm import MockLLMClient, OpenAICompatibleLLMClient
from src.infra.llm_router import LLMRouter, load_llm_router_config
from src.infra.parser import build_document_parser
from src.infra.search import NullSearchClient
from src.core.venues import VenueRepository
from src.core.prompts import PromptRepository
from src.infra.settings import load_settings
from src.graphs.review_nodes import ReviewNodes


@lru_cache(maxsize=1)
def get_review_nodes() -> ReviewNodes:
    """
    获取 ReviewNodes 单例实例

    这是 LangGraph 节点的核心依赖注入点。
    初始化过程:
    1. 加载环境配置 (settings)
    2. 构建文档解析器 (parser)
    3. 构建搜索客户端 (search, 目前是 NullSearchClient 空实现)
    4. 构建提示词仓库 (prompts)
    5. 根据 LLM_PROVIDER 配置构建 LLM 客户端:
       - "router": 使用 configs/llm.yaml 按 model id 路由到不同供应商
       - "openai_compatible": 使用 OpenAI 兼容接口
       - 其他: 使用 MockLLMClient (用于测试/无 API Key 场景)

    Returns:
        ReviewNodes: 包含所有节点业务逻辑依赖的容器对象
    """
    settings = load_settings()
    parser = build_document_parser(settings) # 解析我们的文档
    search = NullSearchClient()
    prompts = PromptRepository(settings.prompts_dir)

    if settings.llm_provider == "router":
        # Router 模式: prompts 只写 model id，具体供应商由 configs/llm.yaml 决定
        llm = LLMRouter(
            config=load_llm_router_config(settings.llm_config_path),
            timeout_sec=settings.llm_timeout_sec,
        )
    elif settings.llm_provider == "openai_compatible":
        # OpenAI 兼容模式 (如 vLLM / LocalAI / Groq 等)
        if not settings.llm_base_url or not settings.llm_api_key:
            raise RuntimeError("LLM_BASE_URL and LLM_API_KEY are required for openai_compatible")
        llm = OpenAICompatibleLLMClient(
            base_url=settings.llm_base_url,
            api_key=settings.llm_api_key,
            default_model=settings.llm_default_model,
            timeout_sec=settings.llm_timeout_sec,
        )
    else:
        # Mock 模式: 用于测试或演示，不消耗 API配额
        llm = MockLLMClient()

    return ReviewNodes(llm=llm, search=search, parser=parser, prompts=prompts)


@lru_cache(maxsize=1)
def get_venue_repository() -> VenueRepository:
    """
    获取 VenueRepository 单例实例

    用于加载和管理期刊配置文件 (venue profiles)。
    期刊配置存储在 venues/ 目录下。

    Returns:
        VenueRepository: 期刊配置仓库实例
    """
    settings = load_settings()
    return VenueRepository(settings.venues_dir, legacy_reference_dir=settings.legacy_reference_dir)
