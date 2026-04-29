import pytest

from app.schema import (
    DEFAULT_SCHEMA,
    FieldDef,
    add_custom_field,
    build_tool_input_schema,
    remove_field,
    validate_field_name,
)


def test_default_schema_shape():
    names = [f.name for f in DEFAULT_SCHEMA]
    assert "title" in names
    assert "document_number" in names
    assert "references" in names
    refs = next(f for f in DEFAULT_SCHEMA if f.name == "references")
    assert refs.type == "list[string]"
    title = next(f for f in DEFAULT_SCHEMA if f.name == "title")
    assert title.type == "string"
    assert title.removable is False


def test_build_tool_input_schema_marks_all_required_and_nullable():
    schema = [FieldDef(name="title", type="string", removable=False),
              FieldDef(name="refs", type="list[string]", removable=True)]
    js = build_tool_input_schema(schema)
    assert js["type"] == "object"
    assert js["required"] == ["title", "refs"]
    assert js["properties"]["title"]["type"] == ["string", "null"]
    assert js["properties"]["refs"]["type"] == ["array", "null"]
    assert js["properties"]["refs"]["items"] == {"type": "string"}


@pytest.mark.parametrize("name", ["", "   ", "a" * 41, "bad name!", "tab\there"])
def test_validate_field_name_rejects_invalid(name):
    with pytest.raises(ValueError):
        validate_field_name(name)


@pytest.mark.parametrize("name", ["keywords", "case_id", "Notes-2024", "x"])
def test_validate_field_name_accepts_valid(name):
    validate_field_name(name)  # does not raise


def test_add_custom_field_appends_string_removable():
    schema = list(DEFAULT_SCHEMA)
    new_schema = add_custom_field(schema, "keywords")
    assert new_schema[-1].name == "keywords"
    assert new_schema[-1].type == "string"
    assert new_schema[-1].removable is True


def test_add_custom_field_rejects_duplicate_case_insensitive():
    schema = list(DEFAULT_SCHEMA)
    with pytest.raises(ValueError, match="already exists"):
        add_custom_field(schema, "Title")


def test_remove_field_rejects_non_removable():
    schema = list(DEFAULT_SCHEMA)
    with pytest.raises(ValueError, match="not removable"):
        remove_field(schema, "title")


def test_remove_field_drops_removable():
    schema = list(DEFAULT_SCHEMA)
    new_schema = remove_field(schema, "references")
    assert "references" not in [f.name for f in new_schema]
