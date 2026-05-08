"""Contract tests for adapter evidence-only output."""

import json
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from lanhu_mcp_server import (  # noqa: E402
    EVIDENCE_ONLY_FORBIDDEN_TERMS,
    _build_evidence_only_analysis_result,
    _normalize_design_info,
    _normalize_resolve_result,
)


def assert_no_forbidden_terms(value):
    serialized = json.dumps(value, ensure_ascii=False)
    for term in EVIDENCE_ONLY_FORBIDDEN_TERMS:
        assert term not in serialized


def test_normalize_design_info_keeps_structured_facts():
    result = _normalize_design_info({
        "textColors": [["rgb(1, 2, 3)", 2]],
        "bgColors": [["rgb(4, 5, 6)", 1]],
        "fontSpecs": [["14px|400|rgb(1, 2, 3)", 3]],
        "images": [{"src": "images/foo.png", "type": "img", "w": 100, "h": 50}],
    })

    assert result["colors"]["text"][0] == {"value": "rgb(1, 2, 3)", "count": 2}
    assert result["colors"]["background"][0] == {"value": "rgb(4, 5, 6)", "count": 1}
    assert result["fonts"][0] == {
        "fontSize": "14px",
        "fontWeight": "400",
        "color": "rgb(1, 2, 3)",
        "count": 3,
    }
    assert result["images"][0]["width"] == 100
    assert result["images"][0]["height"] == 50
    assert_no_forbidden_terms(result)


def test_normalize_resolve_result_has_adapter_fields_and_legacy_fields():
    result = _normalize_resolve_result(
        "https://lanhuapp.com/link/#/invite?sid=abc",
        "https://lanhuapp.com/web/#/item/project/product?tid=t&pid=p&docId=d",
        {"team_id": "t", "project_id": "p", "doc_id": "d", "version_id": "v"},
    )

    assert result["status"] == "ok"
    assert result["resolvedUrl"] == result["resolved_url"]
    assert result["teamId"] == "t"
    assert result["projectId"] == "p"
    assert result["docId"] == "d"
    assert result["versionId"] == "v"
    assert result["errors"] == []
    assert_no_forbidden_terms(result)


def test_build_evidence_only_analysis_result_contract():
    pages_info = {
        "docId": "doc-1",
        "projectId": "project-1",
        "teamId": "team-1",
        "versionId": "version-1",
    }
    results = [
        {
            "page_name": "page_1",
            "success": True,
            "screenshot_path": "/tmp/page_1.png",
            "page_text": "原始页面文本",
            "page_design_info": {"textColors": [["#111111", 1]]},
            "size": "10KB",
            "from_cache": True,
        },
        {
            "page_name": "page_2",
            "success": False,
            "error": "missing html",
        },
    ]
    filename_to_display = {"page_1": "订单详情", "page_2": "退款弹窗"}
    filename_to_page = {
        "page_1": {
            "id": "page-id-1",
            "name": "订单详情",
            "filename": "page_1.html",
            "path": "订单/订单详情",
            "level": 2,
            "parentId": "parent-1",
        }
    }

    result = _build_evidence_only_analysis_result(
        params={"doc_id": "doc-1", "project_id": "project-1", "team_id": "team-1"},
        pages_info=pages_info,
        download_result={"version_id": "version-2"},
        target_pages=["page_1", "page_2"],
        results=results,
        mode="full",
        filename_to_display=filename_to_display,
        filename_to_page=filename_to_page,
        name_to_page={},
    )

    assert result["status"] == "partial_error"
    assert result["outputMode"] == "evidence_only"
    assert result["analysisPromptIncluded"] is False
    assert result["docId"] == "doc-1"
    assert result["versionId"] == "version-2"
    assert result["summary"] == {
        "totalRequested": 2,
        "successful": 1,
        "failed": 1,
        "fromCache": True,
    }
    assert result["pages"][0]["pageId"] == "page-id-1"
    assert result["pages"][0]["pageName"] == "订单详情"
    assert result["pages"][0]["screenshotPath"] == "/tmp/page_1.png"
    assert result["pages"][0]["comments"] == []
    assert result["pages"][0]["annotations"] == []
    assert result["failedPages"] == [{"pageName": "退款弹窗", "error": "missing html"}]
    assert_no_forbidden_terms(result)


def test_evidence_only_invalid_mode_error_has_no_prompt_terms():
    result = {
        "status": "error",
        "outputMode": "bad",
        "analysisPromptIncluded": False,
        "pages": [],
        "failedPages": [],
        "errors": ["Invalid output_mode: bad"],
    }

    assert_no_forbidden_terms(result)
