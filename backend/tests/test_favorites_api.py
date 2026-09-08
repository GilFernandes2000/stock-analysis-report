from fastapi.testclient import TestClient


def test_favorites_crud(api_client: TestClient, auth_headers):
    # empty to start
    assert api_client.get("/api/favorites", headers=auth_headers).json() == []

    # add
    r = api_client.post("/api/favorites", json={"ticker": "aapl"}, headers=auth_headers)
    assert r.status_code == 201
    assert r.json()["ticker"] == "AAPL"

    # adding the same ticker again is idempotent (no duplicate)
    r2 = api_client.post("/api/favorites", json={"ticker": "AAPL"}, headers=auth_headers)
    assert r2.status_code == 201
    listing = api_client.get("/api/favorites", headers=auth_headers).json()
    assert len(listing) == 1

    # add a second, newest-first ordering
    api_client.post("/api/favorites", json={"ticker": "ASML.AS"}, headers=auth_headers)
    tickers = [f["ticker"] for f in api_client.get("/api/favorites", headers=auth_headers).json()]
    assert tickers == ["ASML.AS", "AAPL"]

    # invalid ticker rejected
    bad = api_client.post("/api/favorites", json={"ticker": "!!"}, headers=auth_headers)
    assert bad.status_code == 422

    # remove
    assert api_client.delete("/api/favorites/AAPL", headers=auth_headers).status_code == 204
    remaining = [f["ticker"] for f in api_client.get("/api/favorites", headers=auth_headers).json()]
    assert remaining == ["ASML.AS"]

    # removing a non-favorite 404s
    assert api_client.delete("/api/favorites/TSLA", headers=auth_headers).status_code == 404


def test_favorites_isolated_per_user(api_client: TestClient, auth_headers):
    api_client.post("/api/favorites", json={"ticker": "AAPL"}, headers=auth_headers)

    other = api_client.post(
        "/api/auth/register",
        json={"username": "mallory", "display_name": "M", "password": "secret12"},
    )
    other_headers = {"Authorization": f"Bearer {other.json()['token']}"}
    assert api_client.get("/api/favorites", headers=other_headers).json() == []


def test_favorites_require_auth(api_client: TestClient):
    assert api_client.get("/api/favorites").status_code in (401, 403)


def test_quotes_uses_quote_service(api_client: TestClient, auth_headers, monkeypatch):
    from app.schemas.favorite import Quote

    api_client.post("/api/favorites", json={"ticker": "AAPL"}, headers=auth_headers)

    def fake_get_quotes(self, tickers, display_currency):
        return (
            [
                Quote(
                    ticker=t,
                    name=f"{t} Inc",
                    price=100.0,
                    change_pct=1.5,
                    display_currency=display_currency,
                )
                for t in tickers
            ],
            False,
        )

    monkeypatch.setattr(
        "app.services.quotes.QuoteService.get_quotes", fake_get_quotes
    )
    resp = api_client.get("/api/favorites/quotes?currency=EUR", headers=auth_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["display_currency"] == "EUR"
    assert body["quotes"][0]["ticker"] == "AAPL"
    assert body["quotes"][0]["price"] == 100.0
