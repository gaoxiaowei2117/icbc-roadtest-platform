"""用户相关的数据库操作。"""
from typing import Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.core.security import hash_password, verify_password
from app.models.user import User


def get_by_email(db: Session, email: str) -> User | None:
    return db.scalar(select(User).where(User.email == email.lower()))


def get_by_id(db: Session, user_id: int) -> User | None:
    return db.get(User, user_id)


def list_all(db: Session, limit: int = 200) -> Sequence[User]:
    stmt = (
        select(User)
        .options(joinedload(User.secret))
        .order_by(User.created_at.desc())
        .limit(limit)
    )
    return db.scalars(stmt).all()


def delete(db: Session, user: User) -> None:
    db.delete(user)
    db.commit()


def create(db: Session, email: str, password: str, is_admin: bool = False) -> User:
    user = User(
        email=email.lower(),
        password_hash=hash_password(password),
        is_admin=is_admin,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def authenticate(db: Session, email: str, password: str) -> User | None:
    user = get_by_email(db, email)
    if not user or not user.is_active:
        return None
    if not verify_password(password, user.password_hash):
        return None
    return user


# 这些字段绝不允许经 update_profile 修改（防越权 / 防篡改账号状态）。
# 是 hasattr 之外的数据层兜底：即使将来有人把它们加进 UserUpdate schema 也不会被写入。
_IMMUTABLE_FIELDS = frozenset({
    "id", "email", "password_hash", "is_admin", "is_active", "email_verified",
    "verify_code", "verify_code_expires", "created_at",
})


# 抢号任务必需的档案字段（字段名 -> 人类可读名）。ICBC keyword（secret）单独判断。
# 单一事实源：创建任务的完整性校验、有 active 任务时的清空守卫、worker claim
# 的兜底校验都用它，避免三处各写一份必填列表而漂移。
BOOKING_REQUIRED_FIELDS: dict[str, str] = {
    "icbc_license_no": "驾照号",
    "icbc_last_name": "姓氏",
    "exam_class": "考试类型",
    "pos_ids": "考点",
    "expect_after_date": "开始日期",
    "expect_before_date": "结束日期",
}


def missing_booking_fields(user: User) -> list[str]:
    """返回 user 缺失的抢号必填档案字段（人类可读名）；空列表表示齐全。"""
    return [label for field, label in BOOKING_REQUIRED_FIELDS.items() if not getattr(user, field)]


def update_profile(db: Session, user: User, **fields) -> User:
    # 调用方用 model_dump(exclude_unset=True)，因此 fields 里只有客户端显式提交的字段。
    # 显式传入的 None 表示「清空该字段」，必须写入——不能跳过 None，否则清空操作会被吞掉。
    for key, value in fields.items():
        if key in _IMMUTABLE_FIELDS:
            continue
        if hasattr(user, key):
            setattr(user, key, value)
    db.commit()
    db.refresh(user)
    return user


def set_verify_code(db: Session, user: User, code: str, expires) -> None:
    user.verify_code = code
    user.verify_code_expires = expires
    db.commit()


def mark_verified(db: Session, user: User) -> None:
    user.email_verified = True
    user.verify_code = None
    user.verify_code_expires = None
    db.commit()
