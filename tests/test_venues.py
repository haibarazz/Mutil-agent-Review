import unittest

from src.core.models import VenueCollection, VenueDomain
from src.core.venue_catalog import VenueCatalogRepository
from src.core.venues import VenueRepository
from src.infra.settings import load_settings


class VenueTests(unittest.TestCase):
    def test_loads_legacy_venue_profile(self) -> None:
        settings = load_settings()
        repo = VenueRepository(settings.venues_dir, legacy_reference_dir=settings.legacy_reference_dir)
        profile = repo.load("AAAI")

        self.assertIsNotNone(profile)
        assert profile is not None
        self.assertEqual(profile.code, "AAAI")
        self.assertTrue(profile.profile_text)

    def test_catalog_groups_homepage_venue_choices(self) -> None:
        settings = load_settings()
        catalog = VenueCatalogRepository(settings.venues_dir)
        grouped = catalog.grouped()

        self.assertIn("AAAI", [item["code"] for item in grouped["CS"]["CCFA"]])
        self.assertIn("MISQ", [item["code"] for item in grouped["IS"]["FT50"]])
        self.assertIn("MISQ", [item["code"] for item in grouped["IS"]["UTD24"]])
        self.assertTrue(
            catalog.contains(
                domain=VenueDomain.CS,
                venue_collection=VenueCollection.CCFA,
                code="AAAI",
            )
        )


if __name__ == "__main__":
    unittest.main()
