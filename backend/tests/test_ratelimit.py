"""T10：登录/注册速率限制。

conftest 默认关闭限速（免得干扰其它测试），这里临时打开验证 429。
"""
import pytest

from app.core.ratelimit import limiter


@pytest.fixture
def rate_limit_on():
    limiter.enabled = True
    limiter.reset()
    try:
        yield
    finally:
        limiter.reset()
        limiter.enabled = False


def test_login_rate_limited(client, rate_limit_on):
    """限 5/分钟：第 6 次起返回 429。"""
    codes = [
        client.post("/api/auth/login",
                    json={"email": "nobody@gmail.com", "password": "x"}).status_code
        for _ in range(7)
    ]
    assert codes[:5] == [401] * 5      # 前 5 次正常处理（密码错）
    assert 429 in codes[5:]            # 之后被限流


def test_register_rate_limited(client, rate_limit_on):
    codes = [
        client.post("/api/auth/register",
                    json={"email": f"u{i}@gmail.com", "password": "secret123"}).status_code
        for i in range(7)
    ]
    assert 429 in codes
