from app.merge import merge_page_results
from app.schema import FieldDef


SCHEMA = [
    FieldDef("title", "string", False),
    FieldDef("document_number", "string", False),
    FieldDef("references", "list[string]", True),
]


def test_scalars_first_non_null_wins_with_page_priority():
    page1 = {"title": "Doc A", "document_number": None, "references": None}
    page2 = {"title": "Doc B", "document_number": "EM-1", "references": None}
    out = merge_page_results([page1, page2], SCHEMA)
    assert out["title"] == "Doc A"
    assert out["document_number"] == "EM-1"


def test_lists_concat_dedupe_preserve_order():
    page1 = {"title": None, "document_number": None, "references": ["X", "Y"]}
    page2 = {"title": None, "document_number": None, "references": ["Y", "Z", "X"]}
    out = merge_page_results([page1, page2], SCHEMA)
    assert out["references"] == ["X", "Y", "Z"]


def test_missing_keys_treated_as_null():
    page1 = {}
    out = merge_page_results([page1], SCHEMA)
    assert out["title"] == ""
    assert out["document_number"] == ""
    assert out["references"] == []


def test_failed_pages_skipped():
    page1 = None  # represents a failed extraction
    page2 = {"title": "Doc B", "document_number": None, "references": ["A"]}
    out = merge_page_results([page1, page2], SCHEMA)
    assert out["title"] == "Doc B"
    assert out["references"] == ["A"]
