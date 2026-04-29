from __future__ import annotations

import asyncio
import base64
import logging
import os
from typing import Any

from anthropic import AsyncAnthropic

from app.schema import FieldDef, build_tool_input_schema

logger = logging.getLogger(__name__)

MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-5")
PER_PAGE_TIMEOUT_S = 60.0

_TOOL_NAME = "record_extracted_fields"


def _tool_definition(schema: list[FieldDef]) -> dict[str, Any]:
    return {
        "name": _TOOL_NAME,
        "description": (
            "Record fields extracted from this PDF page. "
            "Use null for any field not visible on this page; "
            "do not invent or infer values that are not present."
        ),
        "input_schema": build_tool_input_schema(schema),
    }


def _client() -> AsyncAnthropic:
    return AsyncAnthropic()


async def extract_page(
    image_png: bytes,
    schema: list[FieldDef],
    *,
    client: AsyncAnthropic | None = None,
) -> dict | None:
    """Call Claude Vision with a tool definition derived from the schema.

    Returns the tool's input dict on success, or None on any failure
    (timeout, API error, no tool_use block, etc.).
    """
    cli = client or _client()
    image_b64 = base64.standard_b64encode(image_png).decode("ascii")
    tool = _tool_definition(schema)
    try:
        response = await asyncio.wait_for(
            cli.messages.create(
                model=MODEL,
                max_tokens=4096,
                tools=[tool],
                tool_choice={"type": "tool", "name": _TOOL_NAME},
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "image",
                                "source": {
                                    "type": "base64",
                                    "media_type": "image/png",
                                    "data": image_b64,
                                },
                            },
                            {
                                "type": "text",
                                "text": (
                                    "Extract the listed fields from this PDF page. "
                                    "Return null for any field not present on this page."
                                ),
                            },
                        ],
                    }
                ],
            ),
            timeout=PER_PAGE_TIMEOUT_S,
        )
    except (asyncio.TimeoutError, Exception) as e:  # noqa: BLE001
        logger.warning("extract_page failed: %s", e)
        return None

    for block in response.content:
        if getattr(block, "type", None) == "tool_use" and getattr(block, "name", None) == _TOOL_NAME:
            inp = getattr(block, "input", None)
            if isinstance(inp, dict):
                return inp
    return None
