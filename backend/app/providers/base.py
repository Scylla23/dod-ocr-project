from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from app.schema import FieldDef


class Provider(Protocol):
    name: str

    async def extract(self, image_png: bytes, schema: list["FieldDef"]) -> dict | None:
        """Returns the extracted dict on success, None on any failure (timeout, API error, malformed response)."""
        ...


class ExtractorError(Exception):
    """Raised when extraction fails in a recoverable way."""
