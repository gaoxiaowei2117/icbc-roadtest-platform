# 多用户化 — 后端实现计划（计划 1/3）

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 后端数据模型与 API 改造，让 user 存完整抢号档案、secret 存 keyword、claim 下发完整档案，为"网页驱动抢号"打底。

**Architecture:** user 表加 7 个抢号档案字段、删 3 个旧字段；booking 简化为纯触发器；secret 语义改为存 keyword（加密链路不变）；新增 pos-list 字典 API；claim 扩展返回完整档案。

**Tech Stack:** FastAPI、SQLAlchemy 2.0、alembic、pydantic v2、pytest、PostgreSQL（测试库 icbc_test）。

**总体说明：**
- 设计见 `docs/superpowers/specs/2026-06-10-multiuser-web-driven-booking-design.md`。
- 这是 3 个计划的第 1 个（后端）。worker、前端是后续计划。
- 现有库是测试数据，迁移直接重建结构，不写数据搬迁。
- 测试命令：`cd backend && .venv/bin/python -m pytest -q`（测试库 icbc_test 已存在）。

---

## 文件结构

| 文件 | 动作 | 责任 |
|---|---|---|
| `backend/app/models/user.py` | 改 | user 加 7 档案字段、删 3 旧字段 |
| `backend/app/models/booking.py` | 改 | 删 target_date/time_window/pos_code |
| `backend/alembic/versions/0002_multiuser_profile.py` | 新 | 迁移：user/booking 列变更 |
| `backend/app/schemas/user.py` | 改 | UserPublic/UserUpdate 加档案字段；SecretIn 改 keyword |
| `backend/app/schemas/booking.py` | 改 | BookingCreate/Out 简化；WorkerClaimOut 扩展 |
| `backend/app/crud/secret.py` | 改 | upsert 存 keyword（单值） |
| `backend/app/data/icbc_pos_list.csv` | 新 | 考点字典（复制自 auto-booking） |
| `backend/app/api/pos.py` | 新 | GET /api/pos-list |
| `backend/app/api/users.py` | 改 | secret 端点改 keyword |
| `backend/app/api/bookings.py` | 改 | 前置校验改档案完整性 |
| `backend/app/api/worker.py` | 改 | claim 构造扩展 WorkerClaimOut |
| `backend/app/main.py` | 改 | 注册 pos 路由 |
| `backend/tests/*` | 改 | 更新 fixtures 与用例 |

---

## Task 1: 数据模型 + 迁移

**Files:**
- Modify: `backend/app/models/user.py`
- Modify: `backend/app/models/booking.py`
- Create: `backend/alembic/versions/0002_multiuser_profile.py`

- [ ] **Step 1: 改 user model**

把 `backend/app/models/user.py` 中这三行：
```python
    preferred_pos: Mapped[list[str] | None] = mapped_column(JSON)
    time_windows: Mapped[dict | None] = mapped_column(JSON)
    max_wait_days: Mapped[int] = mapped_column(Integer, default=60, nullable=False)
```
替换为：
```python
    exam_class: Mapped[str | None] = mapped_column(String(10))
    pos_ids: Mapped[list[int] | None] = mapped_column(JSON)
    expect_after_date: Mapped[date | None] = mapped_column(Date)
    expect_before_date: Mapped[date | None] = mapped_column(Date)
    expect_time_range: Mapped[str | None] = mapped_column(String(20))
    pref_days_of_week: Mapped[list[int] | None] = mapped_column(JSON)
    pref_parts_of_day: Mapped[list[int] | None] = mapped_column(JSON)
```
并在文件顶部 import 加上 `Date` 和 `date`：把 `from sqlalchemy import Boolean, DateTime, Integer, String, func` 改为 `from sqlalchemy import Boolean, Date, DateTime, Integer, String, func`，把 `from datetime import datetime` 改为 `from datetime import date, datetime`。

- [ ] **Step 2: 改 booking model**

在 `backend/app/models/booking.py` 删除这三行（target_date / time_window / pos_code 字段定义）：
```python
    target_date: Mapped[date | None] = mapped_column(Date)
    time_window: Mapped[dict | None] = mapped_column(JSON)
    pos_code: Mapped[str | None] = mapped_column(String(50))
```
其余字段（status/attempt_count/last_error/result/started_at/finished_at/时间戳）保留不动。若删后 `Date`/`JSON`/`String` 有未使用 import，一并清理（保留 `result` 用的 JSON、其它列用到的类型）。

- [ ] **Step 3: 写迁移**

Create `backend/alembic/versions/0002_multiuser_profile.py`:
```python
"""multiuser profile: user 档案字段重构 + booking 简化

Revision ID: 0002_multiuser_profile
Revises: 0001_initial
Create Date: 2026-06-10
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0002_multiuser_profile"
down_revision: Union[str, None] = "0001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # user: 删旧档案字段
    op.drop_column("user", "preferred_pos")
    op.drop_column("user", "time_windows")
    op.drop_column("user", "max_wait_days")
    # user: 加新档案字段
    op.add_column("user", sa.Column("exam_class", sa.String(10)))
    op.add_column("user", sa.Column("pos_ids", sa.JSON()))
    op.add_column("user", sa.Column("expect_after_date", sa.Date()))
    op.add_column("user", sa.Column("expect_before_date", sa.Date()))
    op.add_column("user", sa.Column("expect_time_range", sa.String(20)))
    op.add_column("user", sa.Column("pref_days_of_week", sa.JSON()))
    op.add_column("user", sa.Column("pref_parts_of_day", sa.JSON()))
    # booking: 删参数字段（已移到 user 档案）
    op.drop_column("booking", "target_date")
    op.drop_column("booking", "time_window")
    op.drop_column("booking", "pos_code")


def downgrade() -> None:
    op.add_column("booking", sa.Column("pos_code", sa.String(50)))
    op.add_column("booking", sa.Column("time_window", sa.JSON()))
    op.add_column("booking", sa.Column("target_date", sa.Date()))
    op.drop_column("user", "pref_parts_of_day")
    op.drop_column("user", "pref_days_of_week")
    op.drop_column("user", "expect_time_range")
    op.drop_column("user", "expect_before_date")
    op.drop_column("user", "expect_after_date")
    op.drop_column("user", "pos_ids")
    op.drop_column("user", "exam_class")
    op.add_column("user", sa.Column("max_wait_days", sa.Integer(), nullable=False, server_default="60"))
    op.add_column("user", sa.Column("time_windows", sa.JSON()))
    op.add_column("user", sa.Column("preferred_pos", sa.JSON()))
```

- [ ] **Step 4: 应用迁移到测试库 + 验证 model import**

Run:
```bash
cd /home/xgao/workspace/icbc-roadtest-platform/backend
.venv/bin/python -c "from app.main import app; print('models import OK')"
DATABASE_URL=postgresql+psycopg://icbc:postgres@127.0.0.1:5432/icbc_test .venv/bin/alembic upgrade head
```
Expected: `models import OK`，alembic 输出 `Running upgrade 0001_initial -> 0002_multiuser_profile`。

- [ ] **Step 5: Commit**

```bash
cd /home/xgao/workspace/icbc-roadtest-platform
git add backend/app/models/user.py backend/app/models/booking.py backend/alembic/versions/0002_multiuser_profile.py
git commit -m "backend: user 档案字段重构 + booking 简化（迁移 0002）"
```

---

## Task 2: schema 更新

**Files:**
- Modify: `backend/app/schemas/user.py`
- Modify: `backend/app/schemas/booking.py`

- [ ] **Step 1: 改 user schema**

把 `backend/app/schemas/user.py` 整体替换为：
```python
"""用户资料 schema。"""
from datetime import date, datetime
from pydantic import BaseModel, ConfigDict, EmailStr, Field


class ProfileFields(BaseModel):
    """抢号档案字段（UserPublic 与 UserUpdate 共用形状）。"""
    icbc_license_no: str | None = None
    icbc_last_name: str | None = None
    exam_class: str | None = None
    pos_ids: list[int] | None = None
    expect_after_date: date | None = None
    expect_before_date: date | None = None
    expect_time_range: str | None = None
    pref_days_of_week: list[int] | None = None
    pref_parts_of_day: list[int] | None = None


class UserPublic(ProfileFields):
    model_config = ConfigDict(from_attributes=True)
    id: int
    email: EmailStr
    is_admin: bool
    created_at: datetime


class UserUpdate(ProfileFields):
    icbc_license_no: str | None = Field(default=None, max_length=50)
    icbc_last_name: str | None = Field(default=None, max_length=100)
    exam_class: str | None = Field(default=None, max_length=10)
    expect_time_range: str | None = Field(default=None, max_length=20)


class SecretIn(BaseModel):
    """用户提交 ICBC 登录 keyword（加密存储）。"""
    keyword: str = Field(min_length=1, max_length=128)


class SecretStatus(BaseModel):
    has_secret: bool
    updated_at: datetime | None
```

- [ ] **Step 2: 改 booking schema**

把 `backend/app/schemas/booking.py` 整体替换为：
```python
"""抢号任务 schema。"""
from datetime import datetime
from pydantic import BaseModel, ConfigDict

from app.models.booking import BookingStatus


class BookingCreate(BaseModel):
    """建任务无参数：抢号参数来自 user 档案。"""
    pass


class BookingOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    user_id: int
    status: BookingStatus
    attempt_count: int
    last_error: str | None
    result: dict | None
    started_at: datetime | None
    finished_at: datetime | None
    created_at: datetime
    updated_at: datetime


class WorkerClaimOut(BaseModel):
    """worker 拉取到的任务：含完整抢号档案，keyword 为密文（worker 私钥解）。"""
    booking_id: int
    user_id: int
    drvr_last_name: str
    licence_number: str
    keyword_ciphertext: str
    exam_class: str
    pos_ids: list[int]
    expect_after_date: date
    expect_before_date: date
    expect_time_range: str
    pref_days_of_week: list[int]
    pref_parts_of_day: list[int]


class WorkerResultIn(BaseModel):
    status: BookingStatus
    last_error: str | None = None
    result: dict | None = None
```
注意：`WorkerClaimOut` 用到 `date`，在文件顶部把 `from datetime import datetime` 改为 `from datetime import date, datetime`。

- [ ] **Step 3: 验证 schema import**

Run:
```bash
cd /home/xgao/workspace/icbc-roadtest-platform/backend
.venv/bin/python -c "from app.schemas.user import UserPublic, UserUpdate, SecretIn; from app.schemas.booking import BookingCreate, BookingOut, WorkerClaimOut; print('schemas OK')"
```
Expected: `schemas OK`

- [ ] **Step 4: Commit**

```bash
cd /home/xgao/workspace/icbc-roadtest-platform
git add backend/app/schemas/user.py backend/app/schemas/booking.py
git commit -m "backend: schema 对齐多用户档案 + secret keyword + booking 简化"
```

---

## Task 3: pos-list 字典 + API

**Files:**
- Create: `backend/app/data/icbc_pos_list.csv`
- Create: `backend/app/api/pos.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_pos.py`

- [ ] **Step 1: 复制考点字典**

```bash
mkdir -p /home/xgao/workspace/icbc-roadtest-platform/backend/app/data
cp /home/xgao/workspace/icbc-roadtest-auto-booking/icbc_pos_list.csv /home/xgao/workspace/icbc-roadtest-platform/backend/app/data/icbc_pos_list.csv
```

- [ ] **Step 2: 写失败测试**

Create `backend/tests/test_pos.py`:
```python
def test_pos_list_returns_entries(client):
    r = client.get("/api/pos-list")
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, list)
    assert len(data) > 50
    # 每项有 name + pos_id
    first = data[0]
    assert "name" in first and "pos_id" in first
    assert isinstance(first["pos_id"], int)
```

- [ ] **Step 3: 运行测试确认失败**

Run: `cd backend && .venv/bin/python -m pytest tests/test_pos.py -v`
Expected: FAIL（404，路由不存在）

- [ ] **Step 4: 写 pos API**

Create `backend/app/api/pos.py`:
```python
"""考点字典：GET /api/pos-list，供前端下拉。"""
import csv
from functools import lru_cache
from pathlib import Path

from fastapi import APIRouter

router = APIRouter(tags=["pos"])

_CSV = Path(__file__).resolve().parent.parent / "data" / "icbc_pos_list.csv"


@lru_cache
def _load_pos() -> list[dict]:
    out: list[dict] = []
    with _CSV.open(encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            name = (row.get("考场名称") or "").strip()
            pos_id = (row.get("posID") or "").strip()
            if name and pos_id.isdigit():
                out.append({"name": name, "pos_id": int(pos_id)})
    return out


@router.get("/pos-list")
def pos_list() -> list[dict]:
    return _load_pos()
```

- [ ] **Step 5: 注册路由**

在 `backend/app/main.py` 的路由注册区（`app.include_router(...)` 那几行附近）加：
```python
from app.api import pos
app.include_router(pos.router, prefix=settings.api_v1_prefix)
```
（import 放到顶部已有的 `from app.api import admin, auth, bookings, users, worker` 一行改为包含 pos：`from app.api import admin, auth, bookings, pos, users, worker`，注册行加 `app.include_router(pos.router, prefix=settings.api_v1_prefix)`。）

- [ ] **Step 6: 运行测试确认通过**

Run: `cd backend && .venv/bin/python -m pytest tests/test_pos.py -v`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
cd /home/xgao/workspace/icbc-roadtest-platform
git add backend/app/data/icbc_pos_list.csv backend/app/api/pos.py backend/app/main.py backend/tests/test_pos.py
git commit -m "backend: 考点字典 GET /api/pos-list"
```

---

## Task 4: secret 改存 keyword

**Files:**
- Modify: `backend/app/crud/secret.py`
- Modify: `backend/app/api/users.py`
- Test: `backend/tests/test_secret.py`

- [ ] **Step 1: 改 secret crud**

把 `backend/app/crud/secret.py` 的 `upsert` 函数签名与首行改为存单值 keyword：
```python
def upsert(db: Session, user: User, keyword: str) -> Secret:
    ciphertext = encrypt_secret(keyword)
    if user.secret is None:
        secret = Secret(user_id=user.id, ciphertext=ciphertext)
        db.add(secret)
    else:
        user.secret.ciphertext = ciphertext
        secret = user.secret
    db.commit()
    db.refresh(secret)
    return secret
```
（删掉原来的 `payload = f"{icbc_username}\n{icbc_password}"` 行。）

- [ ] **Step 2: 改 secret API**

在 `backend/app/api/users.py` 的 `set_secret`，把：
```python
    secret = secret_crud.upsert(db, user, payload.icbc_username, payload.icbc_password)
```
改为：
```python
    secret = secret_crud.upsert(db, user, payload.keyword)
```
（`payload` 现在是 `SecretIn{keyword}`，其余不变。）

- [ ] **Step 3: 改 secret 测试**

在 `backend/tests/test_secret.py` 中，把所有 `json={"icbc_username": ..., "icbc_password": ...}` 形式的 PUT secret 请求体改为 `json={"keyword": "my-icbc-keyword"}`。对应断言里如果检查明文不在密文中，把检查的明文改为 `b"my-icbc-keyword"`。`decrypt_secret` 往返测试断言解出的值等于 `"my-icbc-keyword"`（注意 keyword 现在是单值，不再 split）。

- [ ] **Step 4: 运行 secret 测试**

Run: `cd backend && .venv/bin/python -m pytest tests/test_secret.py -v`
Expected: PASS（全部 secret 用例）

- [ ] **Step 5: Commit**

```bash
cd /home/xgao/workspace/icbc-roadtest-platform
git add backend/app/crud/secret.py backend/app/api/users.py backend/tests/test_secret.py
git commit -m "backend: secret 改存 keyword（单值加密）"
```

---

## Task 5: user 档案读写（PATCH /users/me）

**Files:**
- Test: `backend/tests/test_users_profile.py`

说明：`crud.user.update_profile` 已是通用 `**fields` setattr，无需改；`UserUpdate` 已含档案字段（Task 2）。本 task 只加测试覆盖档案读写。

- [ ] **Step 1: 写测试**

Create `backend/tests/test_users_profile.py`:
```python
def test_update_and_read_profile(client, auth_headers):
    h = auth_headers()
    payload = {
        "icbc_license_no": "7654321",
        "icbc_last_name": "GAO",
        "exam_class": "5",
        "pos_ids": [1, 274],
        "expect_after_date": "2026-07-01",
        "expect_before_date": "2026-08-01",
        "expect_time_range": "10:00-17:00",
        "pref_days_of_week": [0, 1, 2, 3, 4],
        "pref_parts_of_day": [0, 1],
    }
    r = client.patch("/api/users/me", headers=h, json=payload)
    assert r.status_code == 200
    body = r.json()
    assert body["exam_class"] == "5"
    assert body["pos_ids"] == [1, 274]
    assert body["expect_time_range"] == "10:00-17:00"
    assert body["pref_days_of_week"] == [0, 1, 2, 3, 4]
    # 读回一致
    me = client.get("/api/users/me", headers=h).json()
    assert me["pos_ids"] == [1, 274]
    assert me["expect_after_date"] == "2026-07-01"
```

- [ ] **Step 2: 运行测试**

Run: `cd backend && .venv/bin/python -m pytest tests/test_users_profile.py -v`
Expected: PASS（若失败，检查 UserUpdate/UserPublic 是否含全部档案字段）

- [ ] **Step 3: Commit**

```bash
cd /home/xgao/workspace/icbc-roadtest-platform
git add backend/tests/test_users_profile.py
git commit -m "backend: user 档案读写测试"
```

---

## Task 6: claim 扩展返回完整档案

**Files:**
- Modify: `backend/app/api/worker.py`
- Test: `backend/tests/test_worker.py`

- [ ] **Step 1: 改 claim 构造**

在 `backend/app/api/worker.py` 的 `claim_task`，把构造 `WorkerClaimOut(...)` 的部分替换为从 user 档案取值：
```python
    user = booking.user
    if user.secret is None:
        booking_crud.complete(
            db, booking, BookingStatus.failed, last_error="用户未配置 ICBC keyword"
        )
        return None
    return WorkerClaimOut(
        booking_id=booking.id,
        user_id=user.id,
        drvr_last_name=user.icbc_last_name or "",
        licence_number=user.icbc_license_no or "",
        keyword_ciphertext=base64.b64encode(user.secret.ciphertext).decode(),
        exam_class=user.exam_class or "",
        pos_ids=user.pos_ids or [],
        expect_after_date=user.expect_after_date,
        expect_before_date=user.expect_before_date,
        expect_time_range=user.expect_time_range or "",
        pref_days_of_week=user.pref_days_of_week or [],
        pref_parts_of_day=user.pref_parts_of_day or [],
    )
```
（`base64` 已在文件顶部 import；保留原 `secret is None` 失败分支逻辑。）

- [ ] **Step 2: 改 worker 测试 fixture/用例**

`backend/tests/test_worker.py` 与 `backend/tests/conftest.py` 的 `ready_user` fixture 当前建任务依赖旧档案/secret 形态。更新：
- `ready_user` 把 `client.patch("/api/users/me", ...)` 的 body 改为完整档案（参考 Task 5 的 payload），`client.put("/api/users/me/secret", ...)` 改为 `json={"keyword": "kw-secret"}`，并返回 keyword 而非 user/pass。
- `test_claim_returns_ciphertext_no_plaintext`：断言改为 claim 返回含 `keyword_ciphertext`、`exam_class`、`pos_ids` 等字段，不含明文 keyword；用 `decrypt_secret(body["keyword_ciphertext"])` 解出等于 `"kw-secret"`（注意：现在解出的是单值 keyword，conftest 的 `decrypt_secret` fixture 若按 `\n` split 需调整为返回整串——见下）。
- conftest 的 `decrypt_secret` fixture 改为返回解密后的整串（不 split）：
  ```python
  @pytest.fixture
  def decrypt_secret():
      def _decrypt(ciphertext_b64: str) -> str:
          box = SealedBox(PrivateKey(TEST_PRIVATE_KEY.encode(), encoder=Base64Encoder))
          return box.decrypt(base64.b64decode(ciphertext_b64)).decode()
      return _decrypt
  ```

- [ ] **Step 3: 运行 worker 测试**

Run: `cd backend && .venv/bin/python -m pytest tests/test_worker.py -v`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
cd /home/xgao/workspace/icbc-roadtest-platform
git add backend/app/api/worker.py backend/tests/test_worker.py backend/tests/conftest.py
git commit -m "backend: claim 扩展返回完整抢号档案 + keyword 密文"
```

---

## Task 7: 建 booking 前置校验（档案完整性）

**Files:**
- Modify: `backend/app/api/bookings.py`
- Test: `backend/tests/test_booking.py`

- [ ] **Step 1: 改前置校验**

在 `backend/app/api/bookings.py` 的建 booking 端点，把原来检查 license/lastName/secret 的前置校验替换为完整档案校验：
```python
    missing = []
    if not user.icbc_license_no or not user.icbc_last_name:
        missing.append("驾照号/姓氏")
    if user.secret is None:
        missing.append("ICBC keyword")
    if not user.exam_class:
        missing.append("考试类型")
    if not user.pos_ids:
        missing.append("考点")
    if not user.expect_after_date or not user.expect_before_date:
        missing.append("日期区间")
    if missing:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, f"请先在设置页补全：{'、'.join(missing)}"
        )
```
建 booking 时不再读 BookingCreate 的 target_date 等（BookingCreate 现为空）；`booking_crud.create(db, user.id)` 不传参数字段。

- [ ] **Step 2: 改 booking 测试**

`backend/tests/test_booking.py`：
- 用到的 `ready_user` 已在 Task 6 更新为完整档案。
- 建 booking 的 `client.post("/api/bookings", ...)` 去掉 body 里的 target_date/pos_code（改为 `json={}` 或无 body）。
- 前置校验测试：拆成"缺档案 → 400"（只注册不填档案）与"档案完整 → 201"。断言 400 的 detail 含"补全"。

- [ ] **Step 3: 运行 booking 测试**

Run: `cd backend && .venv/bin/python -m pytest tests/test_booking.py -v`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
cd /home/xgao/workspace/icbc-roadtest-platform
git add backend/app/api/bookings.py backend/tests/test_booking.py
git commit -m "backend: 建 booking 前置校验改为档案完整性"
```

---

## Task 8: 全量回归

**Files:** 无（仅验证）

- [ ] **Step 1: 跑全量后端测试**

Run:
```bash
cd /home/xgao/workspace/icbc-roadtest-platform/backend
.venv/bin/python -m pytest -q
```
Expected: 全部 passed（含 test_pos / test_users_profile / 更新后的 secret/worker/booking/auth/admin/reaper/ratelimit）。
若有失败：多半是某处仍引用了已删字段（target_date/time_window/pos_code/preferred_pos/max_wait_days/icbc_username/icbc_password）。grep 定位并按本计划的新字段修正，不要恢复旧字段。

- [ ] **Step 2: 确认无残留旧字段引用**

Run:
```bash
cd /home/xgao/workspace/icbc-roadtest-platform/backend
grep -rnE "icbc_username|icbc_password|preferred_pos|max_wait_days|target_date|time_window|pos_code" app/ || echo "✅ 无残留旧字段引用"
```
Expected: `✅ 无残留旧字段引用`（app/ 下）。

- [ ] **Step 3: Commit（如 Step 1 有顺带修复）**

```bash
cd /home/xgao/workspace/icbc-roadtest-platform
git add -A backend/
git commit -m "backend: 多用户化后端全量回归通过" || echo "无新改动"
```

---

## 验收标准

- [ ] 迁移 0002 在 icbc_test 上 upgrade/downgrade 通过。
- [ ] user 档案可经 PATCH/GET /users/me 读写；secret 存 keyword 密文。
- [ ] GET /api/pos-list 返回 >50 个 {name,pos_id}。
- [ ] claim 返回完整档案 + keyword 密文（无明文）。
- [ ] 建 booking 前置校验要求档案完整。
- [ ] 全量后端 pytest 绿；app/ 下无旧字段残留。

## 后续（不在本计划）

- 计划 2：worker road_adapter 从 claim 字段构造 config['icbc']、多 posID 轮询、系统 Gmail 注入。
- 计划 3：前端 Settings 表单完整对齐 + pos-list 下拉。
