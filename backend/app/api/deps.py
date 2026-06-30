"""鉴权依赖：当前用户 / admin / worker。"""
import hmac

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import get_db
from app.core.security import decode_token
from app.crud import user as user_crud
from app.models.user import User

settings = get_settings()
bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    creds: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    if creds is None or creds.scheme.lower() != "bearer":
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "缺少 token")
    user_id = decode_token(creds.credentials, "access")
    if user_id is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "token 无效或已过期")
    user = user_crud.get_by_id(db, user_id)
    if user is None or not user.is_active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "用户不存在或已停用")
    return user


def get_admin_user(user: User = Depends(get_current_user)) -> User:
    if not user.is_admin:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "需要 admin 权限")
    return user


def require_worker_key(api_key: str) -> None:
    """校验 worker 共享密钥（常数时间比较，避免时序侧信道）。"""
    expected = settings.worker_api_key
    if not expected or not hmac.compare_digest(api_key, expected):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "worker key 无效")
