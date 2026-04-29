# PDF Data Extraction & Verification Tool — Design

**Status**: Draft for review
**Date**: 2026-04-29
**Scope**: Single-session prototype. No auth, no persistence, no multi-user.

## 1. Goal

A web tool where a user uploads a PDF, sees it page-by-page on the left, sees Claude-extracted structured data on the right, and can manually correct extracted values by selecting text in the PDF and assigning it to a field.

## 2. Tech Stack

- Backend: Python 3.11+, FastAPI, `uvicorn`
- Frontend: React 18 + Vite, `react-pdf` (pdf.js wrapper)
- PDF rendering (server): PyMuPDF (`fitz`)
- LLM: Anthropic Claude Vision via `anthropic.AsyncAnthropic`, model `claude-sonnet-4-5`
- Structured output: Anthropic tool-use with JSON schema mirroring the active field schema
- State: in-memory dict on the FastAPI process; lost on restart

## 3. Default Schema

Hybrid: small generic core + USACE-flavored extras pre-loaded but removable.

```
GENERIC CORE  (5 fields, scalar string, not removable)
  title              one-paragraph human-readable title
  document_type      e.g. "Engineering Manual" / "Engineering Circular" / "Engineering Technical Letter"
  document_number    e.g. "EM 1110-2-400"
  effective_date     ISO yyyy-mm-dd if parseable, else as-printed
  summary            one-paragraph abstract

USACE EXTRAS  (4 fields, scalar string, removable)
  proponent_office       e.g. "ENGCW-EM"
  issuing_authority      e.g. "Office of the Chief of Engineers"
  applicability          applicability statement
  superseded_documents   raw text of supersession statement

LIST FIELDS  (1, append-style, removable)
  references             list[string], referenced doc numbers / standards
```

Total: 10 fields. Custom fields added during a session are always `string` scalar, removable, with no `original_extracted` value.

## 4. Architecture

```
Frontend (Vite + React)                        Backend (FastAPI)
┌──────────────┐                              ┌──────────────────────┐
│ Upload view  │  POST /upload (multipart)    │ PdfRenderer (PyMuPDF)│
└──────────────┘ ───────────────────────────► │ Extractor (Anthropic)│
┌──────────────┐                              │ SessionStore (dict)  │
│ Workspace    │  GET /sessions/{id}/pdf      └──────────────────────┘
│  PdfPane     │  PATCH /sessions/{id}/values
│  FieldsPane  │  POST /sessions/{id}/fields
│              │  POST /sessions/{id}/extract-page
└──────────────┘
```

`react-pdf` renders pages client-side from the PDF blob fetched via `GET /sessions/{id}/pdf`. The server-side rasterized PNGs are kept only for sending to Claude Vision; they are not served to the frontend.

### 4.1 Components

**Backend modules**
- `pdf_renderer.py` — PyMuPDF wrapper. `render_page(pdf_bytes, page_index, max_edge=1568) -> bytes` returns PNG. `text_length(pdf_bytes, page_index) -> int` for the "no selectable text" hint.
- `extractor.py` — Anthropic client wrapper. `extract_page(image_bytes, schema) -> dict` uses tool-use with the JSON schema derived from the active field schema. Returns a partial value dict (nulls for fields not present on the page).
- `merge.py` — `merge_page_results(per_page_results: list[dict], schema) -> dict`. Scalars: first non-null wins (page-1 priority). Lists: concat then dedupe preserving order.
- `session_store.py` — in-memory `dict[session_id, SessionState]`. `SessionState` is a `dataclass`. No locking; FastAPI workers single-process for the prototype.
- `ops.py` — `apply_op(state, op)` for PATCH operations: `set`, `append`, `remove`, `revert`.
- `app.py` — FastAPI routes wiring the modules together.

**Frontend modules**
- `App.tsx` — routes between Upload and Workspace based on whether a session_id exists.
- `Upload.tsx` — drop zone + progress spinner during upload/extract.
- `Workspace.tsx` — two-pane layout, pagination controls, page input, re-extract button.
- `PdfPane.tsx` — `react-pdf` `Document` + `Page`. Wraps the page in a div that listens for `mouseup` to capture selections.
- `SelectionPopover.tsx` — anchored popover with field dropdown + "Create new field…".
- `FieldsPane.tsx` — renders fields from the schema. Scalar = text input. List = chip row with × per chip. Each field has a revert button when `value !== original_extracted[field]`.
- `AddFieldModal.tsx` — name input with validation.
- `store.ts` — Zustand (or React context) holding `{ sessionId, schema, values, originalExtracted, currentPage, pageCount }` and reducers for ops.

### 4.2 Data flow

**Upload**
1. `POST /upload` (multipart). Server: store bytes, render every page to PNG bytes (kept in memory), generate session_id.
2. Run `extract_page` on pages 1–3 in parallel via `asyncio.gather`. Each call passes the active schema as a tool definition.
3. Merge the per-page partial results: scalars = first non-null with page-1 priority; lists = concat-dedupe.
4. Snapshot merged values into `original_extracted` (frozen). This is what revert restores to.
5. Response: `{ session_id, page_count, schema, values, original_extracted, extraction_errors }`.

**Workspace interactions**

| User action | Frontend | Backend |
| --- | --- | --- |
| Paginate | render page N via react-pdf using PDF blob URL | none |
| Select text → "Assign to existing scalar field" | popover → PATCH | `apply_op({op:"set", field, value})` |
| Select text → "Assign to existing list field" | popover → PATCH | `apply_op({op:"append", field, value})` |
| Select text → "Create new field…" | modal → POST `/fields` then PATCH | add field to schema, then set value |
| × on list chip | PATCH | `apply_op({op:"remove", field, index})` |
| Revert button | PATCH | `apply_op({op:"revert", field})` |
| "Re-extract this page" | POST `/extract-page` | run extractor on page N, merge into current values: scalars only fill if currently empty; lists append-dedupe; do NOT update `original_extracted` |

### 4.3 Session state shape (server)

```python
@dataclass
class FieldDef:
    name: str
    type: Literal["string", "list[string]"]
    removable: bool

@dataclass
class SessionState:
    pdf_bytes: bytes
    page_images: list[bytes]   # PNG, indexed by page
    schema: list[FieldDef]
    values: dict[str, str | list[str]]
    original_extracted: dict[str, str | list[str]]
```

### 4.4 API

| Method & path | Body | Response |
| --- | --- | --- |
| `POST /upload` | multipart `file=<pdf>` | `{session_id, page_count, schema, values, original_extracted, extraction_errors: list[int]}` |
| `GET /sessions/{id}/pdf` | — | original PDF bytes (`application/pdf`) — consumed by `react-pdf` |
| `PATCH /sessions/{id}/values` | `{op, field, value?, index?}` | updated `values[field]` |
| `POST /sessions/{id}/fields` | `{name}` | updated `schema` (new field appended, type=string, removable=true) |
| `DELETE /sessions/{id}/fields/{name}` | — | updated `schema, values, original_extracted` |
| `POST /sessions/{id}/extract-page` | `{page: int}` | merged `values` |

`extraction_errors` is the list of 1-indexed page numbers whose extraction failed during upload; the frontend renders a banner and offers per-page retry.

### 4.5 Vision call shape

Tool-use with one tool whose `input_schema` is built from the active `schema`:

```json
{
  "name": "record_extracted_fields",
  "description": "Record fields extracted from this PDF page. Use null for any field not present on this page.",
  "input_schema": {
    "type": "object",
    "properties": {
      "title": {"type": ["string","null"]},
      "document_number": {"type": ["string","null"]},
      "...": "...",
      "references": {"type":["array","null"], "items":{"type":"string"}}
    },
    "required": ["title","document_type","document_number","effective_date","summary",
                "proponent_office","issuing_authority","applicability",
                "superseded_documents","references"]
  }
}
```

Image is sent as base64 PNG (after downscale to ≤1568 longest edge). `tool_choice` forces the tool, so the model must call it; the call's `input` is the structured result.

## 5. Error Handling & Edge Cases

**Upload**
- Non-PDF MIME → 400.
- PyMuPDF parse failure → 400 "Could not open PDF".
- Empty PDF (0 pages) → 400.
- File >50MB → 413.

**Extraction**
- Per-page timeout: 60s. Total `gather` budget: 90s.
- Per-page Anthropic error → that page skipped; included in `extraction_errors`. Other pages still merge.
- Tool-call missing or input fails schema validation → treat as failed page.
- All 3 pages fail → upload still succeeds with empty values; banner with retry buttons.

**Vision sizing**
- Each PNG downscaled so its longest edge ≤ 1568px before base64 encoding.
- Render DPI starts at 150; if downscale would still exceed 5MB encoded, drop DPI to 110.

**Selection**
- Whitespace-only selection → popover suppressed.
- Selection range that escapes the current page wrapper → ignored.
- Page text length < 20 chars → show inline hint "this page has no selectable text".

**Schema**
- Duplicate field name (case-insensitive) → 409.
- Empty / >40 chars / non-printable name → 400.
- Removing a field with a value → frontend confirm modal; backend deletes the field and its value.
- Generic-core fields have `removable=false`; backend rejects DELETE on them with 400.

**Session**
- Unknown session_id → 404; frontend redirects to upload.
- Server restart drops all state → next call 404 → redirect.

**Revert**
- Field with no entry in `original_extracted` (custom field, or extraction returned null/empty list) → revert sets to empty string / empty list.
- Frontend hides the revert button when `value` already equals `original_extracted[field]`.

## 6. Testing Strategy

**Backend (pytest)**
- Unit: `pdf_renderer.render_page` (returns PNG, dimensions cap respected), `merge_page_results` (scalars first-non-null page-1 priority, list concat-dedupe, nulls ignored), `apply_op` (all four ops including index-out-of-range), schema mutation (add/dup/empty/remove-non-removable).
- Integration with mocked Anthropic client: `/upload` end-to-end (session created, values merged, `original_extracted` frozen); `/extract-page` re-merge (scalars only fill if empty, lists append-dedupe, no change to `original_extracted`).
- Live test (marker `live`, skipped by default): real Claude call on `EC 1105-2-2_19720615.pdf`; asserts `document_number` is non-empty.

**Frontend (Vitest + React Testing Library)**
- Reducer: assign-set, assign-append, remove-from-list, revert, add-field.
- Popover open/close on mocked selection events.
- AddField modal validation.
- Skip react-pdf rendering tests in jsdom.

**Manual checklist**
1. Upload each of the 5 sample PDFs. Each completes within 30s. At least 4 of 5 yield non-empty `document_number`.
2. On page 1 of `EC 1105-2-2`, select "EC 1105-2-2" → assign to `document_number`. Revert → Claude's original returns.
3. Add custom field `keywords`. Append 3 selections. Remove the middle one.
4. On page 3 of the 99-page ETL, click "Re-extract this page". Watch list fields grow without overwriting scalars.
5. Refresh → upload screen (state lost, expected).

**Out of scope**: load testing, non-Chrome browsers, accessibility audit, security review.

## 7. Out of Scope (explicit)

- Authentication
- Saving / loading sessions
- Multi-user support
- Bounding-box overlays on the PDF (native selection only)
- Production deployment concerns
- Custom field types beyond string (numbers/dates stored as strings)
- Multi-PDF library / session list

## 8. Open Risks

- USACE samples have a text layer; an image-only scanned PDF would degrade to "look-only" since selection wouldn't yield text. Hint shown but not solved.
- PyMuPDF is AGPL — fine for a prototype, flag if this work moves toward a commercial product.
- 60s per-page timeout could be tight for very dense pages with many list items; revisit if the manual checklist hits it.
