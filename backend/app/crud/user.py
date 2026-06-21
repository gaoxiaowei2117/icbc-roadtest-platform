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


def update_profile(db: Session, user: User, **fields) -> User:
    for key, value in fields.items():
        if value is not None and hasattr(user, key):
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
