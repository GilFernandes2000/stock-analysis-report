import pytest
from fastapi.testclient import TestClient

from app.services.rate_limit import login_limiter


@pytest.fixture(autouse=True)
def _clear_limiter():
    login_limiter.clear()
    yield
    login_limiter.clear()


def _register(client: TestClient, username: str = "ana", password: str = "hunter22"):
    r = client.post(
        "/api/auth/register",
        json={"username": username, "display_name": username, "password": password},
    )
    assert r.status_code == 201, r.text


def test_login_locks_out_after_repeated_failures(api_client: TestClient):
    _register(api_client)

    for _ in range(login_limiter.max_events):
        bad = api_client.post(
            "/api/auth/login", json={"username": "ana", "password": "nope"}
        )
        assert bad.status_code == 401

    # Cap reached: further attempts are refused before the password is checked,
    # so even the correct password is rejected while the window is open.
    blocked = api_client.post(
        "/api/auth/login", json={"username": "ana", "password": "hunter22"}
    )
    assert blocked.status_code == 429
    assert blocked.headers.get("Retry-After")

    login_limiter.clear()
    ok = api_client.post(
        "/api/auth/login", json={"username": "ana", "password": "hunter22"}
    )
    assert ok.status_code == 200


def test_successful_login_resets_the_failure_counter(api_client: TestClient):
    _register(api_client)

    for _ in range(login_limiter.max_events - 1):
        api_client.post(
            "/api/auth/login", json={"username": "ana", "password": "nope"}
        )

    good = api_client.post(
        "/api/auth/login", json={"username": "ana", "password": "hunter22"}
    )
    assert good.status_code == 200

    # Counter was reset, so the next wrong attempt is a 401, not a 429.
    again = api_client.post(
        "/api/auth/login", json={"username": "ana", "password": "nope"}
    )
    assert again.status_code == 401
