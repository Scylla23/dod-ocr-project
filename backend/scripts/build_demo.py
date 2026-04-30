"""One-shot extractor that produces the static demo JSON.

Run: `uv run python scripts/build_demo.py` from backend/.

Reads the bundled demo PDF, runs the configured provider against every page,
merges results, locates evidence citations, and writes the canonical
`app/demo_data.json` consumed by the /demo route at runtime.
"""

from __future__ import annotations

import asyncio
import json
import sys
from dataclasses import asdict
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
load_dotenv(ROOT / ".env")

from app import extractor  # noqa: E402
from app.citations import locate_quotes  # noqa: E402
from app.merge import merge_page_results  # noqa: E402
from app.pdf_renderer import page_count, render_page_png  # noqa: E402
from app.schema import DEFAULT_SCHEMA, EVIDENCE_KEY  # noqa: E402

PDF_PATH = ROOT / "app" / "demo_assets" / "EC_1105-2-6_19730309.pdf"
OUT_PATH = ROOT / "app" / "demo_data.json"


def _split_evidence(result: dict | None) -> tuple[dict | None, dict[str, str]]:
    if not isinstance(result, dict):
        return result, {}
    evidence = result.pop(EVIDENCE_KEY, None)
    if not isinstance(evidence, dict):
        return result, {}
    quotes = {k: v for k, v in evidence.items() if isinstance(v, str) and v.strip()}
    return result, quotes


async def main() -> None:
    pdf_bytes = PDF_PATH.read_bytes()
    n_pages = page_count(pdf_bytes)
    print(f"PDF: {PDF_PATH.name} ({n_pages} pages, {len(pdf_bytes)} bytes)")

    schema = list(DEFAULT_SCHEMA)
    page_images = [render_page_png(pdf_bytes, i) for i in range(n_pages)]

    print(f"Extracting {n_pages} pages...")
    raw_results = await asyncio.gather(
        *(extractor.extract_page(img, schema) for img in page_images)
    )

    per_page_results: list[dict | None] = []
    per_page_quotes: list[dict[str, str]] = []
    for r in raw_results:
        v, q = _split_evidence(r)
        per_page_results.append(v)
        per_page_quotes.append(q)

    extraction_errors = [i + 1 for i, r in enumerate(per_page_results) if r is None]
    values, _self_confidences = merge_page_results(per_page_results, schema)

    citations: dict[str, dict] = {}
    for page_idx, quotes in enumerate(per_page_quotes):
        if not quotes:
            continue
        remaining = {k: v for k, v in quotes.items() if k not in citations}
        if not remaining:
            continue
        new_cits = locate_quotes(pdf_bytes, remaining, preferred_page_index=page_idx)
        for fname, cit in new_cits.items():
            citations.setdefault(fname, cit)

    payload = {
        "pdf_filename": PDF_PATH.name,
        "page_count": n_pages,
        "schema": [asdict(f) for f in schema],
        "values": values,
        "extraction_errors": extraction_errors,
        "citations": citations,
    }
    OUT_PATH.write_text(json.dumps(payload, indent=2, ensure_ascii=False))
    print(f"Wrote {OUT_PATH} ({OUT_PATH.stat().st_size} bytes)")
    print(f"Extracted fields: {list(values.keys())}")
    print(f"Citations: {len(citations)} fields")
    if extraction_errors:
        print(f"!! Extraction errors on pages: {extraction_errors}")


if __name__ == "__main__":
    asyncio.run(main())
