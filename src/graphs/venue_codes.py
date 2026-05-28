from __future__ import annotations

from src.core.venues import VenueRepository
from src.infra.settings import load_settings


def load_all_venue_codes() -> list[str]:
    settings = load_settings()
    repo = VenueRepository(settings.venues_dir, legacy_reference_dir=settings.legacy_reference_dir)
    return [""] + repo.list_codes()


ALL_VENUE_CODES = load_all_venue_codes()
