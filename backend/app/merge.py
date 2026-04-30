from __future__ import annotations

from app.schema import FieldDef


def merge_page_results(
    page_results: list[dict | None],
    schema: list[FieldDef],
    page_confidences: list[dict | None] | None = None,
) -> tuple[dict[str, str | list[str]], dict[str, float]]:
    """Merge per-page partial results into a single doc-level value dict.

    Scalars: first non-null/non-empty value, page-1 priority.
    Lists: concat across pages, dedupe preserving first-seen order.
    Missing or None per-page result is skipped.

    Returns (values, raw_self_confidences). For scalars the confidence comes
    from the same page that supplied the chosen value. For lists, the max
    self-confidence across pages that contributed any item is used. Fields
    with no model self-confidence are absent from the dict.
    """
    out: dict[str, str | list[str]] = {}
    confs: dict[str, float] = {}
    for f in schema:
        if f.type == "string":
            value = ""
            picked_page: int | None = None
            for i, pr in enumerate(page_results):
                if not pr:
                    continue
                v = pr.get(f.name)
                if isinstance(v, str) and v.strip():
                    value = v
                    picked_page = i
                    break
            out[f.name] = value
            if picked_page is not None and page_confidences:
                pc = page_confidences[picked_page] if picked_page < len(page_confidences) else None
                if isinstance(pc, dict):
                    c = pc.get(f.name)
                    if isinstance(c, (int, float)) and not isinstance(c, bool):
                        confs[f.name] = float(c)
        else:  # list[string]
            seen: set[str] = set()
            collected: list[str] = []
            contributing_pages: list[int] = []
            for i, pr in enumerate(page_results):
                if not pr:
                    continue
                v = pr.get(f.name)
                if not isinstance(v, list):
                    continue
                added_any = False
                for item in v:
                    if isinstance(item, str) and item not in seen:
                        seen.add(item)
                        collected.append(item)
                        added_any = True
                if added_any:
                    contributing_pages.append(i)
            out[f.name] = collected
            if contributing_pages and page_confidences:
                vals: list[float] = []
                for i in contributing_pages:
                    pc = page_confidences[i] if i < len(page_confidences) else None
                    if isinstance(pc, dict):
                        c = pc.get(f.name)
                        if isinstance(c, (int, float)) and not isinstance(c, bool):
                            vals.append(float(c))
                if vals:
                    confs[f.name] = max(vals)
    return out, confs
