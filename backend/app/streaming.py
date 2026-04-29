"""Streaming extraction with partial-JSON snapshots.

Emits fields as the LLM produces them so the UI fills in live instead of
waiting for the full tool_use to arrive.
"""

from __future__ import annotations

import asyncio
import base64
import json
import logging
import os
from typing import Any, AsyncIterator

from app.providers import get_provider
from app.providers.anthropic_provider import AnthropicProvider
from app.providers.openai_provider import OpenAIProvider
from app.schema import EVIDENCE_KEY, EVIDENCE_PROMPT, FieldDef, build_tool_input_schema

logger = logging.getLogger(__name__)


def parse_partial_json(s: str) -> dict | None:
    """Best-effort parse of an incomplete JSON object string.

    Truncates at the last safe top-level comma, closes outstanding braces and
    brackets, and parses. Returns None when nothing parseable yet.
    """
    s = s.strip()
    if not s.startswith("{"):
        return None
    try:
        return json.loads(s)
    except json.JSONDecodeError:
        pass

    depth_brace = 0
    depth_brack = 0
    in_string = False
    escape = False
    last_top_comma = -1  # position of last top-level comma at depth 1
    for i, ch in enumerate(s):
        if escape:
            escape = False
            continue
        if ch == "\\" and in_string:
            escape = True
            continue
        if ch == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if ch == "{":
            depth_brace += 1
        elif ch == "}":
            depth_brace -= 1
        elif ch == "[":
            depth_brack += 1
        elif ch == "]":
            depth_brack -= 1
        elif ch == "," and depth_brace == 1 and depth_brack == 0:
            last_top_comma = i

    if last_top_comma < 0:
        return None
    truncated = s[:last_top_comma].rstrip()
    # Re-count brace/bracket depth on truncated
    db, dk, ins, esc = 0, 0, False, False
    for ch in truncated:
        if esc:
            esc = False
            continue
        if ch == "\\" and ins:
            esc = True
            continue
        if ch == '"':
            ins = not ins
            continue
        if ins:
            continue
        if ch == "{":
            db += 1
        elif ch == "}":
            db -= 1
        elif ch == "[":
            dk += 1
        elif ch == "]":
            dk -= 1
    closed = truncated + ("]" * dk) + ("}" * db)
    try:
        result = json.loads(closed)
        if isinstance(result, dict):
            return result
    except json.JSONDecodeError:
        return None
    return None


def _value_is_complete(value: Any) -> bool:
    """A complete value is anything except an unfinished container.

    Since we truncate at top-level commas, any value we can pull from the parse
    is by definition complete (the next char at depth 1 was a comma).
    """
    return value is not None or value is None  # always true once parsed


_ANTHROPIC_TOOL_NAME = "record_extracted_fields"
_DEFAULT_ANTHROPIC_MODEL = "claude-sonnet-4-5"
_STREAM_TIMEOUT_S = 90.0


async def stream_extract(
    image_png: bytes,
    schema: list[FieldDef],
    provider_name: str | None = None,
) -> AsyncIterator[dict]:
    """Yield streaming events:

    - {"type":"field", "name": str, "value": str | list[str]}
    - {"type":"final", "values": dict, "quotes": dict[str,str]}
    - {"type":"error", "message": str}
    """
    impl = get_provider(provider_name)
    if isinstance(impl, AnthropicProvider):
        async for ev in _stream_anthropic(impl, image_png, schema):
            yield ev
        return
    # Fallback for OpenAI / others: do non-streaming and emit all at once.
    try:
        full = await asyncio.wait_for(
            impl.extract(image_png, schema), timeout=_STREAM_TIMEOUT_S
        )
    except Exception as e:  # noqa: BLE001
        yield {"type": "error", "message": str(e)}
        return
    if not isinstance(full, dict):
        yield {"type": "error", "message": "extraction failed"}
        return
    quotes_raw = full.pop(EVIDENCE_KEY, None)
    quotes = (
        {k: v for k, v in quotes_raw.items() if isinstance(v, str) and v.strip()}
        if isinstance(quotes_raw, dict)
        else {}
    )
    schema_names = {f.name for f in schema}
    for k, v in full.items():
        if k in schema_names and v is not None:
            yield {"type": "field", "name": k, "value": v}
    yield {"type": "final", "values": full, "quotes": quotes}


async def _stream_anthropic(
    provider: AnthropicProvider,
    image_png: bytes,
    schema: list[FieldDef],
) -> AsyncIterator[dict]:
    client = provider._get_client()  # type: ignore[attr-defined]
    model = os.environ.get("ANTHROPIC_MODEL", _DEFAULT_ANTHROPIC_MODEL)
    image_b64 = base64.standard_b64encode(image_png).decode("ascii")
    tool: dict[str, Any] = {
        "name": _ANTHROPIC_TOOL_NAME,
        "description": (
            "Record fields extracted from this PDF page. "
            "Use null for any field not visible on this page; "
            "do not invent or infer values that are not present."
        ),
        "input_schema": build_tool_input_schema(schema, include_evidence=True),
    }

    schema_names = {f.name for f in schema}
    accumulated = ""
    emitted_fields: set[str] = set()
    final_input: dict | None = None

    try:
        async with client.messages.stream(
            model=model,
            max_tokens=4096,
            tools=[tool],
            tool_choice={"type": "tool", "name": _ANTHROPIC_TOOL_NAME},
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {"type": "base64", "media_type": "image/png", "data": image_b64},
                        },
                        {
                            "type": "text",
                            "text": (
                                "Extract the listed fields from this PDF page. "
                                "Return null for any field not present on this page."
                                + EVIDENCE_PROMPT
                            ),
                        },
                    ],
                }
            ],
        ) as stream_ctx:
            async for event in stream_ctx:
                etype = getattr(event, "type", None)
                if etype == "content_block_delta":
                    delta = getattr(event, "delta", None)
                    if delta is None:
                        continue
                    if getattr(delta, "type", None) == "input_json_delta":
                        chunk = getattr(delta, "partial_json", "") or ""
                        if not chunk:
                            continue
                        accumulated += chunk
                        snapshot = parse_partial_json(accumulated)
                        if not snapshot:
                            continue
                        for k, v in snapshot.items():
                            if k in emitted_fields:
                                continue
                            if k not in schema_names:
                                continue
                            # Skip empty/null values until they're populated
                            if v is None:
                                continue
                            if isinstance(v, list) and not v:
                                continue
                            if isinstance(v, str) and not v.strip():
                                continue
                            emitted_fields.add(k)
                            yield {"type": "field", "name": k, "value": v}

            # Pull final input from the completed message.
            try:
                final_msg = await stream_ctx.get_final_message()
                for block in final_msg.content:
                    if getattr(block, "type", None) == "tool_use" and getattr(block, "name", None) == _ANTHROPIC_TOOL_NAME:
                        inp = getattr(block, "input", None)
                        if isinstance(inp, dict):
                            final_input = inp
                            break
            except Exception as e:  # noqa: BLE001
                logger.warning("anthropic stream final fetch failed: %s", e)

    except Exception as e:  # noqa: BLE001
        logger.warning("anthropic stream failed: %s", e)
        yield {"type": "error", "message": str(e)}
        return

    if final_input is None:
        # No tool_use block returned at all.
        yield {"type": "error", "message": "no tool result"}
        return

    quotes_raw = final_input.pop(EVIDENCE_KEY, None)
    quotes = (
        {k: v for k, v in quotes_raw.items() if isinstance(v, str) and v.strip()}
        if isinstance(quotes_raw, dict)
        else {}
    )
    # Emit any remaining fields that streamed too late to detect (or were last).
    for k, v in final_input.items():
        if k in emitted_fields or k not in schema_names:
            continue
        if v is None:
            continue
        if isinstance(v, list) and not v:
            continue
        if isinstance(v, str) and not v.strip():
            continue
        yield {"type": "field", "name": k, "value": v}

    yield {"type": "final", "values": final_input, "quotes": quotes}


__all__ = ["stream_extract", "parse_partial_json"]


# Re-export for type-checkers that don't see OpenAIProvider
_ = OpenAIProvider
