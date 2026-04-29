from __future__ import annotations

import fitz  # PyMuPDF


class PdfOpenError(ValueError):
    pass


class PageIndexError(ValueError):
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
        if page_index < 0 or page_index >= doc.page_count:
            raise PageIndexError(
                f"page_index {page_index} out of range (0..{doc.page_count - 1})"
            )
        return len(doc[page_index].get_text().strip())
    finally:
        doc.close()


def render_page_png(pdf_bytes: bytes, page_index: int, *, dpi: int = 150, max_edge: int = 1568) -> bytes:
    """Render a page to PNG bytes, downscaled so the longest edge <= max_edge."""
    doc = _open(pdf_bytes)
    try:
        if page_index < 0 or page_index >= doc.page_count:
            raise PageIndexError(
                f"page_index {page_index} out of range (0..{doc.page_count - 1})"
            )
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
