import pytest
from unittest.mock import MagicMock, AsyncMock

from app.extractor import extract_page
from app.schema import DEFAULT_SCHEMA


def _fake_provider(return_value):
    p = MagicMock()
    p.extract = AsyncMock(return_value=return_value)
    return p


@pytest.mark.asyncio
async def test_extract_page_delegates_to_provider():
    expected = {f.name: None for f in DEFAULT_SCHEMA}
    expected["title"] = "Hello"
    p = _fake_provider(expected)
    result = await extract_page(b"PNG", DEFAULT_SCHEMA, provider=p)
    assert result == expected
    p.extract.assert_awaited_once()


@pytest.mark.asyncio
async def test_extract_page_propagates_none():
    p = _fake_provider(None)
    result = await extract_page(b"PNG", DEFAULT_SCHEMA, provider=p)
    assert result is None
