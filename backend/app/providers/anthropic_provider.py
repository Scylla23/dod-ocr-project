from __future__ import annotations

import asyncio
import base64
import logging
import os
from typing import Any

from anthropic import AsyncAnthropic

from app.schema import EVIDENCE_PROMPT, FieldDef, build_tool_input_schema

logger = logging.getLogger(__name__)

_TOOL_NAME = "record_extracted_fields"
_DEFAULT_MODEL = "claude-sonnet-4-5"
_TIMEOUT_S = 60.0


class AnthropicProvider:
    name = "anthropic"

    def __init__(self) -> None:
        self._model = os.environ.get("ANTHROPIC_MODEL", _DEFAULT_MODEL)
        self._client: AsyncAnthropic | None = None

    def _get_client(self) -> AsyncAnthropic:
        if self._client is None:
            self._client = AsyncAnthropic()
        return self._client

    async def extract(self, image_png: bytes, schema: list[FieldDef]) -> dict | None:
        client = self._get_client()
        image_b64 = base64.standard_b64encode(image_png).decode("ascii")
        tool: dict[str, Any] = {
            "name": _TOOL_NAME,
            "description": (
                "Record fields extracted from this PDF page. "
                "Use null for any field not visible on this page; "
                "do not invent or infer values that are not present."
            ),
            "input_schema": build_tool_input_schema(schema, include_evidence=True),
        }
        try:
            response = await asyncio.wait_for(
                client.messages.create(
                    model=self._model,
                    max_tokens=4096,
                    tools=[tool],
                    tool_choice={"type": "tool", "name": _TOOL_NAME},
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
                ),
                timeout=_TIMEOUT_S,
            )
        except Exception as e:  # noqa: BLE001
            logger.warning("anthropic extract failed: %s", e)
            return None

        for block in response.content:
            if getattr(block, "type", None) == "tool_use" and getattr(block, "name", None) == _TOOL_NAME:
                inp = getattr(block, "input", None)
                if isinstance(inp, dict):
                    return inp
        return None
