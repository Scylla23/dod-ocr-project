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
    out, _ = merge_page_results([page1, page2], SCHEMA)
    assert out["title"] == "Doc A"
    assert out["document_number"] == "EM-1"


def test_lists_concat_dedupe_preserve_order():
    page1 = {"title": None, "document_number": None, "references": ["X", "Y"]}
    page2 = {"title": None, "document_number": None, "references": ["Y", "Z", "X"]}
    out, _ = merge_page_results([page1, page2], SCHEMA)
    assert out["references"] == ["X", "Y", "Z"]


def test_missing_keys_treated_as_null():
    page1 = {}
    out, _ = merge_page_results([page1], SCHEMA)
    assert out["title"] == ""
    assert out["document_number"] == ""
    assert out["references"] == []


def test_failed_pages_skipped():
    page1 = None  # represents a failed extraction
    page2 = {"title": "Doc B", "document_number": None, "references": ["A"]}
    out, _ = merge_page_results([page1, page2], SCHEMA)
    assert out["title"] == "Doc B"
    assert out["references"] == ["A"]


def test_scalar_confidence_from_picked_page():
    page1 = {"title": None, "document_number": None, "references": None}
    page2 = {"title": "Doc B", "document_number": "EM-1", "references": None}
    confs = [
        {"title": 0.5, "document_number": 0.4, "references": None},
        {"title": 0.9, "document_number": 0.8, "references": None},
    ]
    out, c = merge_page_results([page1, page2], SCHEMA, confs)
    assert out["title"] == "Doc B"
    # Picked page is page 2, so its confidence wins.
    assert c["title"] == 0.9
    assert c["document_number"] == 0.8


def test_list_confidence_takes_max_across_contributing_pages():
    page1 = {"title": None, "document_number": None, "references": ["X"]}
    page2 = {"title": None, "document_number": None, "references": ["Y"]}
    confs = [
        {"references": 0.6},
        {"references": 0.9},
    ]
    out, c = merge_page_results([page1, page2], SCHEMA, confs)
    assert out["references"] == ["X", "Y"]
    assert c["references"] == 0.9


def test_no_confidences_arg_returns_empty_dict():
    page1 = {"title": "Doc A", "document_number": None, "references": ["X"]}
    out, c = merge_page_results([page1], SCHEMA)
    assert out["title"] == "Doc A"
    assert c == {}
