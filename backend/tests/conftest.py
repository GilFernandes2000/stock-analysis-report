from collections.abc import Generator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db


@pytest.fixture()
def db_session() -> Generator[Session, None, None]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    TestingSession = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = TestingSession()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def api_client(db_session: Session) -> Generator[TestClient, None, None]:
    from app.api import auth, favorites, portfolios, reports

    app = FastAPI()
    app.include_router(auth.router, prefix="/api")
    app.include_router(portfolios.router, prefix="/api")
    app.include_router(reports.router, prefix="/api")
    app.include_router(favorites.router, prefix="/api")

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as client:
        yield client


@pytest.fixture()
def auth_headers(api_client: TestClient) -> dict[str, str]:
    response = api_client.post(
        "/api/auth/register",
        json={"username": "joao", "display_name": "João", "password": "secret123"},
    )
    assert response.status_code == 201, response.text
    token = response.json()["token"]
    return {"Authorization": f"Bearer {token}"}
