from __future__ import annotations

from src.graphs.graph import main_graph


def run_review(payload: dict):
    return main_graph.invoke(payload)
