from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from app import session_store

FIXTURE = Path(__file__).parent / "fixtures" / "EC_1105-2-2.pdf"


@pytest.fixture(autouse=True)
def reset_store():
    session_store.store.clear()
    yield
    session_store.store.clear()


@pytest.fixture
def fake_extract():
    async def _fake(image: bytes, schema, client=None):
        return {f.name: None for f in schema} | {
            "title": "Test Doc",
            "document_number": "EC 1105-2-2",
            "references": ["AR 1-1"],
        }
    with patch("app.routes.extractor.extract_page", side_effect=_fake):
        yield


def _upload(client, **patches):
    return client.post(
        "/upload",
        files={"file": ("sample.pdf", FIXTURE.read_bytes(), "application/pdf")},
    )


def test_upload_rejects_non_pdf(client):
    r = client.post("/upload", files={"file": ("x.txt", b"hello", "text/plain")})
    assert r.status_code == 400


def test_upload_rejects_empty(client):
    r = client.post("/upload", files={"file": ("x.pdf", b"", "application/pdf")})
    assert r.status_code == 400


def test_upload_rejects_corrupt(client):
    r = client.post("/upload", files={"file": ("x.pdf", b"not a pdf", "application/pdf")})
    assert r.status_code == 400


def test_upload_returns_session(client, fake_extract):
    r = _upload(client)
    assert r.status_code == 200
    body = r.json()
    assert body["page_count"] == 1
    assert body["values"]["title"] == "Test Doc"
    assert body["values"]["document_number"] == "EC 1105-2-2"
    assert body["values"]["references"] == ["AR 1-1"]
    assert body["original_extracted"]["title"] == "Test Doc"


def test_upload_records_extraction_errors(client):
    async def _fail(image, schema, client=None):
        return None
    with patch("app.routes.extractor.extract_page", side_effect=_fail):
        r = _upload(client)
    assert r.json()["extraction_errors"] == [1]
    assert r.json()["values"]["title"] == ""


def test_get_pdf_returns_bytes(client, fake_extract):
    sid = _upload(client).json()["session_id"]
    r = client.get(f"/sessions/{sid}/pdf")
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/pdf"
    assert r.content[:4] == b"%PDF"


def test_patch_set_scalar(client, fake_extract):
    sid = _upload(client).json()["session_id"]
    r = client.patch(
        f"/sessions/{sid}/values",
        json={"op": "set", "field": "title", "value": "Manual"},
    )
    assert r.status_code == 200
    assert r.json()["value"] == "Manual"


def test_patch_revert_returns_to_original(client, fake_extract):
    sid = _upload(client).json()["session_id"]
    client.patch(f"/sessions/{sid}/values",
                 json={"op": "set", "field": "title", "value": "Manual"})
    r = client.patch(f"/sessions/{sid}/values",
                     json={"op": "revert", "field": "title"})
    assert r.json()["value"] == "Test Doc"


def test_add_custom_field(client, fake_extract):
    sid = _upload(client).json()["session_id"]
    r = client.post(f"/sessions/{sid}/fields", json={"name": "keywords"})
    assert r.status_code == 200
    names = [f["name"] for f in r.json()["schema"]]
    assert "keywords" in names


def test_add_duplicate_field_returns_409(client, fake_extract):
    sid = _upload(client).json()["session_id"]
    r = client.post(f"/sessions/{sid}/fields", json={"name": "title"})
    assert r.status_code == 409


def test_delete_removable_field(client, fake_extract):
    sid = _upload(client).json()["session_id"]
    r = client.delete(f"/sessions/{sid}/fields/references")
    assert r.status_code == 200
    assert "references" not in [f["name"] for f in r.json()["schema"]]


def test_delete_non_removable_field_400(client, fake_extract):
    sid = _upload(client).json()["session_id"]
    r = client.delete(f"/sessions/{sid}/fields/title")
    assert r.status_code == 400


def test_extract_page_re_merge_only_fills_empty_scalars(client, fake_extract):
    sid = _upload(client).json()["session_id"]
    # Manually clear title, then re-extract — should refill from extractor.
    client.patch(f"/sessions/{sid}/values",
                 json={"op": "set", "field": "title", "value": ""})
    r = client.post(f"/sessions/{sid}/extract-page", json={"page": 1})
    assert r.json()["values"]["title"] == "Test Doc"


def test_extract_page_does_not_overwrite_user_scalar(client, fake_extract):
    sid = _upload(client).json()["session_id"]
    client.patch(f"/sessions/{sid}/values",
                 json={"op": "set", "field": "title", "value": "Mine"})
    r = client.post(f"/sessions/{sid}/extract-page", json={"page": 1})
    assert r.json()["values"]["title"] == "Mine"


def test_unknown_session_404(client):
    r = client.get("/sessions/nope/pdf")
    assert r.status_code == 404
