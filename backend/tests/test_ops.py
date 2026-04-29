import pytest

from app.ops import OpError, apply_op
from app.schema import FieldDef

SCHEMA = [
    FieldDef("title", "string", False),
    FieldDef("references", "list[string]", True),
]


def base_state():
    return {
        "schema": SCHEMA,
        "values": {"title": "Original", "references": ["A", "B"]},
        "original_extracted": {"title": "OrigClaude", "references": ["A"]},
    }


def test_set_scalar():
    s = base_state()
    apply_op(s, {"op": "set", "field": "title", "value": "New"})
    assert s["values"]["title"] == "New"


def test_set_rejects_list_field():
    s = base_state()
    with pytest.raises(OpError):
        apply_op(s, {"op": "set", "field": "references", "value": "X"})


def test_append_to_list():
    s = base_state()
    apply_op(s, {"op": "append", "field": "references", "value": "C"})
    assert s["values"]["references"] == ["A", "B", "C"]


def test_append_dedupes():
    s = base_state()
    apply_op(s, {"op": "append", "field": "references", "value": "A"})
    assert s["values"]["references"] == ["A", "B"]


def test_append_rejects_scalar_field():
    s = base_state()
    with pytest.raises(OpError):
        apply_op(s, {"op": "append", "field": "title", "value": "X"})


def test_remove_by_index():
    s = base_state()
    apply_op(s, {"op": "remove", "field": "references", "index": 0})
    assert s["values"]["references"] == ["B"]


def test_remove_index_out_of_range():
    s = base_state()
    with pytest.raises(OpError):
        apply_op(s, {"op": "remove", "field": "references", "index": 99})


def test_revert_scalar_to_original():
    s = base_state()
    s["values"]["title"] = "edited"
    apply_op(s, {"op": "revert", "field": "title"})
    assert s["values"]["title"] == "OrigClaude"


def test_revert_list_to_original():
    s = base_state()
    apply_op(s, {"op": "revert", "field": "references"})
    assert s["values"]["references"] == ["A"]


def test_revert_unknown_original_uses_empty():
    s = base_state()
    s["original_extracted"].pop("title")
    apply_op(s, {"op": "revert", "field": "title"})
    assert s["values"]["title"] == ""


def test_unknown_field():
    s = base_state()
    with pytest.raises(OpError):
        apply_op(s, {"op": "set", "field": "nope", "value": "x"})


def test_unknown_op():
    s = base_state()
    with pytest.raises(OpError):
        apply_op(s, {"op": "delete", "field": "title"})
