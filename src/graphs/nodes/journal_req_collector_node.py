from __future__ import annotations

from src.graphs.runtime import get_venue_repository
from src.graphs.state import GlobalState


def journal_req_collector_node(state: GlobalState) -> GlobalState:
    venue = get_venue_repository().load(state.get("venue_code", ""))
    # V1 不再允许用户上传/输入期刊要求；这里统一从选中的 venue md 文件读取。
    result = {
        "journal_requirements": venue.journal_requirements_text if venue else "",
        "source": "venue_file" if venue else "missing_venue_file",
        "venue_code": state.get("venue_code", ""),
        "source_path": venue.source_path if venue else "",
    }
    return {
        "venue_profile": venue,
        "journal_requirements": result["journal_requirements"],
        "journal_requirements_result": result,
        "stage_outputs": {
            "venue_profile": venue,
            "journal_requirements": result,
        },
    }
