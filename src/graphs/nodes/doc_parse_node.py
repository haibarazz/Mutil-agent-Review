from __future__ import annotations

from pathlib import Path

from src.infra.parser import DocumentParseError
from src.graphs.runtime import get_review_nodes
from src.graphs.state import GlobalState

# 我们在这里定义了一个文档解析节点函数 `doc_parse_node`，它接受一个全局状态对象 `state`，尝试解析指定路径的文档，并返回解析结果或错误信息。
def doc_parse_node(state: GlobalState) -> GlobalState:
    try:
        # get_review_nodes 这是最合的一个单例实例。
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
