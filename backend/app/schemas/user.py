"""用户资料 schema。"""
from datetime import date, datetime
from pydantic import BaseModel, ConfigDict, EmailStr, Field


class ProfileFields(BaseModel):
    """抢号档案字段（UserPublic 与 UserUpdate 共用形状）。"""
    icbc_license_no: str | None = None
    icbc_last_name: str | None = None
    exam_class: str | None = None
    pos_ids: list[int] | None = None
    expect_after_date: date | None = None
    expect_before_date: date | None = None
    expect_time_range: str | None = None
    pref_days_of_week: list[int] | None = None
    pref_parts_of_day: list[int] | None = None


class UserPublic(ProfileFields):
    model_config = ConfigDict(from_attributes=True)
    id: int
    email: EmailStr
    is_admin: bool
    created_at: datetime


class UserUpdate(ProfileFields):
    icbc_license_no: str | None = Field(default=None, max_length=50)
    icbc_last_name: str | None = Field(default=None, max_length=100)
    exam_class: str | None = Field(default=None, max_length=10)
    expect_time_range: str | None = Field(default=None, max_length=20)


class SecretIn(BaseModel):
    """用户提交 ICBC 登录 keyword（加密存储）。"""
    keyword: str = Field(min_length=1, max_length=128)


class SecretStatus(BaseModel):
    has_secret: bool
    updated_at: datetime | None
