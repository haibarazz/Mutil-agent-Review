"""
期刊仓库模块 - 负责加载和管理期刊配置信息

核心概念:
- 期刊配置以 Markdown 文件形式存储在 venues/ 目录下
- 每个期刊文件固定拆成 Journal Requirements 和 Venue Profile 两段
- Journal Requirements 面向官方投稿要求，Venue Profile 面向智能体审稿判断
- 不同集合的期刊有不同的命名后缀 (_CCFA, _UTD_FT50, _UTD, _FT50)

Venues 目录结构:
    venues/
    ├── ccfa/           # CCFA 系列期刊
    │   └── AAAI_CCFA.md
    │   └── IJCAI_CCFA.md
    ├── utd_ft50/       # UTD / FT50 系列期刊
    │   └── AAAI_UTD_FT50.md
    │   └── AAAI_UTD.md
    │   └── AAAI_FT50.md
"""
from __future__ import annotations

from pathlib import Path

from src.core.models import VenueProfile


class VenueRepository:
    """
    期刊配置仓库

    职责: 根据期刊代码加载对应的期刊 profile 配置

    使用方式:
        repo = VenueRepository(Path("venues/"))
        profile = repo.load("AAAI")
        # → 返回 AAAI_XX.md 文件中解析的配置
    """

    def __init__(self, venues_dir: Path, legacy_reference_dir: Path | None = None) -> None:
        """初始化期刊仓库。

        Args:
            venues_dir: 期刊配置文件的根目录 (包含 ccfa/, utd_ft50/ 子目录)
            legacy_reference_dir: 兼容旧调用签名；活跃加载不再读取 reference 目录
        """
        self.venues_dir = venues_dir
        self.legacy_reference_dir = legacy_reference_dir

    def list_codes(self) -> list[str]:
        """
        列出所有可用的期刊代码

        Returns:
            list[str]: 所有期刊代码的列表 (已去重、排序)
        """
        codes: set[str] = set()
        # 遍历所有 profile 目录中的 .md 文件
        for directory in self._profile_dirs():
            for path in directory.glob("*.md"):
                codes.add(self._code_from_path(path))
        return sorted(codes)

    def load(self, code: str) -> VenueProfile | None:
        """
        加载指定期刊代码的配置

        Args:
            code: 期刊代码，如 "AAAI"、"IJCAI"、"NeurIPS" 等

        Returns:
            VenueProfile | None: 期刊配置对象，若未找到则返回 None
        """
        if not code:
            return None
        # 按优先级尝试多个可能的文件路径
        for path in self._candidate_paths(code):
            if not path.exists():
                continue
            text = path.read_text(encoding="utf-8")
            journal_requirements_text, profile_text = self._extract_sections(text)
            return VenueProfile(
                code=code,
                name=code,
                source_path=str(path),
                journal_requirements_text=journal_requirements_text,
                profile_text=profile_text,
            )
        return None

    def _profile_dirs(self) -> list[Path]:
        """
        获取所有有效的 profile 目录

        当前只读取活跃的 venues/ 目录，reference/ 里的旧实现只作为人工参考。
        """
        dirs = [self.venues_dir / "ccfa", self.venues_dir / "utd_ft50"]
        return [path for path in dirs if path.exists()]

    def _candidate_paths(self, code: str) -> list[Path]:
        """
        生成查找期刊配置文件的所有可能路径

        按优先级排序，依次尝试:
        1. {code}_CCFA.md         (CCFA 集合)
        2. {code}_UTD_FT50.md     (UTD+FT50 集合)
        3. {code}_UTD.md         (UTD 集合)
        4. {code}_FT50.md        (FT50 集合)

        Args:
            code: 期刊代码

        Returns:
            list[Path]: 可能路径的有序列表
        """
        candidates = [
            self.venues_dir / "ccfa" / f"{code}_CCFA.md",
            self.venues_dir / "utd_ft50" / f"{code}_UTD_FT50.md",
            self.venues_dir / "utd_ft50" / f"{code}_UTD.md",
            self.venues_dir / "utd_ft50" / f"{code}_FT50.md",
        ]
        return candidates

    def _code_from_path(self, path: Path) -> str:
        """
        从文件路径提取期刊代码

        示例:
            "AAAI_CCFA.md" → "AAAI"
            "NeurIPS_UTD.md" → "NeurIPS"
            "ICML_FT50.md" → "ICML"
        """
        code = path.stem
        # 移除各种后缀以获取原始代码
        for suffix in ("_UTD_FT50", "_CCFA", "_UTD", "_FT50"):
            code = code.removesuffix(suffix)
        return code

    def _extract_sections(self, text: str) -> tuple[str, str]:
        """从标准化 venue 文件中读取官方要求和智能体画像。

        venue 文件现在是 journal requirements 的唯一来源；如果旧文件还没迁移，
        这里保留一个中文标题 fallback，方便迁移期间不让流程直接断掉。
        """
        requirements = self._section_after_marker(
            text=text,
            marker="## Journal Requirements",
            stop_marker="## Venue Profile",
        )
        profile = self._section_after_marker(text=text, marker="## Venue Profile")

        if not requirements:
            requirements = self._section_before_marker(text, "## 智能体提示词片段")
        if not profile:
            profile = self._section_after_marker(text=text, marker="## 智能体提示词片段")

        return self._clean_section(requirements, limit=8000), self._clean_section(profile, limit=8000)

    def _section_after_marker(self, *, text: str, marker: str, stop_marker: str | None = None) -> str:
        index = text.find(marker)
        if index == -1:
            return ""
        start = index + len(marker)
        if stop_marker:
            stop = text.find(stop_marker, start)
            return text[start:stop] if stop != -1 else text[start:]
        return text[start:]

    def _section_before_marker(self, text: str, marker: str) -> str:
        index = text.find(marker)
        return text[:index] if index != -1 else text

    def _clean_section(self, text: str, *, limit: int) -> str:
        return text.replace("```text", "").replace("```", "").strip()[:limit]
