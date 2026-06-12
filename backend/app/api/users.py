"""/api/users/* 当前用户资料 / ICBC 凭据管理。"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.crud import secret as secret_crud
from app.crud import user as user_crud
from app.models.user import User
from app.schemas.user import SecretIn, SecretStatus, UserPublic, UserUpdate

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me", response_model=UserPublic)
def get_me(user: User = Depends(get_current_user)) -> User:
    return user


@router.patch("/me", response_model=UserPublic)
def update_me(
    payload: UserUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> User:
    return user_crud.update_profile(db, user, **payload.model_dump(exclude_unset=True))


@router.put("/me/secret", response_model=SecretStatus)
def set_secret(
    payload: SecretIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SecretStatus:
    secret = secret_crud.upsert(db, user, payload.keyword)
    return SecretStatus(has_secret=True, updated_at=secret.updated_at)


@router.delete("/me/secret", status_code=status.HTTP_204_NO_CONTENT)
def delete_secret(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    if user.secret is not None:
        db.delete(user.secret)
        db.commit()


@router.get("/me/secret", response_model=SecretStatus)
def get_secret_status(user: User = Depends(get_current_user)) -> SecretStatus:
    if user.secret is None:
        return SecretStatus(has_secret=False, updated_at=None)
    return SecretStatus(has_secret=True, updated_at=user.secret.updated_at)
