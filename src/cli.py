from __future__ import annotations

import argparse
import json
from pathlib import Path

from src.infra.parser import build_document_parser
from src.core.venue_catalog import VenueCatalogRepository
from src.core.venues import VenueRepository
from src.services.review_service import build_workflow
from src.services.review_service import ReviewSubmissionError
from src.core.models import OutputLanguage, ReviewMode, ReviewRequest, VenueCollection, VenueDomain
from src.core.models import to_jsonable
from src.infra.settings import load_settings


# 这个是我们最原始的cli借口

def main() -> None:
    parser = argparse.ArgumentParser(prog="paper-review")
    subcommands = parser.add_subparsers(dest="command", required=True)

    subcommands.add_parser("doctor", help="Check local configuration")

    parse_cmd = subcommands.add_parser("parse", help="Parse a manuscript")
    parse_cmd.add_argument("path")

    review_cmd = subcommands.add_parser("review", help="Run a review workflow")
    review_cmd.add_argument("path")
    review_cmd.add_argument("--mode", choices=[m.value for m in ReviewMode], default=ReviewMode.FULL_REVIEW.value)
    review_cmd.add_argument("--output-language", choices=[l.value for l in OutputLanguage], default=OutputLanguage.ZH.value)
    review_cmd.add_argument("--venue-domain", choices=[d.value for d in VenueDomain])
    review_cmd.add_argument("--venue-collection", choices=[c.value for c in VenueCollection])
    review_cmd.add_argument("--venue-code", default="")

    venues_cmd = subcommands.add_parser("venues", help="List available venue codes")
    venues_cmd.add_argument("--limit", type=int, default=30)
    subcommands.add_parser("venue-catalog", help="List grouped venue catalog")

    args = parser.parse_args()
    if args.command == "doctor":
        _doctor()
    elif args.command == "parse":
        _parse(args.path)
    elif args.command == "review":
        _review(args)
    elif args.command == "venues":
        _venues(args.limit)
    elif args.command == "venue-catalog":
        _venue_catalog()


def _doctor() -> None:
    settings = load_settings()
    payload = {
        "project_root": str(settings.project_root),
        "data_dir": str(settings.data_dir),
        "legacy_reference_dir": str(settings.legacy_reference_dir),
        "legacy_reference_exists": settings.legacy_reference_dir.exists(),
        "prompts_dir": str(settings.prompts_dir),
        "prompts_dir_exists": settings.prompts_dir.exists(),
        "venues_dir": str(settings.venues_dir),
        "venues_dir_exists": settings.venues_dir.exists(),
        "llm_provider": settings.llm_provider,
        "parser_backend": settings.parser_backend,
        "mineru_configured": bool(settings.mineru_api_token),
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def _parse(path: str) -> None:
    settings = load_settings()
    parsed = build_document_parser(settings).parse(Path(path))
    print(json.dumps(to_jsonable(parsed), ensure_ascii=False, indent=2))


def _review(args: argparse.Namespace) -> None:
    workflow = build_workflow()
    try:
        run = workflow.run(
            ReviewRequest(
                paper_path=args.path,
                review_mode=ReviewMode(args.mode),
                output_language=OutputLanguage(args.output_language),
                venue_domain=VenueDomain(args.venue_domain) if args.venue_domain else None,
                venue_collection=VenueCollection(args.venue_collection) if args.venue_collection else None,
                venue_code=args.venue_code,
            )
        )
    except ReviewSubmissionError as exc:
        raise SystemExit(f"review submission error: {exc}") from exc
    print(json.dumps(to_jsonable(run), ensure_ascii=False, indent=2))


def _venues(limit: int) -> None:
    settings = load_settings()
    venues = VenueRepository(settings.venues_dir, legacy_reference_dir=settings.legacy_reference_dir).list_codes()
    print(json.dumps({"count": len(venues), "codes": venues[:limit]}, ensure_ascii=False, indent=2))


def _venue_catalog() -> None:
    settings = load_settings()
    catalog = VenueCatalogRepository(settings.venues_dir)
    items = catalog.list_items()
    print(json.dumps({"count": len(items), "catalog": catalog.grouped()}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
