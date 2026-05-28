from __future__ import annotations

from pathlib import Path

from src.infra.parser import DocumentParseError
from src.graphs.runtime import get_review_nodes
from src.graphs.state import GlobalState


def doc_parse_node(state: GlobalState) -> GlobalState:
    try:
        parsed = get_review_nodes().parser.parse(Path(state["paper_path"]))
    except (DocumentParseError, OSError, KeyError) as exc:
        return {
            "parse_error": str(exc),
            "stage_outputs": {"doc_parse": {"parse_error": str(exc)}},
        }
    return {
        "parsed_paper": parsed,
        "paper_content": parsed.full_text,
        "parse_error": "",
        "stage_outputs": {"doc_parse": {"title": parsed.title, "source_path": parsed.source_path}},
    }
