from __future__ import annotations

import asyncio
import logging
from dataclasses import asdict
from typing import Any

from fastapi import APIRouter, File, HTTPException, Request, Response, UploadFile
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
async def upload(request: Request, file: UploadFile = File(...)):
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
    async with state.lock:
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
async def page_text_length(sid: str, n: int):
    """Used by frontend to show a 'no selectable text' hint."""
    try:
        state = store.get(sid)
    except KeyError:
        raise HTTPException(404, "unknown session") from None
    if n < 1 or n > len(state.page_images):
        raise HTTPException(400, "page out of range")
    return {"length": await asyncio.to_thread(text_length, state.pdf_bytes, n - 1)}
