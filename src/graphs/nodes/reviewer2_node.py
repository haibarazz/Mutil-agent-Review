from __future__ import annotations

from src.graphs.nodes._reviewer_common import run_reviewer
from src.graphs.state import GlobalState


def reviewer2_node(state: GlobalState) -> GlobalState:
    return run_reviewer(
        state,
        prompt_name="reviewer2",
        reviewer_key="reviewer2",
        legacy_reviewer_key="reviewer_2",
        role="Field and contribution reviewer",
    )
