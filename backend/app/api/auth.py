"""/api/auth/* 注册 / 邮箱验证 / 登录 / 刷新。"""
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import get_db
from app.core.email import send_verification_code
from app.core.ratelimit import limiter
from app.core.security import create_access_token, create_refresh_token, decode_token
from app.crud import user as user_crud
from app.schemas.auth import (
    AccessTokenOut, LoginIn, MessageOut, RefreshIn, RegisterIn, RegisterOut,
    ResendCodeIn, TokenOut, VerifyEmailIn,
)

router = APIRouter(prefix="/auth", tags=["auth"])
_auth_limit = get_settings().auth_rate_limit
_CODE_TTL_MIN = 10


def _gen_code() -> str:
    return f"{secrets.randbelow(1000000):06d}"


def _issue_code(db: Session, user) -> None:
    code = _gen_code()
    expires = datetime.now(timezone.utc) + timedelta(minutes=_CODE_TTL_MIN)
    user_crud.set_verify_code(db, user, code, expires)
    send_verification_code(user.email, code)


@router.post("/register", response_model=RegisterOut, status_code=status.HTTP_201_CREATED)
@limiter.limit(_auth_limit)
def register(request: Request, payload: RegisterIn, db: Session = Depends(get_db)) -> RegisterOut:
    if user_crud.get_by_email(db, payload.email):
        raise HTTPException(status.HTTP_409_CONFLICT, "邮箱已注册")
    user = user_crud.create(db, payload.email, payload.password, is_admin=False)
    _issue_code(db, user)
    return RegisterOut(message="验证码已发送到邮箱，请查收并验证")


@router.post("/verify-email", response_model=TokenOut)
@limiter.limit(_auth_limit)
def verify_email(request: Request, payload: VerifyEmailIn, db: Session = Depends(get_db)) -> TokenOut:
    user = user_crud.get_by_email(db, payload.email)
    if user is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "验证码错误或已过期")
    if user.email_verified:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "邮箱已验证，请直接登录")
    now = datetime.now(timezone.utc)
    if (user.verify_code != payload.code or user.verify_code_expires is None
            or user.verify_code_expires < now):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "验证码错误或已过期")
    user_crud.mark_verified(db, user)
    return TokenOut(
        access_token=create_access_token(user.id),
        refresh_token=create_refresh_token(user.id),
    )


@router.post("/resend-code", response_model=MessageOut)
@limiter.limit(_auth_limit)
def resend_code(request: Request, payload: ResendCodeIn, db: Session = Depends(get_db)) -> MessageOut:
    user = user_crud.get_by_email(db, payload.email)
    if user is not None and not user.email_verified:
        _issue_code(db, user)
    return MessageOut(message="若该邮箱已注册且未验证，验证码已重新发送")


@router.post("/login", response_model=TokenOut)
@limiter.limit(_auth_limit)
def login(request: Request, payload: LoginIn, db: Session = Depends(get_db)) -> TokenOut:
    user = user_crud.authenticate(db, payload.email, payload.password)
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "邮箱或密码错误")
    if not user.email_verified:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "邮箱未验证，请先验证")
    return TokenOut(
        access_token=create_access_token(user.id),
        refresh_token=create_refresh_token(user.id),
    )


@router.post("/refresh", response_model=AccessTokenOut)
def refresh(payload: RefreshIn, db: Session = Depends(get_db)) -> AccessTokenOut:
    user_id = decode_token(payload.refresh_token, "refresh")
    if user_id is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "refresh token 无效")
    user = user_crud.get_by_id(db, user_id)
    if user is None or not user.is_active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "用户不存在")
    return AccessTokenOut(access_token=create_access_token(user.id))
