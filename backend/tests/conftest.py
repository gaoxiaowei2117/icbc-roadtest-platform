"""pytest 公共 fixtures。

⚠️ 关键：必须在 import 任何 app 模块**之前**设好环境变量，
让整个 app 指向独立测试库、注入临时密钥对、关闭限速与 bootstrap admin，
避免污染主库、避免限速/自动建账号干扰测试。
"""
import base64
import os

from nacl.encoding import Base64Encoder
from nacl.public import PrivateKey, SealedBox

# --- 临时密钥对（公钥给后端加密，私钥留给测试解密验证往返）---
_sk = PrivateKey.generate()
TEST_PRIVATE_KEY = _sk.encode(Base64Encoder).decode()
TEST_PUBLIC_KEY = _sk.public_key.encode(Base64Encoder).decode()

os.environ["DATABASE_URL"] = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql+psycopg://icbc:postgres@127.0.0.1:5432/icbc_test",
)
os.environ["SECRET_PUBLIC_KEY"] = TEST_PUBLIC_KEY
os.environ["JWT_SECRET"] = "test-jwt-secret"
os.environ["WORKER_API_KEY"] = "test-worker-key"
os.environ["RATE_LIMIT_ENABLED"] = "false"
os.environ["BOOTSTRAP_ADMIN_EMAIL"] = ""
os.environ["BOOTSTRAP_ADMIN_PASSWORD"] = ""

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.core.database import Base, SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402  —— 触发全部 model 注册到 Base.metadata

WORKER_HEADERS = {"X-Worker-Key": "test-worker-key"}


@pytest.fixture(scope="session", autouse=True)
def _schema():
    Base.metadata.create_all(engine)
    yield
    Base.metadata.drop_all(engine)


@pytest.fixture(autouse=True)
def _clean():
    """每个测试前清空所有表，保证测试相互独立。"""
    with engine.begin() as conn:
        conn.exec_driver_sql('TRUNCATE secret, booking, "user" RESTART IDENTITY CASCADE')
    yield


@pytest.fixture
def client() -> TestClient:
    # 不用 with：避免每个测试都触发 lifespan 启动一个 reaper 守护线程
    return TestClient(app)


@pytest.fixture
def db():
    with SessionLocal() as session:
        yield session


@pytest.fixture(autouse=True)
def _no_smtp(monkeypatch):
    monkeypatch.setattr("app.api.auth.send_verification_code", lambda *a, **k: None)


@pytest.fixture
def auth_headers(client):
    """注册并登录一个用户，返回带 Bearer token 的请求头。"""
    def _make(email: str = "user@gmail.com", password: str = "secret123") -> dict:
        client.post("/api/auth/register", json={"email": email, "password": password})
        with SessionLocal() as s:
            from app.models.user import User
            u = s.query(User).filter_by(email=email).first()
            u.email_verified = True
            s.commit()
        r = client.post("/api/auth/login", json={"email": email, "password": password})
        return {"Authorization": f"Bearer {r.json()['access_token']}"}
    return _make


@pytest.fixture
def ready_user(client, auth_headers):
    """注册 + 填资料 + 设凭据，返回 (headers, icbc_username, icbc_password)。

    这是"能建任务"的最小完整状态。
    """
    def _make(email: str = "user@gmail.com", icbc_user: str = "icbcU", icbc_pass: str = "icbcP"):
        h = auth_headers(email=email)
        client.patch("/api/users/me", headers=h, json={
            "icbc_license_no": "1234567", "icbc_last_name": "GAO",
            "exam_class": "5", "pos_ids": [1, 274],
            "expect_after_date": "2026-07-01", "expect_before_date": "2026-08-01",
            "expect_time_range": "10:00-17:00",
            "pref_days_of_week": [0, 1, 2, 3, 4], "pref_parts_of_day": [0, 1],
        })
        client.put("/api/users/me/secret", headers=h,
                   json={"keyword": f"{icbc_user}\n{icbc_pass}"})
        return h, icbc_user, icbc_pass
    return _make


@pytest.fixture
def decrypt_secret():
    """用测试私钥解密 claim 下发的密文（复现 worker 端解密）。"""
    def _decrypt(ciphertext_b64: str) -> str:
        box = SealedBox(PrivateKey(TEST_PRIVATE_KEY.encode(), encoder=Base64Encoder))
        return box.decrypt(base64.b64decode(ciphertext_b64)).decode()
    return _decrypt
