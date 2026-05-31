"""
配置管理模块 - 统一管理应用程序的所有配置参数

职责:
1. 从 .env 文件加载环境变量
2. 解析并验证所有配置项
3. 提供类型安全的配置访问接口

配置来源优先级: .env 文件 > 环境变量 > 默认值
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


@dataclass(frozen=True)
class Settings:
    """
    应用程序配置数据类 (不可变对象)

    所有路径字段都会自动转换为绝对路径，确保跨环境一致性。

    属性分组:
    - 项目路径: project_root, data_dir, runs_dir
    - LLM 配置: llm_provider, llm_base_url, llm_api_key, llm_default_model, llm_timeout_sec, llm_config_path
    - 解析器配置: parser_backend, mineru_* (文档解析服务)
    - 搜索/获取配置: search_provider, fetch_provider
    - 业务路径: prompts_dir, venues_dir, legacy_reference_dir
    """
    # ========== 项目路径 ==========
    project_root: Path              # 项目根目录 (src/ 的上级目录)
    data_dir: Path                  # 数据目录 (默认 ./data)

    # ========== 应用环境 ==========
    app_env: str                    # 应用环境: dev / prod / test
    api_cors_origins: tuple[str, ...] # 允许访问 FastAPI 的前端来源
    supported_upload_extensions: tuple[str, ...] # 前端和后端共同支持的稿件扩展名
    max_upload_bytes: int           # 浏览器上传稿件大小上限

    # ========== LLM 配置 ==========
    llm_provider: str               # LLM 提供商: mock / openai_compatible
    llm_base_url: str               # OpenAI 兼容 API 的 base URL
    llm_api_key: str                # API Key (敏感信息)
    llm_default_model: str          # 默认模型名称
    llm_timeout_sec: float          # LLM 请求超时时间 (秒)
    llm_config_path: Path           # 多供应商路由配置文件

    # ========== 搜索/获取配置 ==========
    search_provider: str            # 搜索提供商 (当前为 none)
    fetch_provider: str             # 网页获取提供商 (当前为 none)

    # ========== 解析器配置 ==========
    parser_backend: str             # 解析器后端: auto / mineru 等
    mineru_api_token: str           # MinerU API Token (文档解析服务)
    mineru_base_url: str           # MinerU 服务地址
    mineru_model_version: str      # MinerU 模型版本
    mineru_timeout_sec: int        # MinerU 总超时时间 (秒)
    mineru_poll_interval_sec: float # MinerU 轮询间隔 (秒)
    mineru_request_timeout_sec: float # MinerU 单次请求超时 (秒)

    # ========== 业务路径 ==========
    legacy_reference_dir: Path      # 遗留参考实现目录
    prompts_dir: Path              # Markdown 提示词文件目录
    venues_dir: Path               # 期刊配置目录

    @property
    def runs_dir(self) -> Path:
        """审稿运行记录存放目录 (自动创建于 data/runs)"""
        return self.data_dir / "runs"

    @property
    def uploads_dir(self) -> Path:
        """浏览器上传稿件的本地暂存目录 (自动创建于 data/uploads)"""
        return self.data_dir / "uploads"

    @property
    def jobs_dir(self) -> Path:
        """前端异步审稿任务状态目录 (自动创建于 data/jobs)"""
        return self.data_dir / "jobs"


def load_settings() -> Settings:
    """
    加载并返回应用程序配置

    执行流程:
    1. 确定项目根目录 (从本文件位置向上两级)
    2. 加载 .env 文件到环境变量
    3. 从环境变量读取各配置项 (带默认值)
    4. 统一将相对路径转换为绝对路径
    5. 构建并返回 Settings 实例

    Returns:
        Settings: 包含所有配置项的不可变对象
    """
    # Step 1: 确定项目根目录
    project_root = Path(__file__).resolve().parents[2]

    # Step 2: 加载 .env 文件；不覆盖 shell 中已经显式设置的变量
    load_dotenv(project_root / ".env", override=False)

    # Step 3: 读取 data 目录配置
    data_dir = Path(os.getenv("DATA_DIR", "./data"))
    if not data_dir.is_absolute():
        data_dir = project_root / data_dir

    # Step 4: 读取遗留参考目录配置
    legacy_dir = Path(os.getenv("LEGACY_REFERENCE_DIR", "reference/legacy-coze-review"))
    if not legacy_dir.is_absolute():
        legacy_dir = project_root / legacy_dir

    # Step 5: 读取 prompts 目录配置
    prompts_dir = Path(os.getenv("PROMPTS_DIR", "prompts"))
    if not prompts_dir.is_absolute():
        prompts_dir = project_root / prompts_dir

    # Step 6: 读取 venues 目录配置
    venues_dir = Path(os.getenv("VENUES_DIR", "venues"))
    if not venues_dir.is_absolute():
        venues_dir = project_root / venues_dir

    # Step 7: 读取多供应商 LLM 路由配置
    llm_config_path = Path(os.getenv("LLM_CONFIG_PATH", "configs/llm.yaml"))
    if not llm_config_path.is_absolute():
        llm_config_path = project_root / llm_config_path

    # Step 8: 构建 Settings 实例
    return Settings(
        project_root=project_root,
        app_env=os.getenv("APP_ENV", "dev"),
        api_cors_origins=_env_csv(
            "APP_CORS_ORIGINS",
            "http://127.0.0.1:5173,http://localhost:5173",
        ),
        supported_upload_extensions=_normalize_extensions(
            _env_csv("APP_SUPPORTED_UPLOAD_EXTENSIONS", ".pdf,.md,.tex")
        ),
        max_upload_bytes=_env_int("APP_MAX_UPLOAD_BYTES", 80 * 1024 * 1024),
        data_dir=data_dir,
        llm_provider=os.getenv("LLM_PROVIDER", "mock"),           # 默认 mock 模式
        llm_base_url=os.getenv("LLM_BASE_URL", ""),
        llm_api_key=os.getenv("LLM_API_KEY", ""),
        llm_default_model=os.getenv("LLM_DEFAULT_MODEL", "gpt-4o-mini"),
        llm_timeout_sec=float(os.getenv("LLM_TIMEOUT_SEC", "60")),
        llm_config_path=llm_config_path,
        search_provider=os.getenv("SEARCH_PROVIDER", "none"),
        fetch_provider=os.getenv("FETCH_PROVIDER", "none"),
        parser_backend=os.getenv("PARSER_BACKEND", "auto"),
        mineru_api_token=os.getenv("MINERU_API_TOKEN", ""),
        mineru_base_url=os.getenv("MINERU_BASE_URL", "https://mineru.net"),
        mineru_model_version=os.getenv("MINERU_MODEL_VERSION", "vlm"),
        mineru_timeout_sec=_env_int("MINERU_TIMEOUT_SEC", 300),
        mineru_poll_interval_sec=_env_float("MINERU_POLL_INTERVAL_SEC", 3.0),
        mineru_request_timeout_sec=_env_float("MINERU_REQUEST_TIMEOUT_SEC", 30.0),
        legacy_reference_dir=legacy_dir,
        prompts_dir=prompts_dir,
        venues_dir=venues_dir,
    )


def _env_int(key: str, default: int) -> int:
    """
    从环境变量读取整数值

    Args:
        key: 环境变量名
        default: 默认值 (当变量不存在或解析失败时使用)

    Returns:
        int: 解析后的整数值
    """
    value = os.getenv(key)
    return int(value) if value else default


def _env_float(key: str, default: float) -> float:
    """
    从环境变量读取浮点数值

    Args:
        key: 环境变量名
        default: 默认值 (当变量不存在或解析失败时使用)

    Returns:
        float: 解析后的浮点数值
    """
    value = os.getenv(key)
    return float(value) if value else default


def _env_csv(key: str, default: str) -> tuple[str, ...]:
    """
    从环境变量读取逗号分隔列表

    用于 CORS origins 这类部署期配置；会自动去掉空项和多余空格。
    """
    value = os.getenv(key, default)
    return tuple(item.strip() for item in value.split(",") if item.strip())


def _normalize_extensions(values: tuple[str, ...]) -> tuple[str, ...]:
    """把 pdf / .PDF 这类配置统一收敛为小写 .pdf。"""
    normalized: list[str] = []
    for value in values:
        extension = value.lower()
        if not extension.startswith("."):
            extension = f".{extension}"
        normalized.append(extension)
    return tuple(dict.fromkeys(normalized))
