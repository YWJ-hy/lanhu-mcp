"""Contract tests for scoped Lanhu PRD evidence output."""

import json
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from lanhu_mcp_server import (  # noqa: E402
    EVIDENCE_ONLY_FORBIDDEN_TERMS,
    _build_evidence_only_analysis_result,
    _build_scoped_evidence_result,
    _compute_scope_hash,
    _find_descendant_pages,
    _find_target_page,
    _normalize_design_info,
    _resolve_pageid_children_scope,
    _safe_page_summary,
)


def assert_no_forbidden_terms(value):
    serialized = json.dumps(value, ensure_ascii=False)
    for term in EVIDENCE_ONLY_FORBIDDEN_TERMS:
        assert term not in serialized


def test_safe_page_summary_keeps_only_scope_metadata():
    page = {
        "id": "page-id-1",
        "pageName": "订单详情",
        "path": "订单/订单详情",
        "level": 2,
        "parentId": "parent-1",
        "filename": "page_1.html",
        "hasChildren": True,
    }

    summary = _safe_page_summary(page)

    assert summary == {
        "pageId": "page-id-1",
        "pageName": "订单详情",
        "name": "订单详情",
        "path": "订单/订单详情",
        "level": 2,
        "parentId": "parent-1",
        "filename": "page_1.html",
        "hasChildren": True,
    }
    assert_no_forbidden_terms(summary)


def test_find_target_page_and_descendants_by_tree_shape():
    pages = [
        {"id": "root", "name": "根", "pageName": "根", "path": "根", "level": 0, "parentId": None, "filename": "root.html", "index": 1},
        {"id": "target", "name": "目标", "pageName": "目标", "path": "根/目标", "level": 1, "parentId": "root", "filename": "target.html", "index": 2},
        {"id": "child", "name": "子页", "pageName": "子页", "path": "根/目标/子页", "level": 2, "parentId": "target", "filename": "child.html", "index": 3},
        {"id": "sibling", "name": "相邻页", "pageName": "相邻页", "path": "根/相邻页", "level": 1, "parentId": "root", "filename": "sibling.html", "index": 4},
    ]

    target = _find_target_page(pages, "target")
    assert target["name"] == "目标"

    descendants = _find_descendant_pages(pages, target)
    assert [page["id"] for page in descendants] == ["child"]
    assert_no_forbidden_terms(descendants)


def test_resolve_pageid_children_scope_only_returns_target_and_children():
    pages = [
        {"id": "root", "name": "根", "pageName": "根", "path": "根", "level": 0, "parentId": None, "filename": "root.html", "index": 1},
        {"id": "target", "name": "目标", "pageName": "目标", "path": "根/目标", "level": 1, "parentId": "root", "filename": "target.html", "index": 2},
        {"id": "child-a", "name": "子页A", "pageName": "子页A", "path": "根/目标/子页A", "level": 2, "parentId": "target", "filename": "child-a.html", "index": 3},
        {"id": "child-b", "name": "子页B", "pageName": "子页B", "path": "根/目标/子页B", "level": 2, "parentId": "target", "filename": "child-b.html", "index": 4},
        {"id": "sibling", "name": "相邻页", "pageName": "相邻页", "path": "根/相邻页", "level": 1, "parentId": "root", "filename": "sibling.html", "index": 5},
    ]

    scope = _resolve_pageid_children_scope(pages, "target", include_child_pages=False)
    assert scope["status"] == "ok"
    assert scope["selectedPageIds"] == ["target"]
    assert [page["id"] for page in scope["childPages"]] == ["child-a", "child-b"]

    scope_with_child = _resolve_pageid_children_scope(pages, "target", include_child_pages=True, confirmed_child_page_ids=["child-b", "sibling"])
    assert scope_with_child["selectedPageIds"] == ["target", "child-b"]
    assert scope_with_child["acceptedChildPageIds"] == ["child-b"]
    assert scope_with_child["rejectedChildPageIds"] == ["sibling"]
    assert_no_forbidden_terms(scope_with_child)


def test_compute_scope_hash_is_stable_for_same_scope():
    scope_hash_a = _compute_scope_hash("doc-1", "version-1", "target", ["child-b", "child-a"])
    scope_hash_b = _compute_scope_hash("doc-1", "version-1", "target", ["child-a", "child-b"])
    assert scope_hash_a == scope_hash_b


def test_build_scoped_evidence_result_marks_out_of_scope_as_partial_error():
    pages_info = {"docId": "doc-1", "projectId": "project-1", "teamId": "team-1", "versionId": "version-1"}
    evidence_result = _build_evidence_only_analysis_result(
        params={"doc_id": "doc-1", "project_id": "project-1", "team_id": "team-1"},
        pages_info=pages_info,
        download_result={"version_id": "version-1"},
        target_pages=["target", "child"],
        results=[
            {"page_name": "target", "success": True, "screenshot_path": "/tmp/target.png", "page_text": "目标页", "page_design_info": {}, "size": "1KB", "from_cache": False},
            {"page_name": "child", "success": True, "screenshot_path": "/tmp/child.png", "page_text": "子页", "page_design_info": {}, "size": "1KB", "from_cache": False},
        ],
        mode="full",
        filename_to_display={"target": "目标", "child": "子页"},
        filename_to_page={
            "target": {"id": "target", "name": "目标", "filename": "target.html", "path": "根/目标", "level": 1, "parentId": "root"},
            "child": {"id": "child", "name": "子页", "filename": "child.html", "path": "根/目标/子页", "level": 2, "parentId": "target"},
        },
        name_to_page={},
    )

    scope = {
        "targetPage": {"id": "target", "pageId": "target", "name": "目标", "path": "根/目标", "level": 1, "parentId": "root", "filename": "target.html"},
        "childPages": [],
        "selectedPages": [{"id": "target", "filename": "target.html"}],
        "selectedPageIds": ["target"],
        "acceptedChildPageIds": [],
        "rejectedChildPageIds": [],
    }
    scoped = _build_scoped_evidence_result(evidence_result, scope, include_child_pages=False, confirmed_child_page_ids=[])

    assert scoped["status"] == "partial_error"
    assert scoped["scopePolicy"] == "pageid_children_only"
    assert scoped["scopeValidation"]["returnedPageIds"] == ["target", "child"]
    assert scoped["scopeValidation"]["returnedOutOfScopePages"] == 1
    assert scoped["scopeValidation"]["parentExcluded"] is True
    assert scoped["scopeValidation"]["siblingsExcluded"] is True
    assert_no_forbidden_terms(scoped)


def test_resolve_pageid_children_scope_missing_target_errors_without_broadening():
    scope = _resolve_pageid_children_scope([], "missing", include_child_pages=True, confirmed_child_page_ids=["any"])
    assert scope["status"] == "error"
    assert scope["selectedPages"] == []
    assert scope["errors"]
    assert_no_forbidden_terms(scope)


def test_normalize_design_info_remains_serializable_for_scoped_evidence():
    result = _normalize_design_info({
        "textColors": [["rgb(1, 2, 3)", 2]],
        "bgColors": [["rgb(4, 5, 6)", 1]],
        "fontSpecs": [["14px|400|rgb(1, 2, 3)", 3]],
        "images": [{"src": "images/foo.png", "type": "img", "w": 100, "h": 50}],
    })

    assert result["fonts"][0]["fontSize"] == "14px"
    assert result["images"][0]["width"] == 100
    assert_no_forbidden_terms(result)
