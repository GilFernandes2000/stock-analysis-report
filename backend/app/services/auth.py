import hashlib
import hmac
import secrets
from datetime import timedelta

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import AuthSession, User
from app.utils.time import utcnow

PBKDF2_ITERATIONS = 200_000
SESSION_TTL_DAYS = 30

_bearer = HTTPBearer(auto_error=False)


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode(), bytes.fromhex(salt), PBKDF2_ITERATIONS
    )
    return f"pbkdf2${PBKDF2_ITERATIONS}${salt}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        _, iterations, salt, expected = stored.split("$")
        digest = hashlib.pbkdf2_hmac(
            "sha256", password.encode(), bytes.fromhex(salt), int(iterations)
        )
        return hmac.compare_digest(digest.hex(), expected)
    except (ValueError, TypeError):
        return False


class AuthService:
    def __init__(self, db: Session):
        self.db = db

    def register(self, username: str, display_name: str, password: str) -> User:
        username = username.strip().lower()
        if not username or not password:
            raise HTTPException(status_code=422, detail="Username and password required")
        if len(password) < 8:
            raise HTTPException(
                status_code=422, detail="Password must be at least 8 characters"
            )
        existing = self.db.query(User).filter(User.username == username).first()
        if existing:
            raise HTTPException(status_code=409, detail="Username already taken")
        user = User(
            username=username,
            display_name=display_name.strip() or username,
            password_hash=hash_password(password),
        )
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        return user

    def login(self, username: str, password: str) -> tuple[User, str]:
        user = (
            self.db.query(User)
            .filter(User.username == username.strip().lower())
            .first()
        )
        if not user or not verify_password(password, user.password_hash):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid username or password",
            )
        token = secrets.token_urlsafe(48)
        session = AuthSession(
            token=token,
            user_id=user.id,
            expires_at=utcnow() + timedelta(days=SESSION_TTL_DAYS),
        )
        self.db.add(session)
        self.db.commit()
        return user, token

    def logout(self, token: str) -> None:
        self.db.query(AuthSession).filter(AuthSession.token == token).delete()
        self.db.commit()

    def resolve_token(self, token: str) -> User | None:
        session = (
            self.db.query(AuthSession).filter(AuthSession.token == token).first()
        )
        if not session:
            return None
        if session.expires_at < utcnow():
            self.db.delete(session)
            self.db.commit()
            return None
        return session.user


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: Session = Depends(get_db),
) -> User:
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    user = AuthService(db).resolve_token(credentials.credentials)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session expired or invalid",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user
