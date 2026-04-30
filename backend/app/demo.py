"""Demo session loader.

Materialises a fresh `SessionState` from the canonical JSON + bundled PDF so the
/demo route always serves identical extraction results without calling a model.
Each visit gets its own session id, so the customer can edit/add/delete fields
without affecting other viewers.
"""

from __future__ import annotations

import json
from pathlib import Path

from app.pdf_renderer import page_count, render_page_png
from app.schema import FieldDef
from app.session_store import SessionState, store

_APP_DIR = Path(__file__).resolve().parent
DEMO_PDF_PATH = _APP_DIR / "demo_assets" / "EC_1105-2-6_19730309.pdf"
DEMO_JSON_PATH = _APP_DIR / "demo_data.json"


def _load_payload() -> dict:
    return json.loads(DEMO_JSON_PATH.read_text())


def create_demo_session() -> tuple[str, SessionState]:
    """Build a fresh demo session and register it in the in-memory store."""
    payload = _load_payload()
    pdf_bytes = DEMO_PDF_PATH.read_bytes()
    n_pages = page_count(pdf_bytes)
    page_images = [render_page_png(pdf_bytes, i) for i in range(n_pages)]

    schema = [FieldDef(**f) for f in payload["schema"]]
    values = {
        k: (list(v) if isinstance(v, list) else v) for k, v in payload["values"].items()
    }
    original = {
        k: (list(v) if isinstance(v, list) else v) for k, v in payload["values"].items()
    }
    citations = {k: dict(v) for k, v in payload.get("citations", {}).items()}
    confidences = {k: float(v) for k, v in payload.get("confidences", {}).items()}

    state = SessionState(
        pdf_bytes=pdf_bytes,
        page_images=page_images,
        schema=schema,
        values=values,
        original_extracted=original,
        extraction_errors=list(payload.get("extraction_errors", [])),
        citations=citations,
        confidences=confidences,
    )
    sid = store.create(state)
    return sid, state
