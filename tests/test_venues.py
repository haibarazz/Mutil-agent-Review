import unittest

from src.core.models import VenueCollection, VenueDomain
from src.core.venue_catalog import VenueCatalogRepository
from src.core.venues import VenueRepository
from src.infra.settings import load_settings


class VenueTests(unittest.TestCase):
    def test_loads_active_venue_profile_sections(self) -> None:
        settings = load_settings()
        repo = VenueRepository(settings.venues_dir, legacy_reference_dir=settings.legacy_reference_dir)
        profile = repo.load("AAAI")

        self.assertIsNotNone(profile)
        assert profile is not None
        self.assertEqual(profile.code, "AAAI")
        self.assertTrue(profile.journal_requirements_text)
        self.assertTrue(profile.profile_text)
        self.assertIn("AAAI", profile.journal_requirements_text)
        self.assertIn("AAAI", profile.profile_text)

    def test_all_venue_files_use_two_fixed_sections(self) -> None:
        settings = load_settings()
        for path in settings.venues_dir.rglob("*.md"):
            with self.subTest(path=str(path)):
                headings = [
                    line
                    for line in path.read_text(encoding="utf-8").splitlines()
                    if line.startswith("## ")
                ]
                self.assertEqual(headings, ["## Journal Requirements", "## Venue Profile"])

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
