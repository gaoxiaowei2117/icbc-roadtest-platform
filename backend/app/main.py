"""FastAPI 入口。"""
import logging
import threading
import warnings
from contextlib import asynccontextmanager

# passlib 1.7.4 在 python 3.12+ 用了已废弃的 stdlib "crypt" 模块；
# 我们只用 bcrypt 不走 crypt，这条警告可安全忽略。
warnings.filterwarnings("ignore", module="passlib", message=".*crypt.*")

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.api import admin, auth, bookings, pos, users, worker
from app.core.config import get_settings
from app.core.database import SessionLocal
from app.core.ratelimit import limiter
from app.crud import booking as booking_crud
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


_reaper_stop = threading.Event()


def _reaper_loop() -> None:
    """后台守护线程：定期重置卡死的 running 任务（T2）。"""
    settings = get_settings()
    # Event.wait 返回 True 表示被 set（要退出）；False 表示超时（继续下一轮）
    while not _reaper_stop.wait(settings.reaper_interval_seconds):
        try:
            with SessionLocal() as db:
                n = booking_crud.reset_stale_running(db, settings.running_timeout_minutes)
            if n:
                logger.warning("reaper 重置了 %d 个卡死任务", n)
        except Exception:  # noqa: BLE001 — 守护线程绝不能因单次异常退出
            logger.exception("reaper 循环异常，跳过本轮")


@asynccontextmanager
async def lifespan(app: FastAPI):
    _bootstrap_admin()
    _reaper_stop.clear()
    reaper = threading.Thread(target=_reaper_loop, name="reaper", daemon=True)
    reaper.start()
    yield
    _reaper_stop.set()


settings = get_settings()
app = FastAPI(title="ICBC Road Test Platform", version="0.1.0", lifespan=lifespan)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

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
app.include_router(pos.router, prefix=settings.api_v1_prefix)
