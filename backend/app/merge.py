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
