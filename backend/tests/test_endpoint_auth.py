import io

from fastapi.testclient import TestClient


def test_screener_requires_auth(api_client: TestClient):
    assert api_client.get("/api/screener/presets").status_code in (401, 403)
    assert api_client.get("/api/screener/top_performers").status_code in (401, 403)


def test_import_preview_rejects_oversized_file(api_client: TestClient, auth_headers):
    pid = api_client.post(
        "/api/portfolios",
        json={"name": "P", "broker": "degiro"},
        headers=auth_headers,
    ).json()["id"]

    big = b"x" * (10_000_001)
    r = api_client.post(
        f"/api/portfolios/{pid}/import/preview",
        files={"file": ("huge.csv", io.BytesIO(big), "text/csv")},
        headers=auth_headers,
    )
    assert r.status_code == 413
