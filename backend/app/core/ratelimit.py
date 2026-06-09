"""共享的 slowapi Limiter（T10）。

单独成模块，避免 main.py 与 auth.py 互相 import 产生环依赖。
按客户端 IP 限流；生产经 nginx 反代时需配 `X-Forwarded-For` 才能拿到真实 IP。
"""
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.core.config import get_settings

settings = get_settings()

limiter = Limiter(key_func=get_remote_address, enabled=settings.rate_limit_enabled)
