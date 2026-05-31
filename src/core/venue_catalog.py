from __future__ import annotations

from pathlib import Path

from src.core.models import VenueCatalogItem, VenueCollection, VenueDomain


class VenueCatalogRepository:
    """Builds the product-facing venue selection catalog from active assets.

    从活跃资产构建产品面向的场所选择目录。
    """

    def __init__(self, venues_dir: Path) -> None:
        """初始化场所目录仓库。

        Args:
            venues_dir: 包含场所文件的目录路径
        """
        self.venues_dir = venues_dir

    def list_items(self) -> list[VenueCatalogItem]:
        """列出所有场所目录项目。

        Returns:
            按领域和集合排序的场所目录项目列表
        """
        items: dict[tuple[str, VenueDomain, VenueCollection], VenueCatalogItem] = {}
        for item in self._iter_cs_items():
            items[(item.code, item.domain, item.venue_collection)] = item
        for item in self._iter_is_items():
            items[(item.code, item.domain, item.venue_collection)] = item
        return sorted(items.values(), key=lambda item: (item.domain.value, item.venue_collection.value, item.code))

    def grouped(self) -> dict[str, dict[str, list[dict[str, str]]]]:
        """按领域和集合对场所项目进行分组。

        Returns:
            嵌套字典结构，按领域(CS/IS) -> 集合(CCFA/CCFB/等) -> 项目列表组织
        """
        grouped: dict[str, dict[str, list[dict[str, str]]]] = {
            "CS": {"CCFA": [], "CCFB": [], "CCFC": []},
            "IS": {"FT50": [], "UTD24": []},
        }
        for item in self.list_items():
            grouped[item.domain.value][item.venue_collection.value].append(
                {
                    "code": item.code,
                    "name": item.name,
                    "source_path": item.source_path,
                }
            )
        return grouped

    def contains(self, *, domain: VenueDomain, venue_collection: VenueCollection, code: str) -> bool:
        """检查是否包含指定的场所项目。

        Args:
            domain: 领域(CS或IS)
            venue_collection: 场所集合
            code: 场所代码

        Returns:
            如果存在该项目返回True，否则返回False
        """
        return any(
            item.domain == domain
            and item.venue_collection == venue_collection
            and item.code == code
            for item in self.list_items()
        )

    def _iter_cs_items(self) -> list[VenueCatalogItem]:
        """从 ccfa 目录迭代所有 CS 领域项目。

        Returns:
            CS领域的场所目录项目列表
        """
        return self._items_from_directory(
            directory=self.venues_dir / "ccfa",
            domain=VenueDomain.CS,
            venue_collection=VenueCollection.CCFA,
            suffix="_CCFA",
        )

    def _iter_is_items(self) -> list[VenueCatalogItem]:
        """从 utd_ft50 目录迭代所有 IS 领域项目。

        根据文件名后缀确定所属的集合：
        - 以 _UTD_FT50 结尾：同时属于 FT50 和 UTD24 集合
        - 以 _FT50 结尾：只属于 FT50 集合
        - 以 _UTD 结尾：只属于 UTD24 集合

        Returns:
            IS领域的场所目录项目列表
        """
        items: list[VenueCatalogItem] = []
        directory = self.venues_dir / "utd_ft50"
        if not directory.exists():
            return items

        for path in sorted(directory.glob("*.md")):
            code = path.stem
            collections: list[VenueCollection]
            # 确定该文件属于哪个集合
            if code.endswith("_UTD_FT50"):
                code = code.removesuffix("_UTD_FT50")
                collections = [VenueCollection.FT50, VenueCollection.UTD24]
            elif code.endswith("_FT50"):
                code = code.removesuffix("_FT50")
                collections = [VenueCollection.FT50]
            elif code.endswith("_UTD"):
                code = code.removesuffix("_UTD")
                collections = [VenueCollection.UTD24]
            else:
                continue
            # 为每个集合创建一个项目
            for collection in collections:
                items.append(
                    VenueCatalogItem(
                        code=code,
                        name=code,
                        domain=VenueDomain.IS,
                        venue_collection=collection,
                        source_path=str(path),
                    )
                )
        return items

    def _items_from_directory(
        self,
        *,
        directory: Path,
        domain: VenueDomain,
        venue_collection: VenueCollection,
        suffix: str,
    ) -> list[VenueCatalogItem]:
        """从指定目录提取场所项目。

        通过去除文件名后缀来获取场所代码。

        Args:
            directory: 要扫描的目录路径
            domain: 项目所属的领域
            venue_collection: 项目所属的集合
            suffix: 需要从文件名中去除的后缀

        Returns:
            提取的场所目录项目列表
        """
        if not directory.exists():
            return []
        items: list[VenueCatalogItem] = []
        for path in sorted(directory.glob("*.md")):
            code = path.stem.removesuffix(suffix)
            items.append(
                VenueCatalogItem(
                    code=code,
                    name=code,
                    domain=domain,
                    venue_collection=venue_collection,
                    source_path=str(path),
                )
            )
        return items
