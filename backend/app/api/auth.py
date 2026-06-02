"""/api/auth/* 注册 / 登录 / 刷新 / 当前用户信息。"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import create_access_token, create_refresh_token, decode_token
from app.crud import user as user_crud
from app.schemas.auth import AccessTokenOut, LoginIn, RefreshIn, RegisterIn, TokenOut
from app.schemas.user import UserPublic

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=TokenOut, status_code=status.HTTP_201_CREATED)
def register(payload: RegisterIn, db: Session = Depends(get_db)) -> TokenOut:
    if user_crud.get_by_email(db, payload.email):
        raise HTTPException(status.HTTP_409_CONFLICT, "邮箱已注册")
    user = user_crud.create(db, payload.email, payload.password, is_admin=False)
    return TokenOut(
        access_token=create_access_token(user.id),
        refresh_token=create_refresh_token(user.id),
    )


@router.post("/login", response_model=TokenOut)
def login(payload: LoginIn, db: Session = Depends(get_db)) -> TokenOut:
    user = user_crud.authenticate(db, payload.email, payload.password)
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "邮箱或密码错误")
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
