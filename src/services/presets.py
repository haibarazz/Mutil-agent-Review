from __future__ import annotations

import json
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from src.core.models import OutputLanguage, ReviewMode, VenueCollection, VenueDomain
from src.core.models import to_jsonable
from src.infra.settings import Settings, load_settings


@dataclass(frozen=True)
class ReviewPreset:
    preset_id: str
    name: str
    review_mode: ReviewMode
    output_language: OutputLanguage
    venue_domain: VenueDomain
    venue_collection: VenueCollection
    venue_code: str
    created_at: str
    updated_at: str


@dataclass(frozen=True)
class ReviewPresetInput:
    name: str
    review_mode: ReviewMode
    output_language: OutputLanguage
    venue_domain: VenueDomain
    venue_collection: VenueCollection
    venue_code: str


class LocalPresetStore:
    def __init__(self, path: Path) -> None:
        self.path = path
        self._lock = threading.RLock()

    def create(self, preset_input: ReviewPresetInput) -> ReviewPreset:
        with self._lock:
            presets = self._read_all()
            now = _utc_now()
            preset = ReviewPreset(
                preset_id=uuid4().hex,
                name=preset_input.name.strip() or _default_preset_name(preset_input),
                review_mode=preset_input.review_mode,
                output_language=preset_input.output_language,
                venue_domain=preset_input.venue_domain,
                venue_collection=preset_input.venue_collection,
                venue_code=preset_input.venue_code,
                created_at=now,
                updated_at=now,
            )
            presets.append(preset)
            self._write_all(presets)
            return preset

    def list(self, limit: int = 50) -> list[ReviewPreset]:
        with self._lock:
            presets = self._read_all()
            presets.sort(key=lambda item: item.updated_at, reverse=True)
            return presets[:limit]

    def _read_all(self) -> list[ReviewPreset]:
        if not self.path.exists():
            return []
        data = json.loads(self.path.read_text(encoding="utf-8"))
        if not isinstance(data, list):
            return []
        return [_preset_from_dict(item) for item in data if isinstance(item, dict)]

    def _write_all(self, presets: list[ReviewPreset]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        # preset 是前端配置资产，独立存成一个小 JSON，后面接数据库时也容易迁移。
        self.path.write_text(json.dumps(to_jsonable(presets), ensure_ascii=False, indent=2), encoding="utf-8")


def build_preset_store(settings: Settings | None = None) -> LocalPresetStore:
    settings = settings or load_settings()
    return LocalPresetStore(settings.data_dir / "presets.json")


def _preset_from_dict(data: dict[str, Any]) -> ReviewPreset:
    return ReviewPreset(
        preset_id=str(data["preset_id"]),
        name=str(data.get("name", "")),
        review_mode=ReviewMode(str(data["review_mode"])),
        output_language=OutputLanguage(str(data.get("output_language", OutputLanguage.ZH.value))),
        venue_domain=VenueDomain(str(data["venue_domain"])),
        venue_collection=VenueCollection(str(data["venue_collection"])),
        venue_code=str(data.get("venue_code", "")),
        created_at=str(data["created_at"]),
        updated_at=str(data["updated_at"]),
    )


def _default_preset_name(preset_input: ReviewPresetInput) -> str:
    return f"{preset_input.review_mode.value} · {preset_input.venue_domain.value} · {preset_input.venue_code}"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()
