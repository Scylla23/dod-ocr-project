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
