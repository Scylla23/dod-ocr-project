from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

FieldType = Literal["string", "list[string]"]

_NAME_RE = re.compile(r"^[A-Za-z0-9_\- ]+$")


@dataclass(frozen=True)
class FieldDef:
    name: str
    type: FieldType
    removable: bool


DEFAULT_SCHEMA: tuple[FieldDef, ...] = (
    # Generic core (not removable)
    FieldDef("title", "string", False),
    FieldDef("document_type", "string", False),
    FieldDef("document_number", "string", False),
    FieldDef("effective_date", "string", False),
    FieldDef("summary", "string", False),
    # USACE extras (removable)
    FieldDef("proponent_office", "string", True),
    FieldDef("issuing_authority", "string", True),
    FieldDef("applicability", "string", True),
    FieldDef("superseded_documents", "string", True),
    # List
    FieldDef("references", "list[string]", True),
)


def validate_field_name(name: str) -> None:
    stripped = name.strip()
    if not stripped:
        raise ValueError("field name cannot be empty")
    if len(stripped) > 40:
        raise ValueError("field name must be 40 characters or fewer")
    if not _NAME_RE.match(stripped):
        raise ValueError("field name may contain only letters, digits, spaces, _ and -")


def add_custom_field(schema: list[FieldDef], name: str) -> list[FieldDef]:
    validate_field_name(name)
    name_clean = name.strip()
    existing = {f.name.lower() for f in schema}
    if name_clean.lower() in existing:
        raise ValueError(f"field '{name_clean}' already exists")
    return [*schema, FieldDef(name_clean, "string", True)]


def remove_field(schema: list[FieldDef], name: str) -> list[FieldDef]:
    target = next((f for f in schema if f.name.lower() == name.lower()), None)
    if target is None:
        raise ValueError(f"field '{name}' not found")
    if not target.removable:
        raise ValueError(f"field '{target.name}' is not removable")
    return [f for f in schema if f.name.lower() != name.lower()]


def build_tool_input_schema(schema: list[FieldDef]) -> dict:
    """Build a JSON schema for Anthropic tool-use that mirrors the field schema.

    All fields are required and nullable so the model must produce a complete object.
    """
    properties: dict[str, dict] = {}
    for f in schema:
        if f.type == "string":
            properties[f.name] = {"type": ["string", "null"]}
        else:  # list[string]
            properties[f.name] = {
                "type": ["array", "null"],
                "items": {"type": "string"},
            }
    return {
        "type": "object",
        "properties": properties,
        "required": [f.name for f in schema],
    }
