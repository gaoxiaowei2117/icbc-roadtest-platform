"""用户资料 schema。"""
from datetime import datetime
from pydantic import BaseModel, ConfigDict, EmailStr, Field


class UserPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: EmailStr
    is_admin: bool
    icbc_license_no: str | None
    icbc_last_name: str | None
    preferred_pos: list[str] | None
    time_windows: dict | None
    max_wait_days: int
    created_at: datetime


class UserUpdate(BaseModel):
    icbc_license_no: str | None = Field(default=None, max_length=50)
    icbc_last_name: str | None = Field(default=None, max_length=100)
    preferred_pos: list[str] | None = None
    time_windows: dict | None = None
    max_wait_days: int | None = Field(default=None, ge=1, le=365)


class SecretIn(BaseModel):
    """用户提交 ICBC 凭据。密码字段在响应里永远不返回。"""
    icbc_username: str = Field(min_length=1, max_length=128)
    icbc_password: str = Field(min_length=1, max_length=128)


class SecretStatus(BaseModel):
    has_secret: bool
    updated_at: datetime | None
