# PDF Data Extraction & Verification Tool — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a working prototype of a web tool that uploads a PDF, extracts structured data via Claude Vision, and lets the user correct values by selecting text in the PDF and assigning it to fields.

**Architecture:** Single FastAPI service with in-memory session state. PyMuPDF rasterizes pages server-side for Vision API; first 3 pages auto-extract in parallel via `asyncio.gather`. React + Vite frontend with `react-pdf` for native text selection; Zustand for client state. No database, no auth, no persistence.

**Tech Stack:** Python 3.11+ / FastAPI / PyMuPDF / `anthropic` SDK (model `claude-sonnet-4-5`) — React 18 / Vite / `react-pdf` / Zustand — pytest / Vitest.

**Spec:** `docs/superpowers/specs/2026-04-29-pdf-extraction-tool-design.md`

**Sample PDFs:** `DOD SAFE-8f7gk7Rejn97VEuB/` (5 USACE engineering documents, all with text layers)

**Repo layout produced:**
```
.
├── backend/
│   ├── pyproject.toml
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py           # FastAPI app + CORS + route wiring
│   │   ├── routes.py         # endpoint handlers
│   │   ├── schema.py         # FieldDef + DEFAULT_SCHEMA + tool-schema builder + name validation
│   │   ├── pdf_renderer.py   # PyMuPDF: rasterize page, text length
│   │   ├── extractor.py      # AsyncAnthropic + tool-use call
│   │   ├── merge.py          # merge_page_results
│   │   ├── ops.py            # apply_op for PATCH operations
│   │   └── session_store.py  # SessionState + in-memory dict
│   └── tests/
│       ├── conftest.py
│       ├── fixtures/EC_1105-2-2.pdf  # copied small sample
│       ├── test_schema.py
│       ├── test_pdf_renderer.py
│       ├── test_merge.py
│       ├── test_ops.py
│       ├── test_extractor.py
│       └── test_routes.py
└── frontend/
    ├── package.json
    ├── vite.config.ts
    ├── tsconfig.json
    ├── index.html
    └── src/
        ├── main.tsx
        ├── App.tsx
        ├── api.ts
        ├── store.ts
        ├── types.ts
        ├── styles.css
        └── components/
            ├── Upload.tsx
            ├── Workspace.tsx
            ├── PdfPane.tsx
            ├── SelectionPopover.tsx
            ├── FieldsPane.tsx
            └── AddFieldModal.tsx
```

---

## Task 1: Backend scaffold

**Files:**
- Create: `backend/pyproject.toml`
- Create: `backend/app/__init__.py` (empty)
- Create: `backend/app/main.py`
- Create: `backend/tests/__init__.py` (empty)
- Create: `backend/tests/conftest.py`
- Create: `backend/tests/test_health.py`

- [ ] **Step 1: Write `backend/pyproject.toml`**

```toml
[project]
name = "pdf-extract-backend"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
  "fastapi>=0.115",
  "uvicorn[standard]>=0.30",
  "python-multipart>=0.0.9",
  "pymupdf>=1.24",
  "anthropic>=0.39",
  "pydantic>=2.6",
]

[project.optional-dependencies]
dev = [
  "pytest>=8",
  "pytest-asyncio>=0.23",
  "httpx>=0.27",
]

[tool.pytest.ini_options]
asyncio_mode = "auto"
markers = ["live: live tests that hit the real Anthropic API (skipped by default)"]
addopts = "-m 'not live'"
```

- [ ] **Step 2: Write `backend/app/main.py`**

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="PDF Extract")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict:
    return {"ok": True}
```

- [ ] **Step 3: Write `backend/tests/conftest.py`**

```python
import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)
```

- [ ] **Step 4: Write `backend/tests/test_health.py`**

```python
def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"ok": True}
```

- [ ] **Step 5: Install and run**

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -e '.[dev]'
pytest -v
```

Expected: 1 passed.

- [ ] **Step 6: Commit**

```bash
git add backend/
git commit -m "feat(backend): scaffold FastAPI app with health endpoint"
```

---

## Task 2: Schema module

**Files:**
- Create: `backend/app/schema.py`
- Create: `backend/tests/test_schema.py`

- [ ] **Step 1: Write `backend/tests/test_schema.py`**

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd backend && pytest tests/test_schema.py -v
```
Expected: ImportError / module not found.

- [ ] **Step 3: Write `backend/app/schema.py`**

```python
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


DEFAULT_SCHEMA: list[FieldDef] = [
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
]


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
    target = next((f for f in schema if f.name == name), None)
    if target is None:
        raise ValueError(f"field '{name}' not found")
    if not target.removable:
        raise ValueError(f"field '{name}' is not removable")
    return [f for f in schema if f.name != name]


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
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/test_schema.py -v
```
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add backend/app/schema.py backend/tests/test_schema.py
git commit -m "feat(backend): default field schema with validation and tool-schema builder"
```

---

## Task 3: PDF renderer

**Files:**
- Create: `backend/app/pdf_renderer.py`
- Create: `backend/tests/test_pdf_renderer.py`
- Create: `backend/tests/fixtures/EC_1105-2-2.pdf` (copy of sample)

- [ ] **Step 1: Copy a small sample as a fixture**

```bash
cp "DOD SAFE-8f7gk7Rejn97VEuB/EC 1105-2-2_19720615.pdf" backend/tests/fixtures/EC_1105-2-2.pdf
```

- [ ] **Step 2: Write `backend/tests/test_pdf_renderer.py`**

```python
from pathlib import Path

import pytest

from app.pdf_renderer import (
    PdfOpenError,
    page_count,
    render_page_png,
    text_length,
)

FIXTURE = Path(__file__).parent / "fixtures" / "EC_1105-2-2.pdf"


@pytest.fixture
def pdf_bytes() -> bytes:
    return FIXTURE.read_bytes()


def test_page_count(pdf_bytes):
    assert page_count(pdf_bytes) == 1


def test_render_page_returns_png_bytes(pdf_bytes):
    png = render_page_png(pdf_bytes, 0)
    assert png[:8] == b"\x89PNG\r\n\x1a\n"


def test_render_page_respects_max_edge(pdf_bytes):
    from PIL import Image
    import io

    png = render_page_png(pdf_bytes, 0, max_edge=1024)
    img = Image.open(io.BytesIO(png))
    assert max(img.size) <= 1024


def test_text_length_nonzero(pdf_bytes):
    assert text_length(pdf_bytes, 0) > 100


def test_invalid_pdf_raises():
    with pytest.raises(PdfOpenError):
        render_page_png(b"not a pdf", 0)
```

Add `Pillow` to dev deps for the size assertion: edit `backend/pyproject.toml` and append `"pillow>=10",` to the `dev` extras list, then `pip install -e '.[dev]'`.

- [ ] **Step 3: Run tests to verify they fail**

```bash
pytest tests/test_pdf_renderer.py -v
```
Expected: ImportError.

- [ ] **Step 4: Write `backend/app/pdf_renderer.py`**

```python
from __future__ import annotations

import io

import fitz  # PyMuPDF


class PdfOpenError(ValueError):
    pass


def _open(pdf_bytes: bytes) -> fitz.Document:
    try:
        return fitz.open(stream=pdf_bytes, filetype="pdf")
    except Exception as e:
        raise PdfOpenError(str(e)) from e


def page_count(pdf_bytes: bytes) -> int:
    doc = _open(pdf_bytes)
    try:
        return doc.page_count
    finally:
        doc.close()


def text_length(pdf_bytes: bytes, page_index: int) -> int:
    doc = _open(pdf_bytes)
    try:
        return len(doc[page_index].get_text().strip())
    finally:
        doc.close()


def render_page_png(pdf_bytes: bytes, page_index: int, *, dpi: int = 150, max_edge: int = 1568) -> bytes:
    """Render a page to PNG bytes, downscaled so the longest edge ≤ max_edge."""
    doc = _open(pdf_bytes)
    try:
        page = doc[page_index]
        zoom = dpi / 72.0
        rect = page.rect
        longest = max(rect.width, rect.height) * zoom
        if longest > max_edge:
            zoom *= max_edge / longest
        matrix = fitz.Matrix(zoom, zoom)
        pix = page.get_pixmap(matrix=matrix, alpha=False)
        return pix.tobytes("png")
    finally:
        doc.close()
```

- [ ] **Step 5: Run tests**

```bash
pytest tests/test_pdf_renderer.py -v
```
Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add backend/app/pdf_renderer.py backend/tests/test_pdf_renderer.py backend/tests/fixtures/ backend/pyproject.toml
git commit -m "feat(backend): PDF renderer using PyMuPDF with downscale"
```

---

## Task 4: Merge logic

**Files:**
- Create: `backend/app/merge.py`
- Create: `backend/tests/test_merge.py`

- [ ] **Step 1: Write `backend/tests/test_merge.py`**

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_merge.py -v
```
Expected: ImportError.

- [ ] **Step 3: Write `backend/app/merge.py`**

```python
from __future__ import annotations

from app.schema import FieldDef


def merge_page_results(
    page_results: list[dict | None],
    schema: list[FieldDef],
) -> dict[str, str | list[str]]:
    """Merge per-page partial results into a single doc-level value dict.

    Scalars: first non-null/non-empty value, page-1 priority.
    Lists: concat across pages, dedupe preserving first-seen order.
    Missing or None per-page result is skipped.
    """
    out: dict[str, str | list[str]] = {}
    for f in schema:
        if f.type == "string":
            value = ""
            for pr in page_results:
                if not pr:
                    continue
                v = pr.get(f.name)
                if isinstance(v, str) and v.strip():
                    value = v
                    break
            out[f.name] = value
        else:  # list[string]
            seen: set[str] = set()
            collected: list[str] = []
            for pr in page_results:
                if not pr:
                    continue
                v = pr.get(f.name)
                if not isinstance(v, list):
                    continue
                for item in v:
                    if isinstance(item, str) and item not in seen:
                        seen.add(item)
                        collected.append(item)
            out[f.name] = collected
    return out
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/test_merge.py -v
```
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add backend/app/merge.py backend/tests/test_merge.py
git commit -m "feat(backend): per-page result merge with scalar priority and list dedupe"
```

---

## Task 5: PATCH operations

**Files:**
- Create: `backend/app/ops.py`
- Create: `backend/tests/test_ops.py`

- [ ] **Step 1: Write `backend/tests/test_ops.py`**

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_ops.py -v
```
Expected: ImportError.

- [ ] **Step 3: Write `backend/app/ops.py`**

```python
from __future__ import annotations

from app.schema import FieldDef


class OpError(ValueError):
    pass


def _field(state: dict, name: str) -> FieldDef:
    for f in state["schema"]:
        if f.name == name:
            return f
    raise OpError(f"unknown field '{name}'")


def apply_op(state: dict, op: dict) -> None:
    """Mutate state['values'] according to op. state has keys: schema, values, original_extracted."""
    kind = op.get("op")
    name = op.get("field")
    if not isinstance(name, str):
        raise OpError("op.field is required")
    f = _field(state, name)

    if kind == "set":
        if f.type != "string":
            raise OpError(f"'set' only valid for scalar fields; '{name}' is {f.type}")
        value = op.get("value")
        if not isinstance(value, str):
            raise OpError("op.value must be a string")
        state["values"][name] = value
        return

    if kind == "append":
        if f.type != "list[string]":
            raise OpError(f"'append' only valid for list fields; '{name}' is {f.type}")
        value = op.get("value")
        if not isinstance(value, str):
            raise OpError("op.value must be a string")
        current = state["values"].setdefault(name, [])
        if value not in current:
            current.append(value)
        return

    if kind == "remove":
        if f.type != "list[string]":
            raise OpError(f"'remove' only valid for list fields; '{name}' is {f.type}")
        idx = op.get("index")
        if not isinstance(idx, int):
            raise OpError("op.index must be an int")
        current = state["values"].get(name, [])
        if idx < 0 or idx >= len(current):
            raise OpError(f"index {idx} out of range")
        current.pop(idx)
        return

    if kind == "revert":
        original = state["original_extracted"].get(name)
        if original is None:
            state["values"][name] = "" if f.type == "string" else []
        else:
            # Copy to avoid sharing the list
            state["values"][name] = list(original) if isinstance(original, list) else original
        return

    raise OpError(f"unknown op '{kind}'")
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/test_ops.py -v
```
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add backend/app/ops.py backend/tests/test_ops.py
git commit -m "feat(backend): PATCH operations (set, append, remove, revert)"
```

---

## Task 6: Session store

**Files:**
- Create: `backend/app/session_store.py`

- [ ] **Step 1: Write `backend/app/session_store.py`**

```python
from __future__ import annotations

import threading
import uuid
from dataclasses import dataclass, field

from app.schema import FieldDef


@dataclass
class SessionState:
    pdf_bytes: bytes
    page_images: list[bytes]
    schema: list[FieldDef]
    values: dict[str, str | list[str]]
    original_extracted: dict[str, str | list[str]]
    extraction_errors: list[int] = field(default_factory=list)


class SessionStore:
    def __init__(self) -> None:
        self._sessions: dict[str, SessionState] = {}
        self._lock = threading.Lock()

    def create(self, state: SessionState) -> str:
        sid = uuid.uuid4().hex
        with self._lock:
            self._sessions[sid] = state
        return sid

    def get(self, sid: str) -> SessionState:
        with self._lock:
            state = self._sessions.get(sid)
        if state is None:
            raise KeyError(sid)
        return state

    def clear(self) -> None:
        with self._lock:
            self._sessions.clear()


# Module-level singleton used by routes; replaced in tests via dependency injection.
store = SessionStore()
```

No test file; this is exercised by route tests (Task 9). The dataclass and store are trivial enough that route-level integration is the right test layer.

- [ ] **Step 2: Commit**

```bash
git add backend/app/session_store.py
git commit -m "feat(backend): in-memory session store with UUID keys"
```

---

## Task 7: Extractor (Anthropic client)

**Files:**
- Create: `backend/app/extractor.py`
- Create: `backend/tests/test_extractor.py`

- [ ] **Step 1: Write `backend/tests/test_extractor.py`**

```python
import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.extractor import extract_page
from app.schema import DEFAULT_SCHEMA


def _fake_anthropic_response(tool_input: dict) -> MagicMock:
    block = MagicMock()
    block.type = "tool_use"
    block.name = "record_extracted_fields"
    block.input = tool_input
    response = MagicMock()
    response.content = [block]
    response.stop_reason = "tool_use"
    return response


@pytest.mark.asyncio
async def test_extract_page_returns_tool_input():
    expected = {f.name: None for f in DEFAULT_SCHEMA}
    expected["title"] = "Hello"
    fake_client = MagicMock()
    fake_client.messages.create = AsyncMock(return_value=_fake_anthropic_response(expected))

    result = await extract_page(b"PNG", DEFAULT_SCHEMA, client=fake_client)
    assert result == expected
    args, kwargs = fake_client.messages.create.call_args
    assert kwargs["tools"][0]["name"] == "record_extracted_fields"
    assert kwargs["tool_choice"] == {"type": "tool", "name": "record_extracted_fields"}
    msg = kwargs["messages"][0]["content"]
    image_block = next(b for b in msg if b["type"] == "image")
    assert image_block["source"]["type"] == "base64"
    assert image_block["source"]["media_type"] == "image/png"


@pytest.mark.asyncio
async def test_extract_page_returns_none_on_no_tool_use():
    response = MagicMock()
    text_block = MagicMock()
    text_block.type = "text"
    response.content = [text_block]
    response.stop_reason = "end_turn"
    fake_client = MagicMock()
    fake_client.messages.create = AsyncMock(return_value=response)
    result = await extract_page(b"PNG", DEFAULT_SCHEMA, client=fake_client)
    assert result is None


@pytest.mark.asyncio
async def test_extract_page_returns_none_on_exception():
    fake_client = MagicMock()
    fake_client.messages.create = AsyncMock(side_effect=RuntimeError("API down"))
    result = await extract_page(b"PNG", DEFAULT_SCHEMA, client=fake_client)
    assert result is None
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_extractor.py -v
```
Expected: ImportError.

- [ ] **Step 3: Write `backend/app/extractor.py`**

```python
from __future__ import annotations

import asyncio
import base64
import logging
import os
from typing import Any

from anthropic import AsyncAnthropic

from app.schema import FieldDef, build_tool_input_schema

logger = logging.getLogger(__name__)

MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-5")
PER_PAGE_TIMEOUT_S = 60.0

_TOOL_NAME = "record_extracted_fields"


def _tool_definition(schema: list[FieldDef]) -> dict[str, Any]:
    return {
        "name": _TOOL_NAME,
        "description": (
            "Record fields extracted from this PDF page. "
            "Use null for any field not visible on this page; "
            "do not invent or infer values that are not present."
        ),
        "input_schema": build_tool_input_schema(schema),
    }


def _client() -> AsyncAnthropic:
    return AsyncAnthropic()


async def extract_page(
    image_png: bytes,
    schema: list[FieldDef],
    *,
    client: AsyncAnthropic | None = None,
) -> dict | None:
    """Call Claude Vision with a tool definition derived from the schema.

    Returns the tool's input dict on success, or None on any failure
    (timeout, API error, no tool_use block, etc.).
    """
    cli = client or _client()
    image_b64 = base64.standard_b64encode(image_png).decode("ascii")
    tool = _tool_definition(schema)
    try:
        response = await asyncio.wait_for(
            cli.messages.create(
                model=MODEL,
                max_tokens=4096,
                tools=[tool],
                tool_choice={"type": "tool", "name": _TOOL_NAME},
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "image",
                                "source": {
                                    "type": "base64",
                                    "media_type": "image/png",
                                    "data": image_b64,
                                },
                            },
                            {
                                "type": "text",
                                "text": (
                                    "Extract the listed fields from this PDF page. "
                                    "Return null for any field not present on this page."
                                ),
                            },
                        ],
                    }
                ],
            ),
            timeout=PER_PAGE_TIMEOUT_S,
        )
    except (asyncio.TimeoutError, Exception) as e:  # noqa: BLE001
        logger.warning("extract_page failed: %s", e)
        return None

    for block in response.content:
        if getattr(block, "type", None) == "tool_use" and getattr(block, "name", None) == _TOOL_NAME:
            inp = getattr(block, "input", None)
            if isinstance(inp, dict):
                return inp
    return None
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/test_extractor.py -v
```
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add backend/app/extractor.py backend/tests/test_extractor.py
git commit -m "feat(backend): Anthropic Vision extractor with tool-use forced output"
```

---

## Task 8: Routes — upload + PDF serve

**Files:**
- Create: `backend/app/routes.py`
- Modify: `backend/app/main.py` (register routes)
- Create: `backend/tests/test_routes.py`

- [ ] **Step 1: Write `backend/app/routes.py`**

```python
from __future__ import annotations

import asyncio
import logging
from dataclasses import asdict
from typing import Any

from fastapi import APIRouter, File, HTTPException, Response, UploadFile
from pydantic import BaseModel

from app import extractor
from app.merge import merge_page_results
from app.ops import OpError, apply_op
from app.pdf_renderer import (
    PdfOpenError,
    page_count,
    render_page_png,
    text_length,
)
from app.schema import (
    DEFAULT_SCHEMA,
    add_custom_field,
    remove_field,
    validate_field_name,
)
from app.session_store import SessionState, store

logger = logging.getLogger(__name__)

MAX_UPLOAD_BYTES = 50 * 1024 * 1024  # 50MB
AUTO_EXTRACT_PAGES = 3
TOTAL_EXTRACT_TIMEOUT_S = 90.0

router = APIRouter()


def _serialize_session(sid: str, state: SessionState) -> dict[str, Any]:
    return {
        "session_id": sid,
        "page_count": len(state.page_images),
        "schema": [asdict(f) for f in state.schema],
        "values": state.values,
        "original_extracted": state.original_extracted,
        "extraction_errors": state.extraction_errors,
    }


@router.post("/upload")
async def upload(file: UploadFile = File(...)):
    if file.content_type not in ("application/pdf", "application/x-pdf"):
        raise HTTPException(400, "file must be a PDF")
    pdf_bytes = await file.read()
    if len(pdf_bytes) == 0:
        raise HTTPException(400, "empty file")
    if len(pdf_bytes) > MAX_UPLOAD_BYTES:
        raise HTTPException(413, f"file exceeds {MAX_UPLOAD_BYTES} bytes")

    try:
        n_pages = page_count(pdf_bytes)
    except PdfOpenError as e:
        raise HTTPException(400, f"could not open PDF: {e}") from None
    if n_pages == 0:
        raise HTTPException(400, "PDF has zero pages")

    page_images = [render_page_png(pdf_bytes, i) for i in range(n_pages)]
    schema = list(DEFAULT_SCHEMA)

    pages_to_extract = list(range(min(AUTO_EXTRACT_PAGES, n_pages)))
    try:
        per_page_results = await asyncio.wait_for(
            asyncio.gather(*(extractor.extract_page(page_images[i], schema) for i in pages_to_extract)),
            timeout=TOTAL_EXTRACT_TIMEOUT_S,
        )
    except asyncio.TimeoutError:
        per_page_results = [None] * len(pages_to_extract)

    extraction_errors = [pages_to_extract[i] + 1 for i, r in enumerate(per_page_results) if r is None]
    values = merge_page_results(per_page_results, schema)
    original_extracted = {k: (list(v) if isinstance(v, list) else v) for k, v in values.items()}

    state = SessionState(
        pdf_bytes=pdf_bytes,
        page_images=page_images,
        schema=schema,
        values=values,
        original_extracted=original_extracted,
        extraction_errors=extraction_errors,
    )
    sid = store.create(state)
    return _serialize_session(sid, state)


@router.get("/sessions/{sid}/pdf")
def get_pdf(sid: str):
    try:
        state = store.get(sid)
    except KeyError:
        raise HTTPException(404, "unknown session") from None
    return Response(content=state.pdf_bytes, media_type="application/pdf")


class PatchOp(BaseModel):
    op: str
    field: str
    value: str | None = None
    index: int | None = None


@router.patch("/sessions/{sid}/values")
def patch_values(sid: str, op: PatchOp):
    try:
        state = store.get(sid)
    except KeyError:
        raise HTTPException(404, "unknown session") from None
    state_dict = {
        "schema": state.schema,
        "values": state.values,
        "original_extracted": state.original_extracted,
    }
    try:
        apply_op(state_dict, op.model_dump(exclude_none=True))
    except OpError as e:
        raise HTTPException(400, str(e)) from None
    return {"field": op.field, "value": state.values.get(op.field)}


class AddFieldRequest(BaseModel):
    name: str


@router.post("/sessions/{sid}/fields")
def add_field(sid: str, req: AddFieldRequest):
    try:
        state = store.get(sid)
    except KeyError:
        raise HTTPException(404, "unknown session") from None
    try:
        validate_field_name(req.name)
    except ValueError as e:
        raise HTTPException(400, str(e)) from None
    try:
        new_schema = add_custom_field(state.schema, req.name)
    except ValueError as e:
        msg = str(e)
        status = 409 if "already exists" in msg else 400
        raise HTTPException(status, msg) from None
    state.schema = new_schema
    new_field = new_schema[-1]
    state.values.setdefault(new_field.name, "")
    return {"schema": [asdict(f) for f in state.schema]}


@router.delete("/sessions/{sid}/fields/{name}")
def delete_field(sid: str, name: str):
    try:
        state = store.get(sid)
    except KeyError:
        raise HTTPException(404, "unknown session") from None
    try:
        new_schema = remove_field(state.schema, name)
    except ValueError as e:
        raise HTTPException(400, str(e)) from None
    state.schema = new_schema
    state.values.pop(name, None)
    state.original_extracted.pop(name, None)
    return {"schema": [asdict(f) for f in state.schema]}


class ExtractPageRequest(BaseModel):
    page: int  # 1-indexed


@router.post("/sessions/{sid}/extract-page")
async def extract_single_page(sid: str, req: ExtractPageRequest):
    try:
        state = store.get(sid)
    except KeyError:
        raise HTTPException(404, "unknown session") from None
    page_idx = req.page - 1
    if page_idx < 0 or page_idx >= len(state.page_images):
        raise HTTPException(400, "page out of range")
    result = await extractor.extract_page(state.page_images[page_idx], state.schema)
    if result is None:
        raise HTTPException(502, f"extraction failed for page {req.page}")
    # Re-merge: scalars only fill if currently empty; lists append-dedupe.
    for f in state.schema:
        v = result.get(f.name)
        if f.type == "string":
            if isinstance(v, str) and v.strip() and not state.values.get(f.name):
                state.values[f.name] = v
        else:
            if isinstance(v, list):
                current = state.values.setdefault(f.name, [])
                seen = set(current)
                for item in v:
                    if isinstance(item, str) and item not in seen:
                        seen.add(item)
                        current.append(item)
    return {"values": state.values}


@router.get("/sessions/{sid}/page/{n}/text-length")
def page_text_length(sid: str, n: int):
    """Used by frontend to show a 'no selectable text' hint."""
    try:
        state = store.get(sid)
    except KeyError:
        raise HTTPException(404, "unknown session") from None
    if n < 1 or n > len(state.page_images):
        raise HTTPException(400, "page out of range")
    return {"length": text_length(state.pdf_bytes, n - 1)}
```

- [ ] **Step 2: Modify `backend/app/main.py` to register the router**

Replace the file with:

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routes import router

app = FastAPI(title="PDF Extract")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)


@app.get("/health")
def health() -> dict:
    return {"ok": True}
```

- [ ] **Step 3: Write `backend/tests/test_routes.py`**

```python
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from app import session_store

FIXTURE = Path(__file__).parent / "fixtures" / "EC_1105-2-2.pdf"


@pytest.fixture(autouse=True)
def reset_store():
    session_store.store.clear()
    yield
    session_store.store.clear()


@pytest.fixture
def fake_extract():
    async def _fake(image: bytes, schema, client=None):
        return {f.name: None for f in schema} | {
            "title": "Test Doc",
            "document_number": "EC 1105-2-2",
            "references": ["AR 1-1"],
        }
    with patch("app.routes.extractor.extract_page", side_effect=_fake):
        yield


def _upload(client, **patches):
    return client.post(
        "/upload",
        files={"file": ("sample.pdf", FIXTURE.read_bytes(), "application/pdf")},
    )


def test_upload_rejects_non_pdf(client):
    r = client.post("/upload", files={"file": ("x.txt", b"hello", "text/plain")})
    assert r.status_code == 400


def test_upload_rejects_empty(client):
    r = client.post("/upload", files={"file": ("x.pdf", b"", "application/pdf")})
    assert r.status_code == 400


def test_upload_rejects_corrupt(client):
    r = client.post("/upload", files={"file": ("x.pdf", b"not a pdf", "application/pdf")})
    assert r.status_code == 400


def test_upload_returns_session(client, fake_extract):
    r = _upload(client)
    assert r.status_code == 200
    body = r.json()
    assert body["page_count"] == 1
    assert body["values"]["title"] == "Test Doc"
    assert body["values"]["document_number"] == "EC 1105-2-2"
    assert body["values"]["references"] == ["AR 1-1"]
    assert body["original_extracted"]["title"] == "Test Doc"


def test_upload_records_extraction_errors(client):
    async def _fail(image, schema, client=None):
        return None
    with patch("app.routes.extractor.extract_page", side_effect=_fail):
        r = _upload(client)
    assert r.json()["extraction_errors"] == [1]
    assert r.json()["values"]["title"] == ""


def test_get_pdf_returns_bytes(client, fake_extract):
    sid = _upload(client).json()["session_id"]
    r = client.get(f"/sessions/{sid}/pdf")
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/pdf"
    assert r.content[:4] == b"%PDF"


def test_patch_set_scalar(client, fake_extract):
    sid = _upload(client).json()["session_id"]
    r = client.patch(
        f"/sessions/{sid}/values",
        json={"op": "set", "field": "title", "value": "Manual"},
    )
    assert r.status_code == 200
    assert r.json()["value"] == "Manual"


def test_patch_revert_returns_to_original(client, fake_extract):
    sid = _upload(client).json()["session_id"]
    client.patch(f"/sessions/{sid}/values",
                 json={"op": "set", "field": "title", "value": "Manual"})
    r = client.patch(f"/sessions/{sid}/values",
                     json={"op": "revert", "field": "title"})
    assert r.json()["value"] == "Test Doc"


def test_add_custom_field(client, fake_extract):
    sid = _upload(client).json()["session_id"]
    r = client.post(f"/sessions/{sid}/fields", json={"name": "keywords"})
    assert r.status_code == 200
    names = [f["name"] for f in r.json()["schema"]]
    assert "keywords" in names


def test_add_duplicate_field_returns_409(client, fake_extract):
    sid = _upload(client).json()["session_id"]
    r = client.post(f"/sessions/{sid}/fields", json={"name": "title"})
    assert r.status_code == 409


def test_delete_removable_field(client, fake_extract):
    sid = _upload(client).json()["session_id"]
    r = client.delete(f"/sessions/{sid}/fields/references")
    assert r.status_code == 200
    assert "references" not in [f["name"] for f in r.json()["schema"]]


def test_delete_non_removable_field_400(client, fake_extract):
    sid = _upload(client).json()["session_id"]
    r = client.delete(f"/sessions/{sid}/fields/title")
    assert r.status_code == 400


def test_extract_page_re_merge_only_fills_empty_scalars(client, fake_extract):
    sid = _upload(client).json()["session_id"]
    # Manually clear title, then re-extract — should refill from extractor.
    client.patch(f"/sessions/{sid}/values",
                 json={"op": "set", "field": "title", "value": ""})
    r = client.post(f"/sessions/{sid}/extract-page", json={"page": 1})
    assert r.json()["values"]["title"] == "Test Doc"


def test_extract_page_does_not_overwrite_user_scalar(client, fake_extract):
    sid = _upload(client).json()["session_id"]
    client.patch(f"/sessions/{sid}/values",
                 json={"op": "set", "field": "title", "value": "Mine"})
    r = client.post(f"/sessions/{sid}/extract-page", json={"page": 1})
    assert r.json()["values"]["title"] == "Mine"


def test_unknown_session_404(client):
    r = client.get("/sessions/nope/pdf")
    assert r.status_code == 404
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/test_routes.py -v
```
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add backend/app/routes.py backend/app/main.py backend/tests/test_routes.py
git commit -m "feat(backend): wire all routes (upload, pdf, values, fields, extract-page)"
```

---

## Task 9: Frontend scaffold

**Files:**
- Create: `frontend/package.json`
- Create: `frontend/vite.config.ts`
- Create: `frontend/tsconfig.json`
- Create: `frontend/index.html`
- Create: `frontend/src/main.tsx`
- Create: `frontend/src/App.tsx`
- Create: `frontend/src/styles.css`

- [ ] **Step 1: Initialize and write `frontend/package.json`**

```json
{
  "name": "pdf-extract-frontend",
  "private": true,
  "version": "0.1.0",
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "tsc -b && vite build",
    "test": "vitest run",
    "test:watch": "vitest"
  },
  "dependencies": {
    "react": "^18.3.0",
    "react-dom": "^18.3.0",
    "react-pdf": "^9.1.0",
    "zustand": "^4.5.0"
  },
  "devDependencies": {
    "@testing-library/react": "^16.0.0",
    "@testing-library/user-event": "^14.5.0",
    "@types/react": "^18.3.0",
    "@types/react-dom": "^18.3.0",
    "@vitejs/plugin-react": "^4.3.0",
    "jsdom": "^25.0.0",
    "typescript": "^5.5.0",
    "vite": "^5.4.0",
    "vitest": "^2.1.0"
  }
}
```

- [ ] **Step 2: Write `frontend/vite.config.ts`**

```typescript
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/upload": "http://localhost:8000",
      "/sessions": "http://localhost:8000",
      "/health": "http://localhost:8000",
    },
  },
  test: {
    environment: "jsdom",
    globals: true,
  },
});
```

- [ ] **Step 3: Write `frontend/tsconfig.json`**

```json
{
  "compilerOptions": {
    "target": "ES2020",
    "lib": ["ES2020", "DOM", "DOM.Iterable"],
    "jsx": "react-jsx",
    "module": "ESNext",
    "moduleResolution": "bundler",
    "strict": true,
    "noUnusedLocals": true,
    "noUnusedParameters": true,
    "esModuleInterop": true,
    "skipLibCheck": true,
    "types": ["vitest/globals"]
  },
  "include": ["src"]
}
```

- [ ] **Step 4: Write `frontend/index.html`**

```html
<!doctype html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>PDF Extract</title>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.tsx"></script>
  </body>
</html>
```

- [ ] **Step 5: Write `frontend/src/main.tsx`**

```tsx
import React from "react";
import ReactDOM from "react-dom/client";

import { App } from "./App";
import "./styles.css";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
```

- [ ] **Step 6: Write `frontend/src/App.tsx`**

```tsx
export function App() {
  return <div className="app">PDF Extract — scaffold OK</div>;
}
```

- [ ] **Step 7: Write `frontend/src/styles.css`**

```css
:root {
  font-family: system-ui, sans-serif;
  color-scheme: light;
}
body { margin: 0; }
.app { padding: 24px; }
```

- [ ] **Step 8: Install and verify**

```bash
cd frontend && npm install
npm run dev &  # then open http://localhost:5173 — confirm scaffold message renders
```

Kill the dev server (`kill %1`).

- [ ] **Step 9: Commit**

```bash
git add frontend/
git commit -m "feat(frontend): Vite + React scaffold"
```

---

## Task 10: Frontend types, API client, store

**Files:**
- Create: `frontend/src/types.ts`
- Create: `frontend/src/api.ts`
- Create: `frontend/src/store.ts`
- Create: `frontend/src/store.test.ts`

- [ ] **Step 1: Write `frontend/src/types.ts`**

```typescript
export type FieldType = "string" | "list[string]";

export interface FieldDef {
  name: string;
  type: FieldType;
  removable: boolean;
}

export type FieldValue = string | string[];

export interface SessionData {
  session_id: string;
  page_count: number;
  schema: FieldDef[];
  values: Record<string, FieldValue>;
  original_extracted: Record<string, FieldValue>;
  extraction_errors: number[];
}

export type PatchOp =
  | { op: "set"; field: string; value: string }
  | { op: "append"; field: string; value: string }
  | { op: "remove"; field: string; index: number }
  | { op: "revert"; field: string };
```

- [ ] **Step 2: Write `frontend/src/api.ts`**

```typescript
import type { FieldDef, PatchOp, SessionData } from "./types";

async function jsonOrThrow<T>(res: Response): Promise<T> {
  if (!res.ok) {
    const detail = await res.text();
    throw new Error(`${res.status}: ${detail}`);
  }
  return res.json() as Promise<T>;
}

export const api = {
  upload: async (file: File): Promise<SessionData> => {
    const fd = new FormData();
    fd.append("file", file);
    return jsonOrThrow(await fetch("/upload", { method: "POST", body: fd }));
  },
  pdfUrl: (sid: string) => `/sessions/${sid}/pdf`,
  patchValues: async (sid: string, op: PatchOp): Promise<{ field: string; value: unknown }> =>
    jsonOrThrow(
      await fetch(`/sessions/${sid}/values`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(op),
      }),
    ),
  addField: async (sid: string, name: string): Promise<{ schema: FieldDef[] }> =>
    jsonOrThrow(
      await fetch(`/sessions/${sid}/fields`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name }),
      }),
    ),
  deleteField: async (sid: string, name: string): Promise<{ schema: FieldDef[] }> =>
    jsonOrThrow(
      await fetch(`/sessions/${sid}/fields/${encodeURIComponent(name)}`, {
        method: "DELETE",
      }),
    ),
  extractPage: async (sid: string, page: number): Promise<{ values: Record<string, unknown> }> =>
    jsonOrThrow(
      await fetch(`/sessions/${sid}/extract-page`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ page }),
      }),
    ),
  pageTextLength: async (sid: string, page: number): Promise<{ length: number }> =>
    jsonOrThrow(await fetch(`/sessions/${sid}/page/${page}/text-length`)),
};
```

- [ ] **Step 3: Write `frontend/src/store.ts`**

```typescript
import { create } from "zustand";

import type { FieldDef, FieldValue, SessionData } from "./types";

interface AppState {
  session: SessionData | null;
  currentPage: number;

  setSession: (s: SessionData) => void;
  reset: () => void;
  setPage: (p: number) => void;

  setFieldValue: (field: string, value: FieldValue) => void;
  appendFieldValue: (field: string, value: string) => void;
  removeFieldValue: (field: string, index: number) => void;
  revertField: (field: string) => void;
  addField: (f: FieldDef) => void;
  deleteField: (name: string) => void;
  setSchema: (schema: FieldDef[]) => void;
  applyMergedValues: (values: Record<string, FieldValue>) => void;
}

const isList = (v: FieldValue | undefined): v is string[] => Array.isArray(v);

export const useApp = create<AppState>((set, get) => ({
  session: null,
  currentPage: 1,

  setSession: (s) => set({ session: s, currentPage: 1 }),
  reset: () => set({ session: null, currentPage: 1 }),
  setPage: (p) => set({ currentPage: p }),

  setFieldValue: (field, value) => {
    const s = get().session;
    if (!s) return;
    set({ session: { ...s, values: { ...s.values, [field]: value } } });
  },

  appendFieldValue: (field, value) => {
    const s = get().session;
    if (!s) return;
    const current = s.values[field];
    const list = isList(current) ? current : [];
    if (list.includes(value)) return;
    set({ session: { ...s, values: { ...s.values, [field]: [...list, value] } } });
  },

  removeFieldValue: (field, index) => {
    const s = get().session;
    if (!s) return;
    const current = s.values[field];
    if (!isList(current)) return;
    const next = current.filter((_, i) => i !== index);
    set({ session: { ...s, values: { ...s.values, [field]: next } } });
  },

  revertField: (field) => {
    const s = get().session;
    if (!s) return;
    const def = s.schema.find((f) => f.name === field);
    const orig = s.original_extracted[field];
    let restored: FieldValue;
    if (orig === undefined) {
      restored = def?.type === "list[string]" ? [] : "";
    } else {
      restored = isList(orig) ? [...orig] : orig;
    }
    set({ session: { ...s, values: { ...s.values, [field]: restored } } });
  },

  addField: (f) => {
    const s = get().session;
    if (!s) return;
    set({
      session: {
        ...s,
        schema: [...s.schema, f],
        values: { ...s.values, [f.name]: f.type === "list[string]" ? [] : "" },
      },
    });
  },

  deleteField: (name) => {
    const s = get().session;
    if (!s) return;
    const { [name]: _v, ...values } = s.values;
    const { [name]: _o, ...original_extracted } = s.original_extracted;
    set({
      session: {
        ...s,
        schema: s.schema.filter((f) => f.name !== name),
        values,
        original_extracted,
      },
    });
  },

  setSchema: (schema) => {
    const s = get().session;
    if (!s) return;
    set({ session: { ...s, schema } });
  },

  applyMergedValues: (values) => {
    const s = get().session;
    if (!s) return;
    const merged: Record<string, FieldValue> = { ...s.values };
    for (const [k, v] of Object.entries(values)) {
      merged[k] = v as FieldValue;
    }
    set({ session: { ...s, values: merged } });
  },
}));
```

- [ ] **Step 4: Write `frontend/src/store.test.ts`**

```typescript
import { beforeEach, describe, expect, it } from "vitest";

import { useApp } from "./store";
import type { SessionData } from "./types";

const sample: SessionData = {
  session_id: "abc",
  page_count: 1,
  schema: [
    { name: "title", type: "string", removable: false },
    { name: "references", type: "list[string]", removable: true },
  ],
  values: { title: "Original", references: ["A", "B"] },
  original_extracted: { title: "OrigClaude", references: ["A"] },
  extraction_errors: [],
};

describe("store", () => {
  beforeEach(() => useApp.getState().reset());

  it("setSession initializes", () => {
    useApp.getState().setSession(sample);
    expect(useApp.getState().session?.session_id).toBe("abc");
    expect(useApp.getState().currentPage).toBe(1);
  });

  it("setFieldValue updates scalar", () => {
    useApp.getState().setSession(sample);
    useApp.getState().setFieldValue("title", "Edited");
    expect(useApp.getState().session?.values.title).toBe("Edited");
  });

  it("appendFieldValue appends and dedupes", () => {
    useApp.getState().setSession(sample);
    useApp.getState().appendFieldValue("references", "C");
    expect(useApp.getState().session?.values.references).toEqual(["A", "B", "C"]);
    useApp.getState().appendFieldValue("references", "A");
    expect(useApp.getState().session?.values.references).toEqual(["A", "B", "C"]);
  });

  it("removeFieldValue drops by index", () => {
    useApp.getState().setSession(sample);
    useApp.getState().removeFieldValue("references", 0);
    expect(useApp.getState().session?.values.references).toEqual(["B"]);
  });

  it("revertField restores scalar to original", () => {
    useApp.getState().setSession(sample);
    useApp.getState().setFieldValue("title", "Mine");
    useApp.getState().revertField("title");
    expect(useApp.getState().session?.values.title).toBe("OrigClaude");
  });

  it("revertField on field with no original uses empty default", () => {
    useApp.getState().setSession(sample);
    useApp.getState().addField({ name: "keywords", type: "string", removable: true });
    useApp.getState().setFieldValue("keywords", "x");
    useApp.getState().revertField("keywords");
    expect(useApp.getState().session?.values.keywords).toBe("");
  });
});
```

- [ ] **Step 5: Run tests**

```bash
cd frontend && npm test
```
Expected: 6 passed.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/types.ts frontend/src/api.ts frontend/src/store.ts frontend/src/store.test.ts
git commit -m "feat(frontend): types, API client, Zustand store with reducers"
```

---

## Task 11: Upload screen

**Files:**
- Create: `frontend/src/components/Upload.tsx`
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/styles.css`

- [ ] **Step 1: Write `frontend/src/components/Upload.tsx`**

```tsx
import { useState } from "react";

import { api } from "../api";
import { useApp } from "../store";

export function Upload() {
  const setSession = useApp((s) => s.setSession);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleFile(file: File) {
    setError(null);
    setBusy(true);
    try {
      const session = await api.upload(file);
      setSession(session);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="upload">
      <h1>PDF Extract</h1>
      <p>Upload a PDF to extract structured data.</p>
      <label className="upload-drop">
        <input
          type="file"
          accept="application/pdf"
          disabled={busy}
          onChange={(e) => e.target.files?.[0] && handleFile(e.target.files[0])}
        />
        {busy ? "Extracting…" : "Choose PDF"}
      </label>
      {error && <p className="error">Error: {error}</p>}
    </div>
  );
}
```

- [ ] **Step 2: Update `frontend/src/App.tsx`**

```tsx
import { Upload } from "./components/Upload";
import { useApp } from "./store";

export function App() {
  const session = useApp((s) => s.session);
  if (!session) return <Upload />;
  return <div className="app">Session loaded: {session.session_id}</div>;
}
```

- [ ] **Step 3: Append to `frontend/src/styles.css`**

```css
.upload { max-width: 480px; margin: 64px auto; }
.upload-drop {
  display: block;
  padding: 48px 24px;
  border: 2px dashed #aaa;
  border-radius: 8px;
  text-align: center;
  cursor: pointer;
}
.upload-drop input { display: block; margin: 12px auto 0; }
.error { color: #c00; }
```

- [ ] **Step 4: Manually verify**

In one terminal:
```bash
cd backend && source .venv/bin/activate && uvicorn app.main:app --reload --port 8000
```
In another:
```bash
cd frontend && npm run dev
```
Open `http://localhost:5173`. Upload `EC 1105-2-2_19720615.pdf`. Confirm the page swaps to "Session loaded: <hex>" within ~10–20s.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/Upload.tsx frontend/src/App.tsx frontend/src/styles.css
git commit -m "feat(frontend): upload screen with drop zone"
```

---

## Task 12: Workspace shell + PdfPane

**Files:**
- Create: `frontend/src/components/Workspace.tsx`
- Create: `frontend/src/components/PdfPane.tsx`
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/styles.css`

- [ ] **Step 1: Configure pdf.js worker**

`react-pdf` needs a worker file. Add to `frontend/src/main.tsx`, just below the import lines:

```tsx
import { pdfjs } from "react-pdf";
import "react-pdf/dist/Page/TextLayer.css";
import "react-pdf/dist/Page/AnnotationLayer.css";

pdfjs.GlobalWorkerOptions.workerSrc = new URL(
  "pdfjs-dist/build/pdf.worker.min.mjs",
  import.meta.url,
).toString();
```

(`pdfjs-dist` is a transitive dep of `react-pdf` — no extra install needed.)

- [ ] **Step 2: Write `frontend/src/components/PdfPane.tsx`**

```tsx
import { useEffect, useRef, useState } from "react";
import { Document, Page } from "react-pdf";

import { api } from "../api";
import { useApp } from "../store";

interface SelectionPayload {
  text: string;
  rect: DOMRect;
}

interface Props {
  onSelectText: (payload: SelectionPayload | null) => void;
}

export function PdfPane({ onSelectText }: Props) {
  const session = useApp((s) => s.session)!;
  const currentPage = useApp((s) => s.currentPage);
  const setPage = useApp((s) => s.setPage);
  const containerRef = useRef<HTMLDivElement>(null);
  const [textLengthHint, setTextLengthHint] = useState<number | null>(null);

  useEffect(() => {
    let cancelled = false;
    api.pageTextLength(session.session_id, currentPage).then(({ length }) => {
      if (!cancelled) setTextLengthHint(length);
    });
    return () => {
      cancelled = true;
    };
  }, [session.session_id, currentPage]);

  function handleMouseUp() {
    const sel = window.getSelection();
    if (!sel || sel.isCollapsed) {
      onSelectText(null);
      return;
    }
    const text = sel.toString().trim();
    if (!text) {
      onSelectText(null);
      return;
    }
    const range = sel.getRangeAt(0);
    const container = containerRef.current;
    if (!container || !container.contains(range.commonAncestorContainer)) {
      onSelectText(null);
      return;
    }
    onSelectText({ text, rect: range.getBoundingClientRect() });
  }

  return (
    <div className="pdf-pane">
      <div className="pager">
        <button disabled={currentPage <= 1} onClick={() => setPage(currentPage - 1)}>
          ◀
        </button>
        <span>
          Page {currentPage} / {session.page_count}
        </span>
        <button
          disabled={currentPage >= session.page_count}
          onClick={() => setPage(currentPage + 1)}
        >
          ▶
        </button>
      </div>
      {textLengthHint !== null && textLengthHint < 20 && (
        <div className="hint">This page has little or no selectable text.</div>
      )}
      <div className="pdf-canvas" ref={containerRef} onMouseUp={handleMouseUp}>
        <Document file={api.pdfUrl(session.session_id)}>
          <Page pageNumber={currentPage} width={700} renderAnnotationLayer={false} />
        </Document>
      </div>
    </div>
  );
}
```

- [ ] **Step 3: Write `frontend/src/components/Workspace.tsx`**

```tsx
import { useState } from "react";

import { PdfPane } from "./PdfPane";

interface PendingSelection {
  text: string;
  rect: DOMRect;
}

export function Workspace() {
  const [selection, setSelection] = useState<PendingSelection | null>(null);
  return (
    <div className="workspace">
      <PdfPane onSelectText={setSelection} />
      <div className="fields-pane">
        <p className="placeholder">Fields panel — populated in Task 13.</p>
        {selection && (
          <p className="placeholder">
            Selection captured: "{selection.text.slice(0, 40)}…" (popover in Task 13)
          </p>
        )}
      </div>
    </div>
  );
}
```

- [ ] **Step 4: Update `frontend/src/App.tsx`**

```tsx
import { Upload } from "./components/Upload";
import { Workspace } from "./components/Workspace";
import { useApp } from "./store";

export function App() {
  const session = useApp((s) => s.session);
  return session ? <Workspace /> : <Upload />;
}
```

- [ ] **Step 5: Append to `frontend/src/styles.css`**

```css
.workspace {
  display: grid;
  grid-template-columns: minmax(720px, 1fr) 420px;
  gap: 16px;
  padding: 16px;
  height: 100vh;
  box-sizing: border-box;
}
.pdf-pane { display: flex; flex-direction: column; gap: 8px; overflow: auto; }
.pager { display: flex; gap: 8px; align-items: center; }
.pager button { padding: 4px 12px; }
.pdf-canvas { background: #f4f4f4; padding: 8px; border-radius: 4px; user-select: text; }
.hint { background: #fff3cd; padding: 6px 10px; border-radius: 4px; font-size: 12px; }
.fields-pane { overflow: auto; border-left: 1px solid #ddd; padding-left: 16px; }
.placeholder { color: #888; }
```

- [ ] **Step 6: Manually verify**

Restart `npm run dev` and re-upload the sample PDF. Confirm:
- Page renders.
- Pager works on the multi-page sample (`EC 1105-2-6_19730309.pdf`, 2 pages).
- Selecting text shows the placeholder "Selection captured" line.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/components/Workspace.tsx frontend/src/components/PdfPane.tsx frontend/src/App.tsx frontend/src/main.tsx frontend/src/styles.css
git commit -m "feat(frontend): workspace shell with PDF pane and selection capture"
```

---

## Task 13: SelectionPopover + assignment flow

**Files:**
- Create: `frontend/src/components/SelectionPopover.tsx`
- Create: `frontend/src/components/AddFieldModal.tsx`
- Modify: `frontend/src/components/Workspace.tsx`
- Modify: `frontend/src/styles.css`

- [ ] **Step 1: Write `frontend/src/components/AddFieldModal.tsx`**

```tsx
import { useState } from "react";

interface Props {
  onConfirm: (name: string) => Promise<void>;
  onCancel: () => void;
}

export function AddFieldModal({ onConfirm, onCancel }: Props) {
  const [name, setName] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  function localValidate(value: string): string | null {
    const trimmed = value.trim();
    if (!trimmed) return "Name cannot be empty";
    if (trimmed.length > 40) return "Name must be 40 characters or fewer";
    if (!/^[A-Za-z0-9_\- ]+$/.test(trimmed))
      return "Only letters, digits, spaces, _ and - are allowed";
    return null;
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const local = localValidate(name);
    if (local) {
      setError(local);
      return;
    }
    setBusy(true);
    setError(null);
    try {
      await onConfirm(name.trim());
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="modal-backdrop" onClick={onCancel}>
      <form className="modal" onClick={(e) => e.stopPropagation()} onSubmit={handleSubmit}>
        <h3>Create field</h3>
        <input
          autoFocus
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="field name"
        />
        {error && <p className="error">{error}</p>}
        <div className="modal-actions">
          <button type="button" onClick={onCancel} disabled={busy}>Cancel</button>
          <button type="submit" disabled={busy}>{busy ? "Adding…" : "Add"}</button>
        </div>
      </form>
    </div>
  );
}
```

- [ ] **Step 2: Write `frontend/src/components/SelectionPopover.tsx`**

```tsx
import { useState } from "react";

import { api } from "../api";
import { useApp } from "../store";
import { AddFieldModal } from "./AddFieldModal";

interface Props {
  text: string;
  rect: DOMRect;
  onClose: () => void;
}

const NEW_FIELD_VALUE = "__new__";

export function SelectionPopover({ text, rect, onClose }: Props) {
  const session = useApp((s) => s.session)!;
  const setFieldValue = useApp((s) => s.setFieldValue);
  const appendFieldValue = useApp((s) => s.appendFieldValue);
  const addField = useApp((s) => s.addField);
  const [showModal, setShowModal] = useState(false);

  async function assign(fieldName: string) {
    const def = session.schema.find((f) => f.name === fieldName);
    if (!def) return;
    if (def.type === "string") {
      await api.patchValues(session.session_id, { op: "set", field: fieldName, value: text });
      setFieldValue(fieldName, text);
    } else {
      await api.patchValues(session.session_id, { op: "append", field: fieldName, value: text });
      appendFieldValue(fieldName, text);
    }
    onClose();
  }

  async function handleSelect(value: string) {
    if (value === NEW_FIELD_VALUE) {
      setShowModal(true);
      return;
    }
    await assign(value);
  }

  async function handleCreate(name: string) {
    const { schema } = await api.addField(session.session_id, name);
    const newField = schema.find((f) => f.name === name);
    if (newField) addField(newField);
    setShowModal(false);
    await assign(name);
  }

  const top = rect.bottom + window.scrollY + 4;
  const left = rect.left + window.scrollX;

  return (
    <>
      <div
        className="popover"
        style={{ top, left }}
        onClick={(e) => e.stopPropagation()}
        onMouseDown={(e) => e.preventDefault()} // don't clear selection
      >
        <span className="popover-label">Assign to…</span>
        <select defaultValue="" onChange={(e) => handleSelect(e.target.value)}>
          <option value="" disabled>
            choose field
          </option>
          {session.schema.map((f) => (
            <option key={f.name} value={f.name}>
              {f.name}
            </option>
          ))}
          <option value={NEW_FIELD_VALUE}>+ Create new field…</option>
        </select>
        <button className="popover-close" onClick={onClose}>✕</button>
      </div>
      {showModal && <AddFieldModal onConfirm={handleCreate} onCancel={() => setShowModal(false)} />}
    </>
  );
}
```

- [ ] **Step 3: Update `frontend/src/components/Workspace.tsx`**

```tsx
import { useState } from "react";

import { PdfPane } from "./PdfPane";
import { SelectionPopover } from "./SelectionPopover";

interface PendingSelection {
  text: string;
  rect: DOMRect;
}

export function Workspace() {
  const [selection, setSelection] = useState<PendingSelection | null>(null);

  return (
    <div className="workspace">
      <PdfPane onSelectText={setSelection} />
      <div className="fields-pane">
        <p className="placeholder">Fields panel — populated in Task 14.</p>
      </div>
      {selection && (
        <SelectionPopover
          text={selection.text}
          rect={selection.rect}
          onClose={() => setSelection(null)}
        />
      )}
    </div>
  );
}
```

- [ ] **Step 4: Append to `frontend/src/styles.css`**

```css
.popover {
  position: absolute;
  z-index: 50;
  background: white;
  border: 1px solid #888;
  border-radius: 4px;
  padding: 6px 8px;
  display: flex;
  gap: 6px;
  align-items: center;
  box-shadow: 0 2px 8px rgba(0,0,0,0.15);
  font-size: 13px;
}
.popover-label { color: #666; }
.popover-close { background: none; border: none; cursor: pointer; color: #888; }
.modal-backdrop {
  position: fixed; inset: 0; background: rgba(0,0,0,0.4);
  display: flex; align-items: center; justify-content: center; z-index: 100;
}
.modal {
  background: white; padding: 24px; border-radius: 6px;
  display: flex; flex-direction: column; gap: 12px; min-width: 320px;
}
.modal input { padding: 8px; font-size: 14px; }
.modal-actions { display: flex; justify-content: flex-end; gap: 8px; }
```

- [ ] **Step 5: Manually verify**

Restart frontend. Upload sample. Select text on the page. Popover appears. Pick `title` from the dropdown. Confirm no error in console; backend log shows PATCH 200. (FieldsPane is still placeholder, but the value did update — verify by `console.log(useApp.getState().session?.values.title)` in DevTools.)

Test "+ Create new field…": enter `keywords`, confirm popover closes and value is appended.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/components/SelectionPopover.tsx frontend/src/components/AddFieldModal.tsx frontend/src/components/Workspace.tsx frontend/src/styles.css
git commit -m "feat(frontend): selection popover with field assignment + new-field modal"
```

---

## Task 14: FieldsPane (scalar, list, revert, delete, re-extract)

**Files:**
- Create: `frontend/src/components/FieldsPane.tsx`
- Modify: `frontend/src/components/Workspace.tsx`
- Modify: `frontend/src/styles.css`

- [ ] **Step 1: Write `frontend/src/components/FieldsPane.tsx`**

```tsx
import { useState } from "react";

import { api } from "../api";
import { useApp } from "../store";
import type { FieldDef } from "../types";

function valuesEqual(a: unknown, b: unknown): boolean {
  if (Array.isArray(a) && Array.isArray(b)) {
    return a.length === b.length && a.every((x, i) => x === b[i]);
  }
  return a === b;
}

export function FieldsPane() {
  const session = useApp((s) => s.session)!;
  const currentPage = useApp((s) => s.currentPage);
  const setFieldValue = useApp((s) => s.setFieldValue);
  const removeFieldValue = useApp((s) => s.removeFieldValue);
  const revertField = useApp((s) => s.revertField);
  const deleteFieldStore = useApp((s) => s.deleteField);
  const applyMergedValues = useApp((s) => s.applyMergedValues);
  const [busy, setBusy] = useState(false);

  async function handleRevert(field: string) {
    await api.patchValues(session.session_id, { op: "revert", field });
    revertField(field);
  }

  async function handleScalarChange(field: string, value: string) {
    await api.patchValues(session.session_id, { op: "set", field, value });
    setFieldValue(field, value);
  }

  async function handleRemoveListItem(field: string, index: number) {
    await api.patchValues(session.session_id, { op: "remove", field, index });
    removeFieldValue(field, index);
  }

  async function handleDeleteField(field: FieldDef) {
    if (!confirm(`Delete field "${field.name}" and its value?`)) return;
    await api.deleteField(session.session_id, field.name);
    deleteFieldStore(field.name);
  }

  async function handleReExtract() {
    setBusy(true);
    try {
      const { values } = await api.extractPage(session.session_id, currentPage);
      applyMergedValues(values as Record<string, string | string[]>);
    } catch (e) {
      alert(`Re-extract failed: ${e instanceof Error ? e.message : e}`);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="fields-pane">
      <div className="fields-toolbar">
        <button onClick={handleReExtract} disabled={busy}>
          {busy ? "Re-extracting…" : `Re-extract page ${currentPage}`}
        </button>
      </div>
      {session.extraction_errors.length > 0 && (
        <div className="banner">
          Initial extraction failed for page(s): {session.extraction_errors.join(", ")}
        </div>
      )}
      {session.schema.map((f) => (
        <FieldRow
          key={f.name}
          field={f}
          value={session.values[f.name] ?? (f.type === "list[string]" ? [] : "")}
          original={session.original_extracted[f.name]}
          onScalarChange={handleScalarChange}
          onRevert={handleRevert}
          onRemoveItem={handleRemoveListItem}
          onDelete={handleDeleteField}
        />
      ))}
    </div>
  );
}

interface RowProps {
  field: FieldDef;
  value: string | string[];
  original: string | string[] | undefined;
  onScalarChange: (field: string, value: string) => Promise<void>;
  onRevert: (field: string) => Promise<void>;
  onRemoveItem: (field: string, index: number) => Promise<void>;
  onDelete: (field: FieldDef) => Promise<void>;
}

function FieldRow({ field, value, original, onScalarChange, onRevert, onRemoveItem, onDelete }: RowProps) {
  const dirty = !valuesEqual(value, original);
  const showRevert = original !== undefined && dirty;
  return (
    <div className="field-row">
      <div className="field-header">
        <label className="field-name">{field.name}</label>
        {showRevert && (
          <button className="link" onClick={() => onRevert(field.name)}>revert</button>
        )}
        {field.removable && (
          <button className="link danger" onClick={() => onDelete(field)}>delete</button>
        )}
      </div>
      {field.type === "string" ? (
        <input
          value={value as string}
          onChange={(e) => onScalarChange(field.name, e.target.value)}
        />
      ) : (
        <div className="chips">
          {(value as string[]).map((item, i) => (
            <span key={`${item}-${i}`} className="chip">
              {item}
              <button onClick={() => onRemoveItem(field.name, i)}>×</button>
            </span>
          ))}
          {(value as string[]).length === 0 && <span className="placeholder">(empty)</span>}
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 2: Update `frontend/src/components/Workspace.tsx`**

```tsx
import { useState } from "react";

import { FieldsPane } from "./FieldsPane";
import { PdfPane } from "./PdfPane";
import { SelectionPopover } from "./SelectionPopover";

interface PendingSelection {
  text: string;
  rect: DOMRect;
}

export function Workspace() {
  const [selection, setSelection] = useState<PendingSelection | null>(null);

  return (
    <div className="workspace">
      <PdfPane onSelectText={setSelection} />
      <FieldsPane />
      {selection && (
        <SelectionPopover
          text={selection.text}
          rect={selection.rect}
          onClose={() => setSelection(null)}
        />
      )}
    </div>
  );
}
```

- [ ] **Step 3: Append to `frontend/src/styles.css`**

```css
.fields-toolbar { padding-bottom: 12px; border-bottom: 1px solid #eee; margin-bottom: 12px; }
.field-row { padding: 8px 0; border-bottom: 1px solid #f0f0f0; }
.field-header {
  display: flex; align-items: baseline; gap: 8px;
  font-size: 12px; color: #555;
}
.field-name { font-weight: 600; color: #222; flex: 1; }
.link { background: none; border: none; padding: 0; color: #06c; cursor: pointer; font-size: 12px; }
.link.danger { color: #c00; }
.field-row input { width: 100%; box-sizing: border-box; padding: 4px 6px; font-size: 13px; }
.chips { display: flex; flex-wrap: wrap; gap: 4px; }
.chip {
  background: #eef; padding: 2px 6px; border-radius: 12px; font-size: 12px;
  display: inline-flex; align-items: center; gap: 4px;
}
.chip button { background: none; border: none; cursor: pointer; color: #666; }
.banner { background: #fee; padding: 8px; border-radius: 4px; margin-bottom: 12px; font-size: 13px; }
```

- [ ] **Step 4: Manually verify**

Restart frontend. Upload sample. Confirm:
- Right pane shows all 10 default fields with extracted values.
- Editing a scalar in the input updates state and PATCH succeeds (Network tab).
- Revert link appears once edited; clicking it restores Claude's original.
- For `references` (or any list with values), × removes a chip.
- USACE extras have a "delete" link; generic-core fields don't.
- "Re-extract page N" button refills empty scalar fields and appends to lists.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/FieldsPane.tsx frontend/src/components/Workspace.tsx frontend/src/styles.css
git commit -m "feat(frontend): fields panel with scalars, list chips, revert, delete, re-extract"
```

---

## Task 15: Live integration test + manual checklist

**Files:**
- Create: `backend/tests/test_live_extraction.py`
- Create: `docs/superpowers/MANUAL-CHECKLIST.md`

- [ ] **Step 1: Write `backend/tests/test_live_extraction.py`**

```python
"""Live test against the real Anthropic API. Skipped by default.

Run with:  pytest -m live -v
Requires:  ANTHROPIC_API_KEY in environment
"""
from pathlib import Path

import pytest

from app import extractor
from app.schema import DEFAULT_SCHEMA

FIXTURE = Path(__file__).parent / "fixtures" / "EC_1105-2-2.pdf"


@pytest.mark.live
@pytest.mark.asyncio
async def test_live_extraction_yields_document_number():
    from app.pdf_renderer import render_page_png

    pdf_bytes = FIXTURE.read_bytes()
    png = render_page_png(pdf_bytes, 0)
    result = await extractor.extract_page(png, list(DEFAULT_SCHEMA))
    assert result is not None, "extraction returned None"
    doc_num = result.get("document_number")
    assert isinstance(doc_num, str) and "1105-2-2" in doc_num, (
        f"expected document_number to mention 1105-2-2, got {doc_num!r}"
    )
```

- [ ] **Step 2: Run live test (manual, billable)**

```bash
cd backend
ANTHROPIC_API_KEY=sk-ant-... pytest -m live -v
```
Expected: PASS within ~30s.

- [ ] **Step 3: Write `docs/superpowers/MANUAL-CHECKLIST.md`**

```markdown
# PDF Extract — Manual Test Checklist

Run after each major change. Backend on `:8000`, frontend on `:5173`.

## Setup
- [ ] `cd backend && ANTHROPIC_API_KEY=… uvicorn app.main:app --reload --port 8000`
- [ ] `cd frontend && npm run dev`
- [ ] Open http://localhost:5173

## Sample uploads (use `DOD SAFE-8f7gk7Rejn97VEuB/`)
For each PDF:
- [ ] EC 1105-2-2_19720615.pdf — completes ≤30s, `document_number` non-empty
- [ ] EC 1105-2-6_19730309.pdf — completes ≤30s, pagination shows 2 pages
- [ ] ETL 1110-1-153_19930331.pdf — completes ≤30s, `document_number` non-empty
- [ ] ETL 1110-3-407_19891023.pdf — 99 pages, paginate to page 50, sees "no selectable text" hint
- [ ] EM 1110-2-400_19710901.pdf — 43 pages, completes ≤45s

## Interaction (with EC 1105-2-2)
- [ ] On page 1, select "EC 1105-2-2" → popover opens → assign to `document_number`. Value updates.
- [ ] Click "revert" next to `document_number`. Claude's original value returns.
- [ ] Add custom field `keywords` via "+ Create new field…" — assign 3 different selections to `keywords`. Use × to remove the middle one. List shows 2.
- [ ] Delete a USACE extra (e.g. `applicability`) via the row's "delete" link. Field disappears.
- [ ] Confirm `title` has no "delete" link (non-removable).

## Re-extract
- [ ] On EM 1110-2-400 page 3, click "Re-extract page 3". Watch list field `references` grow. Scalar fields previously edited do NOT change.

## State reset
- [ ] Refresh the browser. App returns to upload screen (state lost, expected).
- [ ] Restart backend. Frontend still loaded → next API call returns 404 → app redirects to upload.
```

- [ ] **Step 4: Commit**

```bash
git add backend/tests/test_live_extraction.py docs/superpowers/MANUAL-CHECKLIST.md
git commit -m "test: live extraction smoke test + manual checklist"
```

- [ ] **Step 5: Run the manual checklist**

Walk through `docs/superpowers/MANUAL-CHECKLIST.md` end-to-end with a real `ANTHROPIC_API_KEY`. File any deviations as follow-up tasks.

---

## Self-review (already applied)

**Spec coverage:**
- §3 Default Schema → Task 2 ✓
- §4.1 Components → Tasks 2-8 (backend), 9-14 (frontend) ✓
- §4.2 Data flow / Workspace interactions → Tasks 8 (re-extract route), 13 (assignment), 14 (revert/remove/delete/re-extract UI) ✓
- §4.4 API endpoints → Task 8 ✓
- §4.5 Vision call shape → Task 7 ✓
- §5 Error handling: upload validation (Task 8), extraction timeouts (Task 7), schema validation (Task 2), session 404 (Task 8), revert empty default (Tasks 5, 10) ✓
- §6 Testing strategy → Tasks 2-8 unit/integration, Task 10 frontend reducer, Task 15 live + manual ✓
- §7 Out-of-scope items not implemented (no auth, no DB, no bbox overlays) ✓
- §8 Open risks acknowledged (text-length hint in Task 12) ✓

**Placeholder scan:** No "TBD" / "implement later" left. All code blocks complete and runnable.

**Type consistency:**
- Backend `FieldDef` (frozen dataclass) used identically across schema/merge/ops/routes.
- Frontend `FieldDef` interface matches the JSON shape returned by `asdict(FieldDef)`.
- `PatchOp` discriminated union in `frontend/src/types.ts` matches Pydantic `PatchOp` model in `backend/app/routes.py` (op/field/value/index, value/index optional).
- Store method `applyMergedValues` cast as `Record<string, string | string[]>` aligns with backend `/extract-page` response.
