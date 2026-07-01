from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app import auth as auth_service
from app.auth import SESSION_COOKIE, get_current_user
from app.database import get_db
from app.models import User
from app.routers.common import user_out
from app.schemas import LoginRequest, LoginResponse, UserOut


router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/login", response_model=LoginResponse)
def login(payload: LoginRequest, response: Response, db: Session = Depends(get_db)):
    user = db.query(User).filter_by(username=payload.username).one_or_none()
    if not user or not user.is_active or not auth_service.verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid username or password")

    user.last_login_at = datetime.now(timezone.utc)
    db.add(user)
    db.commit()
    db.refresh(user)

    token = auth_service.create_session_token(user)
    response.set_cookie(
        SESSION_COOKIE,
        token,
        httponly=True,
        secure=auth_service.COOKIE_SECURE,
        samesite="lax",
        max_age=auth_service.SESSION_MINUTES * 60,
        path="/",
    )
    return {"user": user_out(user)}


@router.post("/logout")
def logout(response: Response):
    response.delete_cookie(SESSION_COOKIE, path="/")
    return {"ok": True}


@router.get("/me", response_model=UserOut)
def me(current_user: User = Depends(get_current_user)):
    return user_out(current_user)
