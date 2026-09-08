from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.schemas.auth import AuthResponse, LoginRequest, RegisterRequest, UserResponse
from app.services.auth import AuthService, get_current_user
from app.services.rate_limit import login_limiter

router = APIRouter(prefix="/auth", tags=["auth"])
_bearer = HTTPBearer(auto_error=False)


def _rate_key(username: str, request: Request) -> str:
    client = request.client.host if request.client else "unknown"
    return f"{username.strip().lower()}|{client}"


@router.post("/register", response_model=AuthResponse, status_code=201)
def register(payload: RegisterRequest, db: Session = Depends(get_db)):
    service = AuthService(db)
    service.register(payload.username, payload.display_name, payload.password)
    user, token = service.login(payload.username, payload.password)
    return AuthResponse(token=token, user=UserResponse.model_validate(user))


@router.post("/login", response_model=AuthResponse)
def login(payload: LoginRequest, request: Request, db: Session = Depends(get_db)):
    key = _rate_key(payload.username, request)
    login_limiter.check(key)
    try:
        user, token = AuthService(db).login(payload.username, payload.password)
    except HTTPException as exc:
        if exc.status_code == 401:
            login_limiter.record_failure(key)
        raise
    login_limiter.reset(key)
    return AuthResponse(token=token, user=UserResponse.model_validate(user))


@router.post("/logout", status_code=204)
def logout(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: Session = Depends(get_db),
):
    if credentials is not None:
        AuthService(db).logout(credentials.credentials)


@router.get("/me", response_model=UserResponse)
def me(user: User = Depends(get_current_user)):
    return UserResponse.model_validate(user)
