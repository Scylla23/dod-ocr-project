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


EVIDENCE_KEY = "_evidence"

EVIDENCE_PROMPT = (
    " Also fill the '_evidence' object: for each field above, supply a short "
    "verbatim quote (≤120 chars) copied EXACTLY from the page's printed text "
    "that supports the value, or null if the value was not present or had to "
    "be inferred. Do not paraphrase. Do not include surrounding punctuation "
    "that does not appear on the page. For list fields, quote one representative item."
)

CONFIDENCE_KEY = "_confidence"

CONFIDENCE_PROMPT = (
    " Also fill the '_confidence' object: for each field above, supply a number "
    "in [0, 1] representing your self-rated confidence that the extracted value "
    "is correct (1.0 = certain, 0 = pure guess or inferred). Use null when the "
    "field is not applicable or was not extracted from this page."
)


def build_tool_input_schema(
    schema: list[FieldDef],
    *,
    include_evidence: bool = False,
    include_confidence: bool = False,
) -> dict:
    """Build a JSON schema for Anthropic tool-use that mirrors the field schema.

    All fields are required and nullable so the model must produce a complete object.
    When include_evidence=True, an additional '_evidence' object is required, with
    one nullable string per field for verbatim source quotes.
    When include_confidence=True, an additional '_confidence' object is required,
    with one nullable number per field for self-rated confidence.
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
    required = [f.name for f in schema]
    if include_evidence:
        properties[EVIDENCE_KEY] = _build_evidence_subschema(schema, strict=False)
        required.append(EVIDENCE_KEY)
    if include_confidence:
        properties[CONFIDENCE_KEY] = _build_confidence_subschema(schema, strict=False)
        required.append(CONFIDENCE_KEY)
    return {
        "type": "object",
        "properties": properties,
        "required": required,
    }


def _build_evidence_subschema(schema: list[FieldDef], *, strict: bool) -> dict:
    """Sub-schema for per-field verbatim quotes. strict=True for OpenAI structured outputs."""
    props: dict[str, dict] = {f.name: {"type": ["string", "null"]} for f in schema}
    sub: dict = {
        "type": "object",
        "properties": props,
        "required": [f.name for f in schema],
    }
    if strict:
        sub["additionalProperties"] = False
    return sub


def build_evidence_subschema(schema: list[FieldDef], *, strict: bool = False) -> dict:
    return _build_evidence_subschema(schema, strict=strict)


def _build_confidence_subschema(schema: list[FieldDef], *, strict: bool) -> dict:
    """Sub-schema for per-field self-rated confidence. strict=True for OpenAI structured outputs."""
    props: dict[str, dict] = {f.name: {"type": ["number", "null"]} for f in schema}
    sub: dict = {
        "type": "object",
        "properties": props,
        "required": [f.name for f in schema],
    }
    if strict:
        sub["additionalProperties"] = False
    return sub


def build_confidence_subschema(schema: list[FieldDef], *, strict: bool = False) -> dict:
    return _build_confidence_subschema(schema, strict=strict)
