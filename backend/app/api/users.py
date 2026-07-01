"""/api/users/* 当前用户资料 / ICBC 凭据管理。"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.crud import booking as booking_crud
from app.crud import secret as secret_crud
from app.crud import user as user_crud
from app.crud.user import BOOKING_REQUIRED_FIELDS
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
    data = payload.model_dump(exclude_unset=True)
    # 有进行中的任务时，禁止清空抢号必填字段：worker claim 会读取实时档案，
    # 若必填字段被清成 NULL，claim 组装 WorkerClaimOut 时会因非空约束 500，
    # 任务卡在 running 反复被 reaper 重排。修改成别的合法值不受影响，只挡清空。
    cleared = [
        BOOKING_REQUIRED_FIELDS[k]
        for k, v in data.items()
        if k in BOOKING_REQUIRED_FIELDS and not v
    ]
    if cleared and booking_crud.has_active(db, user.id):
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"任务进行中，不能清空：{'、'.join(cleared)}；请先取消任务再修改",
        )
    # 日期区间顺序：schema 的 _check_date_order 只能看到本次 PATCH 同时提交的两个日期。
    # 若只改其中一个，需与库中现有值合并后再校验，否则可能存成 结束 < 开始 的非法区间。
    after = data.get("expect_after_date", user.expect_after_date)
    before = data.get("expect_before_date", user.expect_before_date)
    if after is not None and before is not None and before < after:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "结束日期不能早于开始日期"
        )
    return user_crud.update_profile(db, user, **data)


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
