"""注册/登录/刷新 token 的请求响应模型。"""
from typing import Literal

from pydantic import BaseModel, EmailStr, Field

# Which frontend the user signed up on; only changes the verification email branding.
Site = Literal["booking", "routes"]


class RegisterIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    site: Site = "booking"


class LoginIn(BaseModel):
    email: EmailStr
    password: str


class RefreshIn(BaseModel):
    refresh_token: str


class TokenOut(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class AccessTokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"


class RegisterOut(BaseModel):
    message: str


class VerifyEmailIn(BaseModel):
    email: EmailStr
    code: str = Field(min_length=6, max_length=6)


class ResendCodeIn(BaseModel):
    email: EmailStr
    site: Site = "booking"


class MessageOut(BaseModel):
    message: str
