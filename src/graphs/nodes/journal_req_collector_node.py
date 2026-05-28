from __future__ import annotations

from src.graphs.runtime import get_review_nodes, get_venue_repository
from src.graphs.state import GlobalState


def journal_req_collector_node(state: GlobalState) -> GlobalState:
    venue = get_venue_repository().load(state.get("venue_code", ""))
    result = get_review_nodes().journal_requirements(_request_like(state), state["parsed_paper"])
    return {
        "venue_profile": venue,
        "journal_requirements": result["journal_requirements"],
        "journal_requirements_result": result,
        "stage_outputs": {
            "venue_profile": venue,
            "journal_requirements": result,
        },
    }


def _request_like(state: GlobalState):
    from src.core.models import ReviewMode, ReviewRequest, VenueCollection, VenueDomain

    return ReviewRequest(
        paper_path=state["paper_path"],
        review_mode=ReviewMode(state.get("review_mode", "FULL_REVIEW")),
        venue_domain=VenueDomain(state["venue_domain"]) if state.get("venue_domain") else None,
        venue_collection=VenueCollection(state["venue_collection"]) if state.get("venue_collection") else None,
        venue_code=state.get("venue_code", ""),
        journal_name=state.get("journal_name", ""),
        journal_requirements_path=state.get("journal_requirements_path", ""),
    )
