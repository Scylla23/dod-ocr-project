from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import asdict
from typing import Any

from fastapi import APIRouter, File, Form, HTTPException, Request, Response, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app import extractor
from app.citations import locate_quote, locate_quotes  # noqa: F401
from app.merge import merge_page_results
from app.ops import OpError, apply_op
from app.pdf_renderer import (
    PdfOpenError,
    page_count,
    render_page_png,
    text_length,
)
from app.providers import DEFAULT_PROVIDER_NAME, PROVIDERS, list_providers
from app.schema import (
    DEFAULT_SCHEMA,
    EVIDENCE_KEY,
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


@router.get("/providers")
def get_providers():
    return {"providers": list_providers(), "default": DEFAULT_PROVIDER_NAME}


@router.post("/demo/session")
def create_demo():
    """Return a fresh, pre-extracted demo session loaded from bundled JSON."""
    from app.demo import create_demo_session  # local import to avoid cycle at start

    sid, state = create_demo_session()
    return _serialize_session(sid, state)


def _serialize_session(sid: str, state: SessionState) -> dict[str, Any]:
    return {
        "session_id": sid,
        "page_count": len(state.page_images),
        "schema": [asdict(f) for f in state.schema],
        "values": state.values,
        "original_extracted": state.original_extracted,
        "extraction_errors": state.extraction_errors,
        "citations": state.citations,
    }


def _locate_single(pdf_bytes: bytes, quote: str, preferred_page_index: int) -> dict | None:
    return locate_quote(pdf_bytes, quote, preferred_page_index=preferred_page_index)


def _locate_quotes_for_page(pdf_bytes: bytes, quotes: dict[str, str], preferred_page_index: int) -> dict[str, dict]:
    return locate_quotes(pdf_bytes, quotes, preferred_page_index=preferred_page_index)


def _split_evidence(result: dict | None) -> tuple[dict | None, dict[str, str]]:
    """Pop _evidence quotes off the model result. Tolerant of missing / malformed."""
    if not isinstance(result, dict):
        return result, {}
    evidence = result.pop(EVIDENCE_KEY, None)
    if not isinstance(evidence, dict):
        return result, {}
    quotes = {k: v for k, v in evidence.items() if isinstance(v, str) and v.strip()}
    return result, quotes


@router.post("/upload")
async def upload(
    request: Request,
    file: UploadFile = File(...),
    provider: str | None = Form(default=None),
):
    if provider is not None and provider not in PROVIDERS:
        raise HTTPException(400, f"unknown provider '{provider}'")
    content_length = request.headers.get("content-length")
    if content_length is not None:
        try:
            size = int(content_length)
        except ValueError:
            size = 0
        if size > MAX_UPLOAD_BYTES:
            raise HTTPException(413, f"file exceeds {MAX_UPLOAD_BYTES} bytes")
    if file.content_type not in ("application/pdf", "application/x-pdf"):
        raise HTTPException(400, "file must be a PDF")
    pdf_bytes = await file.read()
    if len(pdf_bytes) == 0:
        raise HTTPException(400, "empty file")
    if len(pdf_bytes) > MAX_UPLOAD_BYTES:
        raise HTTPException(413, f"file exceeds {MAX_UPLOAD_BYTES} bytes")

    try:
        n_pages = await asyncio.to_thread(page_count, pdf_bytes)
    except PdfOpenError as e:
        raise HTTPException(400, f"could not open PDF: {e}") from None
    if n_pages == 0:
        raise HTTPException(400, "PDF has zero pages")

    page_images = await asyncio.to_thread(
        lambda: [render_page_png(pdf_bytes, i) for i in range(n_pages)]
    )
    schema = list(DEFAULT_SCHEMA)

    pages_to_extract = list(range(min(AUTO_EXTRACT_PAGES, n_pages)))
    try:
        per_page_results_raw = await asyncio.wait_for(
            asyncio.gather(*(extractor.extract_page(page_images[i], schema, provider_name=provider) for i in pages_to_extract)),
            timeout=TOTAL_EXTRACT_TIMEOUT_S,
        )
    except asyncio.TimeoutError:
        per_page_results_raw = [None] * len(pages_to_extract)

    # Split evidence quotes off each page result before merging.
    per_page_results: list[dict | None] = []
    per_page_quotes: list[dict[str, str]] = []
    for r in per_page_results_raw:
        v, q = _split_evidence(r)
        per_page_results.append(v)
        per_page_quotes.append(q)

    extraction_errors = [pages_to_extract[i] + 1 for i, r in enumerate(per_page_results) if r is None]
    values = merge_page_results(per_page_results, schema)
    original_extracted = {k: (list(v) if isinstance(v, list) else v) for k, v in values.items()}

    # Build citations page-by-page (fields not yet located fall through to next page).
    citations: dict[str, dict] = {}
    for page_idx, quotes in zip(pages_to_extract, per_page_quotes):
        if not quotes:
            continue
        remaining = {k: v for k, v in quotes.items() if k not in citations}
        if not remaining:
            continue
        new_cits = await asyncio.to_thread(
            _locate_quotes_for_page, pdf_bytes, remaining, page_idx
        )
        for fname, cit in new_cits.items():
            citations.setdefault(fname, cit)

    state = SessionState(
        pdf_bytes=pdf_bytes,
        page_images=page_images,
        schema=schema,
        values=values,
        original_extracted=original_extracted,
        extraction_errors=extraction_errors,
        provider_name=provider,
        citations=citations,
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
async def patch_values(sid: str, op: PatchOp):
    try:
        state = store.get(sid)
    except KeyError:
        raise HTTPException(404, "unknown session") from None
    async with state.lock:
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
async def add_field(sid: str, req: AddFieldRequest):
    try:
        state = store.get(sid)
    except KeyError:
        raise HTTPException(404, "unknown session") from None
    try:
        validate_field_name(req.name)
    except ValueError as e:
        raise HTTPException(400, str(e)) from None
    async with state.lock:
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
async def delete_field(sid: str, name: str):
    try:
        state = store.get(sid)
    except KeyError:
        raise HTTPException(404, "unknown session") from None
    async with state.lock:
        try:
            new_schema = remove_field(state.schema, name)
        except ValueError as e:
            raise HTTPException(400, str(e)) from None
        state.schema = new_schema
        state.values.pop(name, None)
        state.original_extracted.pop(name, None)
        state.citations.pop(name, None)
    return {"schema": [asdict(f) for f in state.schema]}


class ExtractPageRequest(BaseModel):
    page: int  # 1-indexed
    provider: str | None = None  # optional override; defaults to session's provider_name


@router.post("/sessions/{sid}/extract-page")
async def extract_single_page(sid: str, req: ExtractPageRequest):
    if req.provider is not None and req.provider not in PROVIDERS:
        raise HTTPException(400, f"unknown provider '{req.provider}'")
    try:
        state = store.get(sid)
    except KeyError:
        raise HTTPException(404, "unknown session") from None
    page_idx = req.page - 1
    if page_idx < 0 or page_idx >= len(state.page_images):
        raise HTTPException(400, "page out of range")
    provider_name = req.provider or state.provider_name
    raw = await extractor.extract_page(state.page_images[page_idx], state.schema, provider_name=provider_name)
    if raw is None:
        raise HTTPException(502, f"extraction failed for page {req.page}")
    result, quotes = _split_evidence(raw)
    # Re-merge: scalars only fill if currently empty; lists append-dedupe.
    async with state.lock:
        for f in state.schema:
            v = result.get(f.name) if result else None
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
        # Refresh citations for fields that produced new quotes on this page.
        if quotes:
            new_cits = await asyncio.to_thread(
                locate_quotes, state.pdf_bytes, quotes, preferred_page_index=page_idx
            )
            for fname, cit in new_cits.items():
                state.citations[fname] = cit
    return {"values": state.values, "citations": state.citations}


@router.get("/sessions/{sid}/extract-page/stream")
async def extract_page_stream(sid: str, page: int, provider: str | None = None):
    """SSE stream of extracted fields as the model produces them.

    Events:
      event: field    data: {"name": str, "value": str|list[str]}
      event: citations data: {field: {page, rects, quote}}
      event: done     data: {}
      event: error    data: {"message": str}
    """
    from app.streaming import stream_extract  # local import to avoid cycle

    if provider is not None and provider not in PROVIDERS:
        raise HTTPException(400, f"unknown provider '{provider}'")
    try:
        state = store.get(sid)
    except KeyError:
        raise HTTPException(404, "unknown session") from None
    page_idx = page - 1
    if page_idx < 0 or page_idx >= len(state.page_images):
        raise HTTPException(400, "page out of range")
    provider_name = provider or state.provider_name

    image = state.page_images[page_idx]
    schema_snapshot = list(state.schema)

    def fmt(event: str, data: Any) -> bytes:
        return f"event: {event}\ndata: {json.dumps(data)}\n\n".encode("utf-8")

    async def event_gen():
        merged_quotes: dict[str, str] = {}
        merged_values: dict[str, Any] = {}
        try:
            async for ev in stream_extract(image, schema_snapshot, provider_name):
                t = ev.get("type")
                if t == "field":
                    yield fmt("field", {"name": ev["name"], "value": ev["value"]})
                elif t == "final":
                    merged_values = ev.get("values", {}) or {}
                    merged_quotes = ev.get("quotes", {}) or {}
                elif t == "error":
                    yield fmt("error", {"message": ev.get("message", "error")})
                    return

            # Apply final values to session (re-merge semantics) and locate citations.
            new_cits: dict[str, dict] = {}
            if merged_quotes:
                new_cits = await asyncio.to_thread(
                    _locate_quotes_for_page,
                    state.pdf_bytes,
                    merged_quotes,
                    page_idx,
                )
            async with state.lock:
                for f in schema_snapshot:
                    v = merged_values.get(f.name)
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
                for fname, cit in new_cits.items():
                    state.citations[fname] = cit
            yield fmt("citations", new_cits)
            yield fmt("done", {})
        except Exception as e:  # noqa: BLE001
            yield fmt("error", {"message": str(e)})

    return StreamingResponse(
        event_gen(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


@router.get("/sessions/{sid}/page/{n}/text-length")
async def page_text_length(sid: str, n: int):
    """Used by frontend to show a 'no selectable text' hint."""
    try:
        state = store.get(sid)
    except KeyError:
        raise HTTPException(404, "unknown session") from None
    if n < 1 or n > len(state.page_images):
        raise HTTPException(400, "page out of range")
    return {"length": await asyncio.to_thread(text_length, state.pdf_bytes, n - 1)}
