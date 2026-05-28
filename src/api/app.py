from __future__ import annotations

from pathlib import Path

from src.core.venue_catalog import VenueCatalogRepository
from src.core.venues import VenueRepository
from src.services.review_service import build_workflow
from src.services.review_service import ReviewSubmissionError
from src.core.models import ReviewMode, ReviewRequest, VenueCollection, VenueDomain
from src.core.models import to_jsonable
from src.infra.settings import load_settings


def create_app():
    try:
        from fastapi import FastAPI, HTTPException
        from pydantic import BaseModel
    except ImportError as exc:
        raise RuntimeError("fastapi and pydantic are required for the API app") from exc

    class ReviewCreate(BaseModel):
        paper_path: str
        review_mode: ReviewMode = ReviewMode.FULL_REVIEW
        venue_domain: VenueDomain
        venue_collection: VenueCollection
        venue_code: str

    app = FastAPI(title="Paper Review Agent")

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/api/venues")
    def venues() -> dict[str, object]:
        settings = load_settings()
        codes = VenueRepository(settings.venues_dir, legacy_reference_dir=settings.legacy_reference_dir).list_codes()
        return {"count": len(codes), "codes": codes}

    @app.get("/api/venue-catalog")
    def venue_catalog() -> dict[str, object]:
        settings = load_settings()
        catalog = VenueCatalogRepository(settings.venues_dir)
        items = catalog.list_items()
        return {"count": len(items), "catalog": catalog.grouped()}

    @app.post("/api/reviews")
    def create_review(payload: ReviewCreate) -> dict[str, object]:
        path = Path(payload.paper_path)
        if not path.exists():
            raise HTTPException(status_code=400, detail=f"paper_path does not exist: {path}")
        workflow = build_workflow()
        try:
            run = workflow.run(
                ReviewRequest(
                    paper_path=payload.paper_path,
                    review_mode=payload.review_mode,
                    venue_domain=payload.venue_domain,
                    venue_collection=payload.venue_collection,
                    venue_code=payload.venue_code,
                )
            )
        except ReviewSubmissionError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return to_jsonable(run)

    return app


app = create_app()
