from __future__ import annotations

from pathlib import Path

from src.core.models import VenueCatalogItem, VenueCollection, VenueDomain


class VenueCatalogRepository:
    """Builds the product-facing venue selection catalog from active assets."""

    def __init__(self, venues_dir: Path) -> None:
        self.venues_dir = venues_dir

    def list_items(self) -> list[VenueCatalogItem]:
        items: dict[tuple[str, VenueDomain, VenueCollection], VenueCatalogItem] = {}
        for item in self._iter_cs_items():
            items[(item.code, item.domain, item.venue_collection)] = item
        for item in self._iter_is_items():
            items[(item.code, item.domain, item.venue_collection)] = item
        return sorted(items.values(), key=lambda item: (item.domain.value, item.venue_collection.value, item.code))

    def grouped(self) -> dict[str, dict[str, list[dict[str, str]]]]:
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
        return any(
            item.domain == domain
            and item.venue_collection == venue_collection
            and item.code == code
            for item in self.list_items()
        )

    def _iter_cs_items(self) -> list[VenueCatalogItem]:
        return self._items_from_directory(
            directory=self.venues_dir / "ccfa",
            domain=VenueDomain.CS,
            venue_collection=VenueCollection.CCFA,
            suffix="_CCFA",
        )

    def _iter_is_items(self) -> list[VenueCatalogItem]:
        items: list[VenueCatalogItem] = []
        directory = self.venues_dir / "utd_ft50"
        if not directory.exists():
            return items

        for path in sorted(directory.glob("*.md")):
            code = path.stem
            collections: list[VenueCollection]
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
