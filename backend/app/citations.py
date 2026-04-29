from __future__ import annotations

import logging
import re
from typing import Iterable

import fitz  # PyMuPDF

logger = logging.getLogger(__name__)

# Citation = which page (1-indexed) and the highlight rectangles in normalized
# page-fraction coordinates: x, y, w, h all in [0,1] from top-left.
Citation = dict  # {"page": int, "rects": list[list[float]], "quote": str}

_MAX_QUOTE_CHARS = 240
_MIN_QUOTE_CHARS = 4


def _normalize_rects(rects: Iterable[fitz.Rect], page_rect: fitz.Rect) -> list[list[float]]:
    pw = max(page_rect.width, 1.0)
    ph = max(page_rect.height, 1.0)
    out: list[list[float]] = []
    for r in rects:
        x = (r.x0 - page_rect.x0) / pw
        y = (r.y0 - page_rect.y0) / ph
        w = (r.x1 - r.x0) / pw
        h = (r.y1 - r.y0) / ph
        out.append([round(x, 5), round(y, 5), round(w, 5), round(h, 5)])
    return out


def _try_search(page: fitz.Page, needle: str) -> list[fitz.Rect]:
    if not needle:
        return []
    try:
        return list(page.search_for(needle, quads=False))
    except Exception:  # noqa: BLE001
        return []


def _shrink_candidates(quote: str) -> list[str]:
    """Yield progressively shorter substrings of the quote to try when the full
    quote does not match (e.g. model added/dropped a word)."""
    q = quote.strip()
    if len(q) <= _MIN_QUOTE_CHARS:
        return [q] if q else []
    out = [q]
    # Trim trailing/leading non-word punctuation
    trimmed = re.sub(r"^[^\w]+|[^\w]+$", "", q)
    if trimmed and trimmed != q:
        out.append(trimmed)
    # Try the first half, last half, middle 60%
    n = len(q)
    if n > 24:
        out.append(q[: n // 2].strip())
        out.append(q[n // 2 :].strip())
        a, b = int(n * 0.2), int(n * 0.8)
        out.append(q[a:b].strip())
    # Token-based: longest run of 4+ word chars
    longest = max(re.findall(r"[\w][\w \-/]{6,}", q), key=len, default="")
    if longest and longest not in out:
        out.append(longest.strip())
    # Dedupe, keep order, drop too-short
    seen: set[str] = set()
    final: list[str] = []
    for c in out:
        if c and len(c) >= _MIN_QUOTE_CHARS and c not in seen:
            seen.add(c)
            final.append(c)
    return final


def locate_quote(
    pdf_bytes: bytes,
    quote: str | None,
    *,
    preferred_page_index: int | None = None,
) -> Citation | None:
    """Locate the first occurrence of `quote` in the PDF.

    Searches the preferred page first (if given), then iterates from page 0.
    Falls back to progressively shorter substrings of the quote so paraphrased
    or slightly off quotes still highlight. Returns None if nothing found.
    """
    if not quote or not quote.strip():
        return None
    raw = quote.strip()
    if len(raw) > _MAX_QUOTE_CHARS:
        raw = raw[:_MAX_QUOTE_CHARS]

    candidates = _shrink_candidates(raw)
    if not candidates:
        return None

    try:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    except Exception as e:  # noqa: BLE001
        logger.warning("citations: open failed: %s", e)
        return None

    try:
        n = doc.page_count
        order: list[int] = []
        if preferred_page_index is not None and 0 <= preferred_page_index < n:
            order.append(preferred_page_index)
        for i in range(n):
            if i not in order:
                order.append(i)

        for cand in candidates:
            for page_idx in order:
                page = doc[page_idx]
                hits = _try_search(page, cand)
                if hits:
                    return {
                        "page": page_idx + 1,
                        "rects": _normalize_rects(hits, page.rect),
                        "quote": cand,
                    }
        return None
    finally:
        doc.close()


def locate_quotes(
    pdf_bytes: bytes,
    quotes: dict[str, str | None] | None,
    *,
    preferred_page_index: int | None = None,
) -> dict[str, Citation]:
    """Locate citations for a {field_name: quote} dict. Skips empty quotes and misses."""
    if not quotes:
        return {}
    out: dict[str, Citation] = {}
    # Open once for efficiency.
    try:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    except Exception as e:  # noqa: BLE001
        logger.warning("citations: open failed: %s", e)
        return {}
    try:
        n = doc.page_count
        order: list[int] = []
        if preferred_page_index is not None and 0 <= preferred_page_index < n:
            order.append(preferred_page_index)
        for i in range(n):
            if i not in order:
                order.append(i)

        for field, q in quotes.items():
            if not isinstance(q, str) or not q.strip():
                continue
            raw = q.strip()
            if len(raw) > _MAX_QUOTE_CHARS:
                raw = raw[:_MAX_QUOTE_CHARS]
            cands = _shrink_candidates(raw)
            found = False
            for cand in cands:
                for page_idx in order:
                    page = doc[page_idx]
                    hits = _try_search(page, cand)
                    if hits:
                        out[field] = {
                            "page": page_idx + 1,
                            "rects": _normalize_rects(hits, page.rect),
                            "quote": cand,
                        }
                        found = True
                        break
                if found:
                    break
        return out
    finally:
        doc.close()
