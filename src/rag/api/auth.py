from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.orm import Session

from rag.auth.utils import create_access_token, get_password_hash, verify_password
from rag.config.settings import settings
from rag.db import get_db
from rag.db_models import User

router = APIRouter(prefix="/auth", tags=["auth"])


class RegisterRequest(BaseModel):
    email: EmailStr
    username: str = Field(..., min_length=3, max_length=50)
    password: str


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


def _set_token_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key="access_token", value=token, httponly=True, secure=False, samesite="lax",
        max_age=settings.JWT_EXPIRES_MINUTES * 60,
    )


@router.post("/register")
def register(
    payload: RegisterRequest,
    response: Response,
    db: Session = Depends(get_db),  # noqa: B008
) -> dict[str, str]:
    if len(payload.password) < 8:
        raise HTTPException(status_code=422, detail="Password must be at least 8 characters")

    if db.query(User).filter(User.email == payload.email).first():
        raise HTTPException(status_code=400, detail="Email already registered")
        
    if db.query(User).filter(User.username == payload.username).first():
        raise HTTPException(status_code=400, detail="Username already taken")

    user = User(
        email=payload.email, 
        username=payload.username, 
        hashed_password=get_password_hash(payload.password)
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    token = create_access_token(user.id, user.email)
    _set_token_cookie(response, token)
    return {"status": "registered", "email": user.email, "username": user.username}


@router.post("/login")
def login(
    payload: LoginRequest,
    response: Response,
    db: Session = Depends(get_db),  # noqa: B008
) -> dict[str, str]:
    user = db.query(User).filter(User.email == payload.email).first()
    if not user or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    token = create_access_token(user.id, user.email)
    _set_token_cookie(response, token)
    return {"status": "logged_in", "email": user.email, "username": user.username}


@router.post("/logout")
def logout(response: Response) -> dict[str, str]:
    response.delete_cookie("access_token")
    return {"status": "logged_out"}
