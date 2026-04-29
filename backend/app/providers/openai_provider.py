from __future__ import annotations

import asyncio
import base64
import json
import logging
import os
from typing import Any

from openai import AsyncOpenAI

from app.schema import FieldDef

logger = logging.getLogger(__name__)

_DEFAULT_MODEL = "gpt-4o-mini"
_DEFAULT_BASE_URL = "https://api.openai.com/v1"
_TIMEOUT_S = 60.0


def _build_openai_schema(schema: list[FieldDef]) -> dict[str, Any]:
    """Build an OpenAI strict-mode JSON schema mirroring the field schema."""
    properties: dict[str, dict] = {}
    for f in schema:
        if f.type == "string":
            properties[f.name] = {"type": ["string", "null"]}
        else:
            properties[f.name] = {
                "type": ["array", "null"],
                "items": {"type": "string"},
            }
    return {
        "type": "object",
        "properties": properties,
        "required": [f.name for f in schema],
        "additionalProperties": False,
    }


class OpenAIProvider:
    name = "openai"

    def __init__(self) -> None:
        self._model = os.environ.get("OPENAI_MODEL", _DEFAULT_MODEL)
        self._base_url = os.environ.get("OPENAI_BASE_URL", _DEFAULT_BASE_URL)
        self._api_key = os.environ.get("OPENAI_API_KEY")
        self._client: AsyncOpenAI | None = None

    def _get_client(self) -> AsyncOpenAI:
        if self._client is None:
            self._client = AsyncOpenAI(api_key=self._api_key, base_url=self._base_url)
        return self._client

    async def extract(self, image_png: bytes, schema: list[FieldDef]) -> dict | None:
        client = self._get_client()
        image_b64 = base64.standard_b64encode(image_png).decode("ascii")
        json_schema = _build_openai_schema(schema)
        try:
            response = await asyncio.wait_for(
                client.chat.completions.create(
                    model=self._model,
                    max_tokens=4096,
                    response_format={
                        "type": "json_schema",
                        "json_schema": {
                            "name": "ExtractedFields",
                            "schema": json_schema,
                            "strict": True,
                        },
                    },
                    messages=[
                        {
                            "role": "user",
                            "content": [
                                {
                                    "type": "image_url",
                                    "image_url": {"url": f"data:image/png;base64,{image_b64}"},
                                },
                                {
                                    "type": "text",
                                    "text": (
                                        "Extract the listed fields from this PDF page. "
                                        "Return null for any field not present on this page; "
                                        "do not invent or infer values that are not present."
                                    ),
                                },
                            ],
                        }
                    ],
                ),
                timeout=_TIMEOUT_S,
            )
        except Exception as e:  # noqa: BLE001
            logger.warning("openai extract failed: %s", e)
            return None

        try:
            content = response.choices[0].message.content
            if not isinstance(content, str):
                return None
            parsed = json.loads(content)
            if isinstance(parsed, dict):
                return parsed
            return None
        except Exception as e:  # noqa: BLE001
            logger.warning("openai response parse failed: %s", e)
            return None
