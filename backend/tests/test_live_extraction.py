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
