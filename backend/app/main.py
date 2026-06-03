"""FastAPI 入口。"""
import logging
import warnings
from contextlib import asynccontextmanager

# passlib 1.7.4 在 python 3.12+ 用了已废弃的 stdlib "crypt" 模块；
# 我们只用 bcrypt 不走 crypt，这条警告可安全忽略。
warnings.filterwarnings("ignore", module="passlib", message=".*crypt.*")

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import admin, auth, bookings, users, worker
from app.core.config import get_settings
from app.core.database import SessionLocal
from app.crud import user as user_crud

logger = logging.getLogger("icbc")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


def _bootstrap_admin() -> None:
    """启动时如果 admin 邮箱不存在则创建。

    多实例并发时靠 email 唯一约束保护；第二个进程会撞 IntegrityError 静默吞掉。
    """
    from sqlalchemy.exc import IntegrityError
    settings = get_settings()
    if not settings.bootstrap_admin_email or not settings.bootstrap_admin_password:
        return
    email = settings.bootstrap_admin_email.lower()
    with SessionLocal() as db:
        if user_crud.get_by_email(db, email) is not None:
            return
        try:
            user = user_crud.create(db, email, settings.bootstrap_admin_password, is_admin=True)
        except IntegrityError:
            logger.info("bootstrap admin 已被其他实例创建，跳过")
            return
        logger.warning("已创建 bootstrap admin 账号：%s（id=%d）", user.email, user.id)


@asynccontextmanager
async def lifespan(app: FastAPI):
    _bootstrap_admin()
    yield


settings = get_settings()
app = FastAPI(title="ICBC Road Test Platform", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


app.include_router(auth.router, prefix=settings.api_v1_prefix)
app.include_router(users.router, prefix=settings.api_v1_prefix)
app.include_router(bookings.router, prefix=settings.api_v1_prefix)
app.include_router(worker.router, prefix=settings.api_v1_prefix)
app.include_router(admin.router, prefix=settings.api_v1_prefix)
