from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.static import mount_frontend


def test_serves_index_when_dist_exists(tmp_path: Path, monkeypatch):
    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "index.html").write_text("<html><body>UI</body></html>", encoding="utf-8")

    monkeypatch.setattr(
        "app.static.settings.serve_frontend",
        True,
    )
    monkeypatch.setattr(
        "app.static.settings.frontend_dist_path",
        dist,
    )

    app = FastAPI()
    mount_frontend(app)
    client = TestClient(app)

    response = client.get("/")
    assert response.status_code == 200
    assert "UI" in response.text
