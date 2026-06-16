# 注册邮箱验证 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 注册时强制邮箱验证——发 6 位验证码、未验证不能登录、验证后才发 token，前端独立验证页。

**Architecture:** user 加 `email_verified`/`verify_code`/`verify_code_expires`；新增 `core/email.py`（smtplib 同步发信，复用系统 Gmail SMTP）；auth 端点改 register/verify-email/resend-code/login；前端加验证页。测试全程 mock SMTP。

**Tech Stack:** FastAPI、SQLAlchemy、alembic、pydantic、smtplib、pytest、Vue 3 + TS。

**说明：**
- 设计见 `docs/superpowers/specs/2026-06-16-email-verification-design.md`。
- 后端测试库 icbc_test；命令 `cd backend && .venv/bin/python -m pytest -q`。前端 `cd frontend && npm run build`。
- ⚠️ 与 spec 的一处调整：`verify-email` 对**已验证**邮箱返回 400"请直接登录"，**不发 token**（避免无密码绕过登录）。

---

## 文件结构

| 文件 | 动作 | 责任 |
|---|---|---|
| `backend/app/models/user.py` | 改 | 加 email_verified/verify_code/verify_code_expires |
| `backend/alembic/versions/0003_email_verify.py` | 新 | 迁移 |
| `backend/app/core/config.py` | 改 | SMTP 配置项 |
| `backend/app/core/email.py` | 新 | send_email / send_verification_code |
| `backend/app/schemas/auth.py` | 改 | RegisterOut/VerifyEmailIn/ResendCodeIn/MessageOut |
| `backend/app/crud/user.py` | 改 | set_verify_code / mark_verified |
| `backend/app/api/auth.py` | 改 | register/verify-email/resend-code/login |
| `backend/tests/conftest.py` | 改 | mock SMTP + auth_headers 适配（注册后置 verified） |
| `backend/tests/test_auth.py` | 改 | 邮箱验证用例 |
| `backend/tests/test_email.py` | 新 | email 模块单测 |
| `frontend/src/stores/auth.ts` | 改 | register/verifyEmail/resendCode |
| `frontend/src/views/VerifyEmail.vue` | 新 | 验证页 |
| `frontend/src/router/index.ts` | 改 | /verify 路由 |
| `frontend/src/views/Register.vue` | 改 | 注册后跳验证页 |
| `frontend/src/views/Login.vue` | 改 | 未验证引导 |

---

## Task 1: 数据模型 + 迁移 0003

**Files:**
- Modify: `backend/app/models/user.py`
- Create: `backend/alembic/versions/0003_email_verify.py`

- [ ] **Step 1: 改 user model**

在 `backend/app/models/user.py` 的 `is_admin` 字段之后加：
```python
    email_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    verify_code: Mapped[str | None] = mapped_column(String(6))
    verify_code_expires: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
```
（`Boolean`/`String`/`DateTime`/`datetime` 都已 import。）

- [ ] **Step 2: 写迁移**

Create `backend/alembic/versions/0003_email_verify.py`:
```python
"""email verification: user 加 email_verified/verify_code/verify_code_expires

Revision ID: 0003_email_verify
Revises: 0002_multiuser_profile
Create Date: 2026-06-16
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0003_email_verify"
down_revision: Union[str, None] = "0002_multiuser_profile"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("user", sa.Column("email_verified", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("user", sa.Column("verify_code", sa.String(6)))
    op.add_column("user", sa.Column("verify_code_expires", sa.DateTime(timezone=True)))


def downgrade() -> None:
    op.drop_column("user", "verify_code_expires")
    op.drop_column("user", "verify_code")
    op.drop_column("user", "email_verified")
```

- [ ] **Step 3: 验证 model import + 迁移语法**

Run:
```bash
cd /home/xgao/workspace/icbc-roadtest-platform/backend
.venv/bin/python -c "from app.main import app; print('models OK')"
.venv/bin/python -c "import ast; ast.parse(open('alembic/versions/0003_email_verify.py').read()); print('migration OK')"
DATABASE_URL=postgresql+psycopg://icbc:postgres@127.0.0.1:5432/icbc_test .venv/bin/alembic upgrade head 2>&1 | tail -2
```
Expected: `models OK`、`migration OK`、alembic 输出含 `0002_multiuser_profile -> 0003_email_verify`（若 icbc_test 是 create_all 维护的库导致 alembic 冲突，只需 model/迁移语法正确即可，如实报告）。

- [ ] **Step 4: Commit**

```bash
cd /home/xgao/workspace/icbc-roadtest-platform
git add backend/app/models/user.py backend/alembic/versions/0003_email_verify.py
git commit -m "backend: user 加邮箱验证字段（迁移 0003）"
```

---

## Task 2: SMTP 配置 + email 模块（TDD）

**Files:**
- Modify: `backend/app/core/config.py`
- Create: `backend/app/core/email.py`
- Test: `backend/tests/test_email.py`

- [ ] **Step 1: 加 SMTP 配置**

在 `backend/app/core/config.py` 的 `Settings` 类里（`worker_api_key` 附近）加：
```python
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = ""
```

- [ ] **Step 2: 写失败测试**

Create `backend/tests/test_email.py`:
```python
from unittest.mock import MagicMock, patch

from app.core import email


def test_send_email_uses_smtp(monkeypatch):
    monkeypatch.setattr(email.settings, "smtp_user", "sys@gmail.com")
    monkeypatch.setattr(email.settings, "smtp_password", "pw")
    smtp = MagicMock()
    with patch("app.core.email.smtplib.SMTP") as smtp_cls:
        smtp_cls.return_value.__enter__.return_value = smtp
        email.send_email("u@x.com", "subj", "body")
    smtp.starttls.assert_called_once()
    smtp.login.assert_called_once_with("sys@gmail.com", "pw")
    smtp.send_message.assert_called_once()


def test_send_email_requires_config(monkeypatch):
    monkeypatch.setattr(email.settings, "smtp_user", "")
    import pytest
    with pytest.raises(ValueError):
        email.send_email("u@x.com", "s", "b")


def test_send_verification_code_calls_send_email():
    with patch("app.core.email.send_email") as send:
        email.send_verification_code("u@x.com", "123456")
    send.assert_called_once()
    args = send.call_args[0]
    assert args[0] == "u@x.com"
    assert "123456" in args[2]
```

- [ ] **Step 3: 运行确认失败**

Run: `cd backend && .venv/bin/python -m pytest tests/test_email.py -v`
Expected: FAIL（`No module named 'app.core.email'`）

- [ ] **Step 4: 写 email 模块**

Create `backend/app/core/email.py`:
```python
"""邮件发送（smtplib 同步，复用系统 Gmail SMTP）。"""
import smtplib
from email.message import EmailMessage

from app.core.config import get_settings

settings = get_settings()


def send_email(to: str, subject: str, body: str) -> None:
    if not settings.smtp_user:
        raise ValueError("SMTP 未配置：请在 .env 设置 SMTP_USER/SMTP_PASSWORD")
    msg = EmailMessage()
    msg["From"] = settings.smtp_from or settings.smtp_user
    msg["To"] = to
    msg["Subject"] = subject
    msg.set_content(body)
    with smtplib.SMTP(settings.smtp_host, settings.smtp_port) as s:
        s.starttls()
        s.login(settings.smtp_user, settings.smtp_password)
        s.send_message(msg)


def send_verification_code(to: str, code: str) -> None:
    send_email(
        to,
        "ICBC 抢号平台 — 邮箱验证码",
        f"你的验证码是 {code}，10 分钟内有效。如非本人操作请忽略。",
    )
```

- [ ] **Step 5: 运行确认通过**

Run: `cd backend && .venv/bin/python -m pytest tests/test_email.py -v`
Expected: 3 passed

- [ ] **Step 6: Commit**

```bash
cd /home/xgao/workspace/icbc-roadtest-platform
git add backend/app/core/config.py backend/app/core/email.py backend/tests/test_email.py
git commit -m "backend: SMTP 配置 + email 发送模块"
```

---

## Task 3: auth schema + user crud helpers

**Files:**
- Modify: `backend/app/schemas/auth.py`
- Modify: `backend/app/crud/user.py`

- [ ] **Step 1: 加 auth schema**

在 `backend/app/schemas/auth.py` 末尾加：
```python
class RegisterOut(BaseModel):
    message: str


class VerifyEmailIn(BaseModel):
    email: EmailStr
    code: str = Field(min_length=6, max_length=6)


class ResendCodeIn(BaseModel):
    email: EmailStr


class MessageOut(BaseModel):
    message: str
```

- [ ] **Step 2: 加 user crud helpers**

在 `backend/app/crud/user.py` 末尾加：
```python
def set_verify_code(db: Session, user: User, code: str, expires) -> None:
    user.verify_code = code
    user.verify_code_expires = expires
    db.commit()


def mark_verified(db: Session, user: User) -> None:
    user.email_verified = True
    user.verify_code = None
    user.verify_code_expires = None
    db.commit()
```
（`Session`/`User` 已 import；`expires` 是 datetime，由调用方传。）

- [ ] **Step 3: 验证 import**

Run: `cd backend && .venv/bin/python -c "from app.schemas.auth import RegisterOut, VerifyEmailIn, ResendCodeIn, MessageOut; from app.crud.user import set_verify_code, mark_verified; print('OK')"`
Expected: `OK`

- [ ] **Step 4: Commit**

```bash
cd /home/xgao/workspace/icbc-roadtest-platform
git add backend/app/schemas/auth.py backend/app/crud/user.py
git commit -m "backend: 邮箱验证 schema + user crud helpers"
```

---

## Task 4: auth 端点 + conftest 适配 + 测试（TDD）

**Files:**
- Modify: `backend/app/api/auth.py`
- Modify: `backend/tests/conftest.py`
- Modify: `backend/tests/test_auth.py`

- [ ] **Step 1: conftest 加 mock SMTP + 适配 auth_headers**

在 `backend/tests/conftest.py`：
1. 加一个 autouse fixture 全局 mock 发邮件（避免真发 + 注册不阻塞）：
```python
@pytest.fixture(autouse=True)
def _no_smtp(monkeypatch):
    monkeypatch.setattr("app.core.email.send_email", lambda *a, **k: None)
```
2. 改 `auth_headers` fixture：注册后直接在 DB 置 `email_verified=True` 再登录（跳过验证码流程，保持其它测试不受邮件流程拖累）。把 `auth_headers` 的 `_make` 改为：
```python
    def _make(email: str = "user@gmail.com", password: str = "secret123") -> dict:
        client.post("/api/auth/register", json={"email": email, "password": password})
        with SessionLocal() as s:
            from app.models.user import User
            u = s.query(User).filter_by(email=email).first()
            u.email_verified = True
            s.commit()
        r = client.post("/api/auth/login", json={"email": email, "password": password})
        return {"Authorization": f"Bearer {r.json()['access_token']}"}
```
（`SessionLocal` 已在 conftest import；若未导入，从 `app.core.database import SessionLocal`。）

- [ ] **Step 2: 写/改 test_auth 用例**

把 `backend/tests/test_auth.py` 中依赖"register 直接返回 token"的用例改掉，并加邮箱验证用例。目标用例集（整体替换 test_auth.py 为以下内容）：
```python
"""auth flow：注册发码 / 邮箱验证 / 登录需已验证 / 刷新。"""
from app.models.user import User


def _register(client, email="a@gmail.com", password="secret123"):
    return client.post("/api/auth/register", json={"email": email, "password": password})


def _code(db, email):
    return db.query(User).filter_by(email=email).first().verify_code


def test_register_sends_code_no_token(client, db):
    r = _register(client)
    assert r.status_code == 201
    assert "access_token" not in r.json()
    u = db.query(User).filter_by(email="a@gmail.com").first()
    assert u.email_verified is False
    assert u.verify_code and len(u.verify_code) == 6


def test_register_duplicate_conflict(client):
    _register(client)
    assert _register(client).status_code == 409


def test_login_blocked_before_verify(client):
    _register(client)
    r = client.post("/api/auth/login", json={"email": "a@gmail.com", "password": "secret123"})
    assert r.status_code == 403


def test_verify_email_then_login(client, db):
    _register(client)
    code = _code(db, "a@gmail.com")
    r = client.post("/api/auth/verify-email", json={"email": "a@gmail.com", "code": code})
    assert r.status_code == 200
    assert r.json()["access_token"]
    db.expire_all()
    assert db.query(User).filter_by(email="a@gmail.com").first().email_verified is True
    # 验证后能登录
    assert client.post("/api/auth/login",
                       json={"email": "a@gmail.com", "password": "secret123"}).status_code == 200


def test_verify_wrong_code(client):
    _register(client)
    r = client.post("/api/auth/verify-email", json={"email": "a@gmail.com", "code": "000000"})
    assert r.status_code == 400


def test_verify_already_verified_rejected(client, db):
    _register(client)
    code = _code(db, "a@gmail.com")
    client.post("/api/auth/verify-email", json={"email": "a@gmail.com", "code": code})
    # 再 verify → 400 提示去登录（不发 token）
    r = client.post("/api/auth/verify-email", json={"email": "a@gmail.com", "code": code})
    assert r.status_code == 400


def test_resend_code(client, db):
    _register(client)
    old = _code(db, "a@gmail.com")
    r = client.post("/api/auth/resend-code", json={"email": "a@gmail.com"})
    assert r.status_code == 200
    db.expire_all()
    assert _code(db, "a@gmail.com") is not None  # 新码已生成
    # 对不存在邮箱也返回同样消息（防枚举）
    r2 = client.post("/api/auth/resend-code", json={"email": "nobody@gmail.com"})
    assert r2.status_code == 200


def test_me_requires_auth(client):
    assert client.get("/api/users/me").status_code == 401
```

- [ ] **Step 3: 运行确认失败**

Run: `cd backend && .venv/bin/python -m pytest tests/test_auth.py -v`
Expected: FAIL（register 仍返回 token、无 verify-email 端点等）

- [ ] **Step 4: 改 auth 端点**

把 `backend/app/api/auth.py` 整体替换为：
```python
"""/api/auth/* 注册 / 邮箱验证 / 登录 / 刷新。"""
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import get_db
from app.core.email import send_verification_code
from app.core.ratelimit import limiter
from app.core.security import create_access_token, create_refresh_token, decode_token
from app.crud import user as user_crud
from app.schemas.auth import (
    AccessTokenOut, LoginIn, MessageOut, RefreshIn, RegisterIn, RegisterOut,
    ResendCodeIn, TokenOut, VerifyEmailIn,
)

router = APIRouter(prefix="/auth", tags=["auth"])
_auth_limit = get_settings().auth_rate_limit
_CODE_TTL_MIN = 10


def _gen_code() -> str:
    return f"{secrets.randbelow(1000000):06d}"


def _issue_code(db: Session, user) -> None:
    code = _gen_code()
    expires = datetime.now(timezone.utc) + timedelta(minutes=_CODE_TTL_MIN)
    user_crud.set_verify_code(db, user, code, expires)
    send_verification_code(user.email, code)


@router.post("/register", response_model=RegisterOut, status_code=status.HTTP_201_CREATED)
@limiter.limit(_auth_limit)
def register(request: Request, payload: RegisterIn, db: Session = Depends(get_db)) -> RegisterOut:
    if user_crud.get_by_email(db, payload.email):
        raise HTTPException(status.HTTP_409_CONFLICT, "邮箱已注册")
    user = user_crud.create(db, payload.email, payload.password, is_admin=False)
    _issue_code(db, user)
    return RegisterOut(message="验证码已发送到邮箱，请查收并验证")


@router.post("/verify-email", response_model=TokenOut)
@limiter.limit(_auth_limit)
def verify_email(request: Request, payload: VerifyEmailIn, db: Session = Depends(get_db)) -> TokenOut:
    user = user_crud.get_by_email(db, payload.email)
    if user is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "验证码错误或已过期")
    if user.email_verified:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "邮箱已验证，请直接登录")
    now = datetime.now(timezone.utc)
    if (user.verify_code != payload.code or user.verify_code_expires is None
            or user.verify_code_expires < now):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "验证码错误或已过期")
    user_crud.mark_verified(db, user)
    return TokenOut(
        access_token=create_access_token(user.id),
        refresh_token=create_refresh_token(user.id),
    )


@router.post("/resend-code", response_model=MessageOut)
@limiter.limit(_auth_limit)
def resend_code(request: Request, payload: ResendCodeIn, db: Session = Depends(get_db)) -> MessageOut:
    user = user_crud.get_by_email(db, payload.email)
    if user is not None and not user.email_verified:
        _issue_code(db, user)
    return MessageOut(message="若该邮箱已注册且未验证，验证码已重新发送")


@router.post("/login", response_model=TokenOut)
@limiter.limit(_auth_limit)
def login(request: Request, payload: LoginIn, db: Session = Depends(get_db)) -> TokenOut:
    user = user_crud.authenticate(db, payload.email, payload.password)
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "邮箱或密码错误")
    if not user.email_verified:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "邮箱未验证，请先验证")
    return TokenOut(
        access_token=create_access_token(user.id),
        refresh_token=create_refresh_token(user.id),
    )


@router.post("/refresh", response_model=AccessTokenOut)
def refresh(payload: RefreshIn, db: Session = Depends(get_db)) -> AccessTokenOut:
    user_id = decode_token(payload.refresh_token, "refresh")
    if user_id is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "refresh token 无效")
    user = user_crud.get_by_id(db, user_id)
    if user is None or not user.is_active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "用户不存在")
    return AccessTokenOut(access_token=create_access_token(user.id))
```

- [ ] **Step 5: 运行确认通过**

Run: `cd backend && .venv/bin/python -m pytest tests/test_auth.py -v`
Expected: 全部 PASS（8 个用例）

- [ ] **Step 6: Commit**

```bash
cd /home/xgao/workspace/icbc-roadtest-platform
git add backend/app/api/auth.py backend/tests/conftest.py backend/tests/test_auth.py
git commit -m "backend: 注册发码 + verify-email + login 拒未验证 + 测试"
```

---

## Task 5: 前端 auth store + api

**Files:**
- Modify: `frontend/src/stores/auth.ts`

- [ ] **Step 1: 改 auth store**

在 `frontend/src/stores/auth.ts`：
1. `register` 改为不存 token（注册只发码，跳验证页由组件处理）：
```typescript
  async function register(email: string, password: string) {
    await axios.post('/api/auth/register', { email, password })
  }
```
2. 新增 `verifyEmail` / `resendCode`：
```typescript
  async function verifyEmail(email: string, code: string) {
    const r = await axios.post('/api/auth/verify-email', { email, code })
    setTokens(r.data.access_token, r.data.refresh_token)
    await fetchMe()
  }

  async function resendCode(email: string) {
    await axios.post('/api/auth/resend-code', { email })
  }
```
3. 把 `verifyEmail`/`resendCode` 加进 store 的 return。

- [ ] **Step 2: 类型检查**

Run: `cd /home/xgao/workspace/icbc-roadtest-platform/frontend && npx vue-tsc --noEmit 2>&1 | head -20`
Expected: 仅 Register.vue（仍调旧 register 后 push dashboard）可能无类型错（register 现在返回 void，Register.vue 的 `await auth.register` 仍合法）——确认 store 自身无类型错。

- [ ] **Step 3: Commit**

```bash
cd /home/xgao/workspace/icbc-roadtest-platform
git add frontend/src/stores/auth.ts
git commit -m "frontend: auth store 加 verifyEmail/resendCode，register 不存 token"
```

---

## Task 6: 前端验证页 + 路由 + Register/Login 改

**Files:**
- Create: `frontend/src/views/VerifyEmail.vue`
- Modify: `frontend/src/router/index.ts`
- Modify: `frontend/src/views/Register.vue`
- Modify: `frontend/src/views/Login.vue`

- [ ] **Step 1: 建 VerifyEmail.vue**

Create `frontend/src/views/VerifyEmail.vue`:
```vue
<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()

const email = ref((route.query.email as string) || '')
const code = ref('')
const cooldown = ref(0)
let timer: number | undefined

async function onVerify() {
  if (!/^[0-9]{6}$/.test(code.value)) {
    alert('请输入 6 位验证码')
    return
  }
  try {
    await auth.verifyEmail(email.value, code.value)
    alert('验证成功')
    router.push('/dashboard')
  } catch (e: any) {
    alert('验证失败：' + (e.response?.data?.detail || '未知错误'))
  }
}

function startCooldown() {
  cooldown.value = 60
  timer = window.setInterval(() => {
    cooldown.value -= 1
    if (cooldown.value <= 0 && timer) window.clearInterval(timer)
  }, 1000)
}

async function onResend() {
  try {
    await auth.resendCode(email.value)
    alert('验证码已重新发送')
    startCooldown()
  } catch (e: any) {
    alert('发送失败：' + (e.response?.data?.detail || '未知错误'))
  }
}

onMounted(() => { if (email.value) startCooldown() })
</script>

<template>
  <div class="max-w-md mx-auto mt-20">
    <div class="card space-y-4">
      <h1 class="text-2xl font-bold text-center">验证邮箱</h1>
      <p class="text-sm text-slate-600 text-center">验证码已发送到 {{ email }}，10 分钟内有效。</p>
      <div>
        <label class="label">邮箱</label>
        <input v-model="email" type="email" class="input" />
      </div>
      <div>
        <label class="label">6 位验证码</label>
        <input v-model="code" maxlength="6" class="input" />
      </div>
      <button class="btn-primary w-full" @click="onVerify">验证</button>
      <button class="btn-secondary w-full" :disabled="cooldown > 0" @click="onResend">
        {{ cooldown > 0 ? `重发（${cooldown}s）` : '重发验证码' }}
      </button>
      <p class="text-sm text-center text-slate-600">
        <RouterLink to="/login" class="text-blue-600 hover:underline">返回登录</RouterLink>
      </p>
    </div>
  </div>
</template>
```

- [ ] **Step 2: 加 /verify 路由**

在 `frontend/src/router/index.ts` 的 `routes` 数组里、`register` 路由之后加：
```typescript
    {
      path: '/verify',
      name: 'verify',
      component: () => import('@/views/VerifyEmail.vue'),
      meta: { guest: true },
    },
```

- [ ] **Step 3: 改 Register.vue 跳验证页**

把 `frontend/src/views/Register.vue` 的 `onSubmit` 里：
```typescript
    await auth.register(email.value, password.value)
    router.push('/dashboard')
```
改为：
```typescript
    await auth.register(email.value, password.value)
    router.push({ name: 'verify', query: { email: email.value } })
```

- [ ] **Step 4: 改 Login.vue 未验证引导**

先读 `frontend/src/views/Login.vue`。在登录失败的 catch 里，若是 403（邮箱未验证），引导去验证页。把 catch 改为：
```typescript
  } catch (e: any) {
    if (e.response?.status === 403) {
      if (confirm('邮箱未验证，是否前往验证？')) {
        router.push({ name: 'verify', query: { email: email.value } })
      }
    } else {
      error.value = e.response?.data?.detail || '登录失败'
    }
  }
```
（若 Login.vue 没有 `router`，从 `vue-router` import `useRouter` 并 `const router = useRouter()`；保留其它逻辑。）

- [ ] **Step 5: 构建验证**

Run: `cd /home/xgao/workspace/icbc-roadtest-platform/frontend && npm run build 2>&1 | tail -15`
Expected: vue-tsc 无错误，vite build 成功。若报错按提示修。

- [ ] **Step 6: Commit**

```bash
cd /home/xgao/workspace/icbc-roadtest-platform
git add frontend/src/views/VerifyEmail.vue frontend/src/router/index.ts frontend/src/views/Register.vue frontend/src/views/Login.vue
git commit -m "frontend: 邮箱验证页 + 路由 + 注册跳验证 + 登录未验证引导"
```

---

## Task 7: 全栈回归 + 运维说明

**Files:**
- Modify: `deploy/env.example`

- [ ] **Step 1: 全量后端回归**

Run:
```bash
cd /home/xgao/workspace/icbc-roadtest-platform/backend && .venv/bin/python -m pytest -q
```
Expected: 全部 passed（含 test_email 3 + test_auth 8 + 其它）。若某测试因新 auth 流程挂掉（多半是某处直接 register 后用 token），按 conftest 的 auth_headers 模式修（注册后置 verified 再 login）。

- [ ] **Step 2: 前端构建**

Run: `cd /home/xgao/workspace/icbc-roadtest-platform/frontend && npm run build 2>&1 | tail -5`
Expected: build 成功。

- [ ] **Step 3: deploy/env.example 补 SMTP**

在 `deploy/env.example` 的安全密钥段之后加：
```
# ===== 邮箱验证 SMTP（复用系统 Gmail，应用专用密码）=====
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=system-icbc@gmail.com
SMTP_PASSWORD=your 16char app password
SMTP_FROM=system-icbc@gmail.com
```

- [ ] **Step 4: Commit**

```bash
cd /home/xgao/workspace/icbc-roadtest-platform
git add deploy/env.example
git commit -m "docs: deploy env 补 SMTP 配置 + 邮箱验证全栈回归通过"
```

---

## 验收标准

- [ ] 注册返回 message、不返回 token；DB 存了 6 位码。
- [ ] 未验证登录 → 403；正确码验证 → 激活 + 发 token；错码/过期 → 400；已验证再验证 → 400。
- [ ] resend 重发新码、对不存在邮箱同样回应（防枚举）。
- [ ] 前端：注册 → 验证页 → 输码 → 进面板；重发倒计时；登录未验证有引导。
- [ ] 后端全量 pytest 绿（mock SMTP）；前端 build 通过。
- [ ] deploy/env.example 有 SMTP_*。

## 后续（不在本计划）

- 修改注册邮箱流程（YAGNI）。
- 同步 SMTP → 异步队列（上规模再说）。
