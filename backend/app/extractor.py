from __future__ import annotations

from typing import TYPE_CHECKING

from app.providers import get_provider
from app.schema import FieldDef

if TYPE_CHECKING:
    from app.providers.base import Provider


async def extract_page(
    image_png: bytes,
    schema: list[FieldDef],
    *,
    provider_name: str | None = None,
    provider: "Provider | None" = None,  # for tests
) -> dict | None:
    """Extract fields from a page image using the configured provider.

    provider_name: optional override of the env-configured default.
    provider: optional injection for tests (overrides provider_name).
    """
    if provider is not None:
        return await provider.extract(image_png, schema)
    impl = get_provider(provider_name)
    return await impl.extract(image_png, schema)
