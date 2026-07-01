"""用户资料 schema。"""
import re
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator

_TIME_RANGE_RE = re.compile(r"^([01]\d|2[0-3]):([0-5]\d)-([01]\d|2[0-3]):([0-5]\d)$")
_MAX_POS_IDS = 50


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


class AdminUserOut(UserPublic):
    is_active: bool
    email_verified: bool
    has_secret: bool


class UserUpdate(ProfileFields):
    icbc_license_no: str | None = Field(default=None, max_length=50)
    icbc_last_name: str | None = Field(default=None, max_length=100)
    exam_class: str | None = Field(default=None, max_length=10)
    expect_time_range: str | None = Field(default=None, max_length=20)

    @field_validator("exam_class")
    @classmethod
    def _check_exam_class(cls, v: str | None) -> str | None:
        # ICBC 可在线预约 road test 的驾照班级：5、6、7、8（含摩托车 novice）；
        # 商用类 1-4 需电话/线下预约，本平台不支持。
        if v is not None and v not in {"5", "6", "7", "8"}:
            raise ValueError("exam_class 必须是可在线预约 road test 的班级码（5-8）")
        return v

    @field_validator("pos_ids")
    @classmethod
    def _check_pos_ids(cls, v: list[int] | None) -> list[int] | None:
        if v is None:
            return v
        if len(v) > _MAX_POS_IDS:
            raise ValueError(f"考点数量不能超过 {_MAX_POS_IDS} 个")
        # 延迟导入避免 schema ← api 的导入耦合。
        from app.api.pos import valid_pos_ids

        allowed = valid_pos_ids()
        deduped: list[int] = []
        for pid in v:
            if pid not in allowed:
                raise ValueError(f"无效的考点 ID：{pid}")
            if pid not in deduped:
                deduped.append(pid)
        return deduped

    @field_validator("pref_days_of_week")
    @classmethod
    def _check_days(cls, v: list[int] | None) -> list[int] | None:
        if v is None:
            return v
        deduped: list[int] = []
        for d in v:
            if not 0 <= d <= 6:
                raise ValueError("星期取值必须在 0-6 之间")
            if d not in deduped:
                deduped.append(d)
        return deduped

    @field_validator("pref_parts_of_day")
    @classmethod
    def _check_parts(cls, v: list[int] | None) -> list[int] | None:
        if v is None:
            return v
        deduped: list[int] = []
        for p in v:
            if p not in (0, 1):
                raise ValueError("时段取值必须是 0（上午）或 1（下午）")
            if p not in deduped:
                deduped.append(p)
        return deduped

    @field_validator("expect_time_range")
    @classmethod
    def _check_time_range(cls, v: str | None) -> str | None:
        if v is None:
            return v
        m = _TIME_RANGE_RE.match(v)
        if not m:
            raise ValueError("时间区间格式必须为 HH:MM-HH:MM")
        start = (int(m.group(1)), int(m.group(2)))
        end = (int(m.group(3)), int(m.group(4)))
        if start >= end:
            raise ValueError("时间区间的起始必须早于结束")
        return v

    @model_validator(mode="after")
    def _check_date_order(self) -> "UserUpdate":
        if (
            self.expect_after_date is not None
            and self.expect_before_date is not None
            and self.expect_before_date < self.expect_after_date
        ):
            raise ValueError("结束日期不能早于开始日期")
        return self


class SecretIn(BaseModel):
    """用户提交 ICBC 登录 keyword（加密存储）。"""
    keyword: str = Field(min_length=1, max_length=128)


class SecretStatus(BaseModel):
    has_secret: bool
    updated_at: datetime | None
