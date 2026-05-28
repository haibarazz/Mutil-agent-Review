from __future__ import annotations

from src.graphs.nodes._reviewer_common import run_reviewer
from src.graphs.state import GlobalState


def reviewer1_node(state: GlobalState) -> GlobalState:
    return run_reviewer(
        state,
        prompt_name="reviewer1",
        reviewer_key="reviewer1",
        legacy_reviewer_key="reviewer_1",
        role="Methodology reviewer",
    )
