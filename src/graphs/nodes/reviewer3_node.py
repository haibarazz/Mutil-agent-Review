from __future__ import annotations

from src.graphs.nodes._reviewer_common import run_reviewer
from src.graphs.state import GlobalState


def reviewer3_node(state: GlobalState) -> GlobalState:
    return run_reviewer(
        state,
        prompt_name="reviewer3",
        reviewer_key="reviewer3",
        legacy_reviewer_key="reviewer_3",
        role="Cross-disciplinary reviewer",
    )
