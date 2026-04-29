import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.extractor import extract_page
from app.schema import DEFAULT_SCHEMA


def _fake_anthropic_response(tool_input: dict) -> MagicMock:
    block = MagicMock()
    block.type = "tool_use"
    block.name = "record_extracted_fields"
    block.input = tool_input
    response = MagicMock()
    response.content = [block]
    response.stop_reason = "tool_use"
    return response


@pytest.mark.asyncio
async def test_extract_page_returns_tool_input():
    expected = {f.name: None for f in DEFAULT_SCHEMA}
    expected["title"] = "Hello"
    fake_client = MagicMock()
    fake_client.messages.create = AsyncMock(return_value=_fake_anthropic_response(expected))

    result = await extract_page(b"PNG", DEFAULT_SCHEMA, client=fake_client)
    assert result == expected
    args, kwargs = fake_client.messages.create.call_args
    assert kwargs["tools"][0]["name"] == "record_extracted_fields"
    assert kwargs["tool_choice"] == {"type": "tool", "name": "record_extracted_fields"}
    msg = kwargs["messages"][0]["content"]
    image_block = next(b for b in msg if b["type"] == "image")
    assert image_block["source"]["type"] == "base64"
    assert image_block["source"]["media_type"] == "image/png"


@pytest.mark.asyncio
async def test_extract_page_returns_none_on_no_tool_use():
    response = MagicMock()
    text_block = MagicMock()
    text_block.type = "text"
    response.content = [text_block]
    response.stop_reason = "end_turn"
    fake_client = MagicMock()
    fake_client.messages.create = AsyncMock(return_value=response)
    result = await extract_page(b"PNG", DEFAULT_SCHEMA, client=fake_client)
    assert result is None


@pytest.mark.asyncio
async def test_extract_page_returns_none_on_exception():
    fake_client = MagicMock()
    fake_client.messages.create = AsyncMock(side_effect=RuntimeError("API down"))
    result = await extract_page(b"PNG", DEFAULT_SCHEMA, client=fake_client)
    assert result is None
