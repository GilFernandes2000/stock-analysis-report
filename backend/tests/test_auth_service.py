from datetime import timedelta

from sqlalchemy.orm import Session

from app.models.user import AuthSession
from app.services.auth import AuthService
from app.utils.time import utcnow


def test_resolve_token_returns_user_before_expiry(db_session: Session):
    svc = AuthService(db_session)
    user = svc.register("ana", "Ana", "hunter22")
    _, token = svc.login("ana", "hunter22")

    assert svc.resolve_token(token) is not None
    assert svc.resolve_token(token).id == user.id


def test_resolve_token_rejects_and_purges_expired_session(db_session: Session):
    svc = AuthService(db_session)
    svc.register("ana", "Ana", "hunter22")
    _, token = svc.login("ana", "hunter22")

    session = (
        db_session.query(AuthSession).filter(AuthSession.token == token).one()
    )
    # Stored timestamps are naive UTC; utcnow() must compare correctly against them.
    session.expires_at = utcnow() - timedelta(seconds=1)
    db_session.commit()

    assert svc.resolve_token(token) is None
    assert (
        db_session.query(AuthSession).filter(AuthSession.token == token).first()
        is None
    )
