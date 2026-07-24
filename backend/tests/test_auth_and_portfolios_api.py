import io

from fastapi.testclient import TestClient

from tests.test_importers import DEGIRO_TRANSACTIONS


def test_register_login_me_logout(api_client: TestClient):
    r = api_client.post(
        "/api/auth/register",
        json={"username": "Ana", "display_name": "Ana", "password": "hunter22"},
    )
    assert r.status_code == 201
    token = r.json()["token"]
    assert r.json()["user"]["username"] == "ana"

    # duplicate username rejected
    r2 = api_client.post(
        "/api/auth/register",
        json={"username": "ana", "display_name": "", "password": "hunter22"},
    )
    assert r2.status_code == 409

    r3 = api_client.post(
        "/api/auth/login", json={"username": "ANA", "password": "hunter22"}
    )
    assert r3.status_code == 200

    bad = api_client.post(
        "/api/auth/login", json={"username": "ana", "password": "wrong"}
    )
    assert bad.status_code == 401

    headers = {"Authorization": f"Bearer {token}"}
    me = api_client.get("/api/auth/me", headers=headers)
    assert me.status_code == 200
    assert me.json()["username"] == "ana"

    out = api_client.post("/api/auth/logout", headers=headers)
    assert out.status_code == 204
    me2 = api_client.get("/api/auth/me", headers=headers)
    assert me2.status_code == 401


def test_portfolio_crud_requires_auth(api_client: TestClient):
    assert api_client.get("/api/portfolios").status_code in (401, 403)


def test_portfolio_crud_and_transactions(api_client: TestClient, auth_headers):
    created = api_client.post(
        "/api/portfolios",
        json={"name": "Main", "broker": "degiro", "base_currency": "eur"},
        headers=auth_headers,
    )
    assert created.status_code == 201, created.text
    pid = created.json()["id"]
    assert created.json()["base_currency"] == "EUR"

    txn = api_client.post(
        f"/api/portfolios/{pid}/transactions",
        json={
            "type": "buy",
            "date": "2024-01-02T09:30:00",
            "ticker": "aapl",
            "shares": 10,
            "price": 150.0,
            "currency": "USD",
            "amount": -1380.0,
            "fees": 2.0,
        },
        headers=auth_headers,
    )
    assert txn.status_code == 201, txn.text
    assert txn.json()["ticker"] == "AAPL"

    txns = api_client.get(
        f"/api/portfolios/{pid}/transactions", headers=auth_headers
    )
    assert len(txns.json()) == 1

    # second user cannot see the first user's portfolio
    other = api_client.post(
        "/api/auth/register",
        json={"username": "bob", "display_name": "Bob", "password": "secret99"},
    )
    other_headers = {"Authorization": f"Bearer {other.json()['token']}"}
    denied = api_client.get(f"/api/portfolios/{pid}", headers=other_headers)
    assert denied.status_code == 404


def test_import_preview_and_commit(api_client: TestClient, auth_headers, monkeypatch):
    monkeypatch.setattr(
        "app.services.importers.IsinResolver._lookup",
        staticmethod(lambda isin, currency=None: None),
    )
    created = api_client.post(
        "/api/portfolios",
        json={"name": "Degiro", "broker": "degiro"},
        headers=auth_headers,
    )
    pid = created.json()["id"]

    preview = api_client.post(
        f"/api/portfolios/{pid}/import/preview",
        files={"file": ("Transactions.csv", io.BytesIO(DEGIRO_TRANSACTIONS.encode()), "text/csv")},
        headers=auth_headers,
    )
    assert preview.status_code == 200, preview.text
    body = preview.json()
    assert body["broker"] == "degiro"
    assert body["file_kind"] == "transactions"
    assert body["total_rows"] == 3
    assert body["duplicate_count"] == 0
    # no network -> Degiro rows (no broker ticker) stay unresolved
    assert "US0378331005" in body["unresolved_isins"]

    # user maps the unresolved tickers, then commits
    for row in body["rows"]:
        if row["isin"] == "US0378331005":
            row["ticker"] = "AAPL"
        elif row["isin"] == "NL0010273215":
            row["ticker"] = "ASML.AS"

    commit = api_client.post(
        f"/api/portfolios/{pid}/import/commit",
        json={"rows": body["rows"], "skip_duplicates": True},
        headers=auth_headers,
    )
    assert commit.status_code == 200, commit.text
    assert commit.json() == {"imported": 3, "skipped": 0}

    # re-importing the same file flags everything as duplicate
    preview2 = api_client.post(
        f"/api/portfolios/{pid}/import/preview",
        files={"file": ("Transactions.csv", io.BytesIO(DEGIRO_TRANSACTIONS.encode()), "text/csv")},
        headers=auth_headers,
    )
    assert preview2.json()["duplicate_count"] == 3

    commit2 = api_client.post(
        f"/api/portfolios/{pid}/import/commit",
        json={"rows": preview2.json()["rows"], "skip_duplicates": True},
        headers=auth_headers,
    )
    assert commit2.json() == {"imported": 0, "skipped": 3}
