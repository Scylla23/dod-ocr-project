import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.providers import get_provider, list_providers, PROVIDERS
from app.providers.anthropic_provider import AnthropicProvider
from app.providers.openai_provider import OpenAIProvider, _build_openai_schema
from app.schema import DEFAULT_SCHEMA, FieldDef


def test_list_providers_includes_both():
    names = list_providers()
    assert "anthropic" in names
    assert "openai" in names


def test_get_provider_unknown_name_raises():
    with pytest.raises(ValueError, match="unknown provider"):
        get_provider("bogus")


def test_get_provider_default_is_anthropic_unless_overridden(monkeypatch):
    monkeypatch.delenv("EXTRACTOR_PROVIDER", raising=False)
    # The default at import-time is captured; we re-read
    import importlib
    import app.providers as providers_module
    importlib.reload(providers_module)
    p = providers_module.get_provider()
    assert p.name == "anthropic"


def test_build_openai_schema_includes_additional_properties_false():
    schema = [
        FieldDef("title", "string", False),
        FieldDef("refs", "list[string]", True),
    ]
    js = _build_openai_schema(schema)
    assert js["additionalProperties"] is False
    assert js["required"] == ["title", "refs"]
    assert js["properties"]["title"]["type"] == ["string", "null"]
    assert js["properties"]["refs"]["type"] == ["array", "null"]


@pytest.mark.asyncio
async def test_anthropic_provider_extracts_via_tool_use():
    expected = {f.name: None for f in DEFAULT_SCHEMA}
    expected["title"] = "Doc A"
    block = MagicMock()
    block.type = "tool_use"
    block.name = "record_extracted_fields"
    block.input = expected
    response = MagicMock()
    response.content = [block]
    fake_client = MagicMock()
    fake_client.messages.create = AsyncMock(return_value=response)

    p = AnthropicProvider()
    p._client = fake_client  # type: ignore[attr-defined]
    result = await p.extract(b"PNG", list(DEFAULT_SCHEMA))
    assert result == expected


@pytest.mark.asyncio
async def test_openai_provider_extracts_from_json_response():
    import json
    payload = {f.name: None for f in DEFAULT_SCHEMA}
    payload["title"] = "Doc A"
    msg = MagicMock()
    msg.content = json.dumps(payload)
    choice = MagicMock()
    choice.message = msg
    response = MagicMock()
    response.choices = [choice]
    fake_client = MagicMock()
    fake_client.chat.completions.create = AsyncMock(return_value=response)

    p = OpenAIProvider()
    p._client = fake_client  # type: ignore[attr-defined]
    result = await p.extract(b"PNG", list(DEFAULT_SCHEMA))
    assert result == payload


@pytest.mark.asyncio
async def test_openai_provider_returns_none_on_invalid_json():
    msg = MagicMock()
    msg.content = "not json"
    choice = MagicMock()
    choice.message = msg
    response = MagicMock()
    response.choices = [choice]
    fake_client = MagicMock()
    fake_client.chat.completions.create = AsyncMock(return_value=response)

    p = OpenAIProvider()
    p._client = fake_client  # type: ignore[attr-defined]
    result = await p.extract(b"PNG", list(DEFAULT_SCHEMA))
    assert result is None


@pytest.mark.asyncio
async def test_anthropic_provider_returns_none_on_exception():
    fake_client = MagicMock()
    fake_client.messages.create = AsyncMock(side_effect=RuntimeError("API down"))
    p = AnthropicProvider()
    p._client = fake_client  # type: ignore[attr-defined]
    result = await p.extract(b"PNG", list(DEFAULT_SCHEMA))
    assert result is None
