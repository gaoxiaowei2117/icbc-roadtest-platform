# road.py 接入 booking_engine 实现计划（单用户阶段）

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 road.py 的真实抢号逻辑以薄封装方式接进 `worker/booking_engine.py`，用 config.yml 单用户配置真实跑通。

**Architecture:** road.py 原样 vendor 进 `worker/vendor/`，新增 `road_adapter.py` 把 road.py 的 `job()`（一轮抢号）包成限时循环并映射为 `Result`；`booking_engine.run()` 委托给适配器。`Task`/`Result` 接口不变。

**Tech Stack:** Python 3.12、pytest、unittest.mock、requests/PyYAML/faker（road.py 依赖）、pydantic-settings（worker 配置）。

**测试环境约定：** worker 测试用 backend 的 venv 跑（已装 pydantic-settings/pynacl/httpx），额外装 requests/PyYAML/faker。命令统一用绝对路径 `/home/xgao/workspace/icbc-roadtest-platform/backend/.venv/bin/python`（下称 `$PY`）。

---

## 文件结构

| 文件 | 责任 |
|---|---|
| `worker/vendor/road.py` | vendor 的 road.py 原样副本，当库 import，不修改 |
| `worker/vendor/__init__.py` | 空包标记 |
| `worker/road_adapter.py` | 适配器：load config + 限时循环调 `road.job()` + 状态→Result 映射 + 邮箱 restore 兜底 |
| `worker/booking_engine.py` | `run()` 委托 `road_adapter.run()`；`Task`/`Result`/`BookingEngineError` 不变 |
| `worker/config.py` | 加 `road_config_path` / `booking_timeout_seconds` / `booking_poll_seconds` |
| `worker/config.example.yml` | road.py yaml 占位模板（进仓库） |
| `worker/pytest.ini` | worker 测试配置 |
| `worker/tests/test_road_adapter.py` | 适配器单测（mock road.job 等） |
| `worker/requirements.txt` | 放开 requests/PyYAML/faker |
| `docs/known-issues.md` | T1 标记本阶段完成范围 |

---

## Task 1: vendor road.py + 依赖

**Files:**
- Create: `worker/vendor/road.py`（复制）
- Create: `worker/vendor/__init__.py`
- Modify: `worker/requirements.txt`

- [ ] **Step 1: 复制 road.py 并建包**

```bash
cd /home/xgao/workspace/icbc-roadtest-platform
mkdir -p worker/vendor
cp /home/xgao/workspace/icbc-roadtest-auto-booking/road.py worker/vendor/road.py
touch worker/vendor/__init__.py
```

- [ ] **Step 2: 装 road.py 依赖到测试 venv**

```bash
/home/xgao/workspace/icbc-roadtest-platform/backend/.venv/bin/pip install requests==2.31.0 PyYAML==6.0.1 faker==24.0.0
```
Expected: `Successfully installed ... faker-24.0.0 ...`（或已满足；版本须与 Step 4 的 requirements.txt 一致）

- [ ] **Step 3: 验证 vendor 的 road.py import 无副作用**

Run:
```bash
cd /home/xgao/workspace/icbc-roadtest-platform/worker && \
/home/xgao/workspace/icbc-roadtest-platform/backend/.venv/bin/python -c "from vendor import road; print('OK', callable(road.job), callable(road.load_config))"
```
Expected: `OK True True`（import 不执行 main、不报错）

- [ ] **Step 4: 放开 worker/requirements.txt 依赖**

把 `worker/requirements.txt` 改为：
```
httpx==0.27.0
pynacl==1.5.0
requests==2.31.0
PyYAML==6.0.1
faker==24.0.0
# playwright==1.42.0  # 不再需要：road.py 用 requests 直连，非浏览器自动化
pydantic==2.6.1
pydantic-settings==2.2.1
python-dateutil==2.8.2
```

- [ ] **Step 5: Commit**

```bash
cd /home/xgao/workspace/icbc-roadtest-platform
git add worker/vendor/road.py worker/vendor/__init__.py worker/requirements.txt
git commit -m "worker: vendor road.py + 抢号依赖（requests/PyYAML/faker）"
```

---

## Task 2: worker 配置扩展 + yaml 模板

**Files:**
- Modify: `worker/config.py`
- Create: `worker/config.example.yml`

- [ ] **Step 1: 扩展 worker/config.py**

在 `worker/config.py` 的 `Settings` 类里，`secret_private_key` 字段之后加入：
```python
    # road.py 抢号配置
    road_config_path: str = "./config.yml"
    booking_timeout_seconds: int = 600   # run() 限时循环上限，须 < backend RUNNING_TIMEOUT_MINUTES(15min)
    booking_poll_seconds: int = 30       # 没号时两轮 job() 之间的间隔
```

- [ ] **Step 2: 建 config.example.yml 占位模板**

把 `/home/xgao/workspace/icbc-roadtest-auto-booking/config.yml` 复制为 `worker/config.example.yml`，并把敏感值替换为占位：
```bash
cp /home/xgao/workspace/icbc-roadtest-auto-booking/config.yml /home/xgao/workspace/icbc-roadtest-platform/worker/config.example.yml
```
然后编辑 `worker/config.example.yml`，把这些字段改成占位：
- `icbc.drvrLastName` → `"YOUR_LAST_NAME"`
- `icbc.licenceNumber` → `"YOUR_LICENCE_NUMBER"`
- `icbc.keyword` → `"YOUR_KEYWORD"`
- `gmail.email` → `"your-gmail@gmail.com"`
- `gmail.password` → `"your 16char app password"`
- 并把 `autoBooking.enable` 改为 `false`（默认 dry-run，安全）

- [ ] **Step 3: 确认实际 config.yml 被 gitignore**

Run:
```bash
cd /home/xgao/workspace/icbc-roadtest-platform
grep -q "config.yml" worker/../.gitignore 2>/dev/null || echo "worker/config.yml" >> .gitignore
git check-ignore worker/config.yml && echo "✅ 真值文件被忽略"
```
Expected: `✅ 真值文件被忽略`

- [ ] **Step 4: Commit**

```bash
cd /home/xgao/workspace/icbc-roadtest-platform
git add worker/config.py worker/config.example.yml .gitignore
git commit -m "worker: 加 road 抢号配置项 + config.example.yml 占位模板"
```

---

## Task 3: road_adapter — 成功路径状态映射（TDD）

**Files:**
- Create: `worker/pytest.ini`
- Create: `worker/tests/test_road_adapter.py`
- Create: `worker/road_adapter.py`

- [ ] **Step 1: 建 worker/pytest.ini**

```ini
[pytest]
pythonpath = .
testpaths = tests
addopts = -q
```

- [ ] **Step 2: 写失败测试（成功路径映射）**

Create `worker/tests/test_road_adapter.py`:
```python
"""road_adapter 单测：全部 mock vendor.road，不触真实 ICBC。"""
from unittest.mock import patch

import road_adapter
from booking_engine import Task

TASK = Task(
    booking_id=1, user_id=1, target_date="2026-07-01", time_window=None,
    pos_code=None, icbc_username="u", icbc_password="p", max_wait_days=60,
)


def _cfg():
    return {"emailReplace": {"enable": False}}


def test_booking_success_maps_to_result():
    status = {"appointment": {"date": "2026-07-15", "time": "10:30", "dayOfWeek": "Tue"}}
    with patch.object(road_adapter.road, "load_config", return_value=_cfg()), \
         patch.object(road_adapter.road, "job", return_value="booking_success"), \
         patch.object(road_adapter.road, "load_booking_status", return_value=status):
        result = road_adapter.run(TASK)
    assert result.success is True
    assert result.booked_at == "2026-07-15 10:30"
    assert result.details["job_status"] == "booking_success"


def test_already_booked_is_success():
    with patch.object(road_adapter.road, "load_config", return_value=_cfg()), \
         patch.object(road_adapter.road, "job", return_value="already_booked"), \
         patch.object(road_adapter.road, "load_booking_status", return_value=None):
        result = road_adapter.run(TASK)
    assert result.success is True
```

- [ ] **Step 3: 运行测试确认失败**

Run:
```bash
cd /home/xgao/workspace/icbc-roadtest-platform/worker && \
/home/xgao/workspace/icbc-roadtest-platform/backend/.venv/bin/python -m pytest tests/test_road_adapter.py -v
```
Expected: FAIL（`ModuleNotFoundError: No module named 'road_adapter'`）

- [ ] **Step 4: 写最小实现**

Create `worker/road_adapter.py`:
```python
"""把 vendor 的 road.py 封装成 booking_engine 能调用的限时循环。

单用户阶段：凭据/偏好全来自 config.yml（settings.road_config_path）。
task 仅用于日志关联 booking_id。
"""
import logging
import time

from config import settings
from vendor import road

logger = logging.getLogger("worker.road_adapter")

# job() 返回这些状态视为"已成交"
_SUCCESS_STATES = {"booking_success", "already_booked"}


def run(task):
    from booking_engine import Result  # 延迟 import 破循环依赖

    config = road.load_config(settings.road_config_path)
    deadline = time.monotonic() + settings.booking_timeout_seconds
    rounds = 0
    try:
        while time.monotonic() < deadline:
            rounds += 1
            status = road.job(config)
            logger.info("booking #%s 第 %d 轮：job 返回 %s", task.booking_id, rounds, status)
            if status in _SUCCESS_STATES:
                return _success_result(Result, config, status)
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            time.sleep(min(settings.booking_poll_seconds, remaining))
        return Result(success=False,
                      error=f"到达时限（{settings.booking_timeout_seconds}s）仍未抢到号")
    finally:
        _best_effort_restore(config)


def _success_result(Result, config, status):
    info = road.load_booking_status(config) or {}
    appt = info.get("appointment") or {}
    booked_at = None
    if appt.get("date"):
        booked_at = f"{appt.get('date')} {appt.get('time', '')}".strip()
    return Result(
        success=True,
        booked_at=booked_at,
        confirmation_no=appt.get("date"),  # ICBC 无独立确认号，用日期标识
        details={"job_status": status, **appt},
    )


def _best_effort_restore(config):
    """循环结束兜底：emailReplace 开启时，轻量登录后 restore 原邮箱。"""
    try:
        if not (config.get("emailReplace") or {}).get("enable"):
            return
        resp = road.get_weblogin(config)
        if not resp:
            logger.warning("兜底 restore：登录失败，跳过")
            return
        token = resp.headers.get("Authorization", "")
        road.restore_original_email(config, token, resp.json())
    except Exception:  # noqa: BLE001 — 兜底绝不能影响主结果
        logger.exception("兜底 restore 邮箱异常")
```

- [ ] **Step 5: 运行测试确认通过**

Run:
```bash
cd /home/xgao/workspace/icbc-roadtest-platform/worker && \
/home/xgao/workspace/icbc-roadtest-platform/backend/.venv/bin/python -m pytest tests/test_road_adapter.py -v
```
Expected: `test_booking_success_maps_to_result PASSED` + `test_already_booked_is_success PASSED`

- [ ] **Step 6: Commit**

```bash
cd /home/xgao/workspace/icbc-roadtest-platform
git add worker/pytest.ini worker/tests/test_road_adapter.py worker/road_adapter.py
git commit -m "worker: road_adapter 成功路径状态映射 + 单测"
```

---

## Task 4: 限时循环与超时（TDD）

**Files:**
- Modify: `worker/tests/test_road_adapter.py`

- [ ] **Step 1: 加超时与多轮测试**

在 `worker/tests/test_road_adapter.py` 末尾追加：
```python
def test_timeout_returns_failure(monkeypatch):
    monkeypatch.setattr(road_adapter.settings, "booking_timeout_seconds", 0.2)
    monkeypatch.setattr(road_adapter.settings, "booking_poll_seconds", 0.05)
    with patch.object(road_adapter.road, "load_config", return_value=_cfg()), \
         patch.object(road_adapter.road, "job", return_value="no_appointments"):
        result = road_adapter.run(TASK)
    assert result.success is False
    assert "时限" in result.error


def test_loops_until_success(monkeypatch):
    monkeypatch.setattr(road_adapter.settings, "booking_timeout_seconds", 5)
    monkeypatch.setattr(road_adapter.settings, "booking_poll_seconds", 0.01)
    seq = ["no_appointments", "token_failed", "booking_success"]
    with patch.object(road_adapter.road, "load_config", return_value=_cfg()), \
         patch.object(road_adapter.road, "job", side_effect=seq) as job_mock, \
         patch.object(road_adapter.road, "load_booking_status", return_value=None):
        result = road_adapter.run(TASK)
    assert result.success is True
    assert job_mock.call_count == 3
```

- [ ] **Step 2: 运行测试确认通过**

Run:
```bash
cd /home/xgao/workspace/icbc-roadtest-platform/worker && \
/home/xgao/workspace/icbc-roadtest-platform/backend/.venv/bin/python -m pytest tests/test_road_adapter.py -v
```
Expected: 4 passed（前两个 + 新两个）。实现已在 Task 3 写好，本任务只补测试验证循环/超时行为。

- [ ] **Step 3: Commit**

```bash
cd /home/xgao/workspace/icbc-roadtest-platform
git add worker/tests/test_road_adapter.py
git commit -m "worker: road_adapter 限时循环/超时测试"
```

---

## Task 5: 邮箱 restore 兜底（TDD）

**Files:**
- Modify: `worker/tests/test_road_adapter.py`

- [ ] **Step 1: 加 restore 兜底测试**

在 `worker/tests/test_road_adapter.py` 末尾追加：
```python
class _Resp:
    headers = {"Authorization": "tok"}
    def json(self):
        return {"email": "replaced@gmail.com"}


def test_finally_restores_email_when_enabled():
    cfg = {"emailReplace": {"enable": True}}
    with patch.object(road_adapter.road, "load_config", return_value=cfg), \
         patch.object(road_adapter.road, "job", return_value="booking_success"), \
         patch.object(road_adapter.road, "load_booking_status", return_value=None), \
         patch.object(road_adapter.road, "get_weblogin", return_value=_Resp()), \
         patch.object(road_adapter.road, "restore_original_email") as restore_mock:
        road_adapter.run(TASK)
    restore_mock.assert_called_once()


def test_no_restore_when_disabled():
    with patch.object(road_adapter.road, "load_config", return_value=_cfg()), \
         patch.object(road_adapter.road, "job", return_value="booking_success"), \
         patch.object(road_adapter.road, "load_booking_status", return_value=None), \
         patch.object(road_adapter.road, "restore_original_email") as restore_mock:
        road_adapter.run(TASK)
    restore_mock.assert_not_called()
```

- [ ] **Step 2: 运行测试确认通过**

Run:
```bash
cd /home/xgao/workspace/icbc-roadtest-platform/worker && \
/home/xgao/workspace/icbc-roadtest-platform/backend/.venv/bin/python -m pytest tests/test_road_adapter.py -v
```
Expected: 6 passed（实现已在 Task 3 的 `_best_effort_restore` 写好）

- [ ] **Step 3: Commit**

```bash
cd /home/xgao/workspace/icbc-roadtest-platform
git add worker/tests/test_road_adapter.py
git commit -m "worker: road_adapter 邮箱 restore 兜底测试"
```

---

## Task 6: booking_engine 委托适配器（TDD）

**Files:**
- Modify: `worker/booking_engine.py`
- Create: `worker/tests/test_booking_engine.py`

- [ ] **Step 1: 写测试（run 委托适配器，不再抛 stub 错）**

Create `worker/tests/test_booking_engine.py`:
```python
from unittest.mock import patch

import booking_engine
from booking_engine import Result, Task

TASK = Task(
    booking_id=9, user_id=1, target_date=None, time_window=None,
    pos_code=None, icbc_username="u", icbc_password="p", max_wait_days=60,
)


def test_run_delegates_to_adapter():
    fake = Result(success=True, confirmation_no="2026-07-15")
    with patch("road_adapter.run", return_value=fake) as adapter:
        out = booking_engine.run(TASK)
    adapter.assert_called_once_with(TASK)
    assert out is fake
```

- [ ] **Step 2: 运行测试确认失败**

Run:
```bash
cd /home/xgao/workspace/icbc-roadtest-platform/worker && \
/home/xgao/workspace/icbc-roadtest-platform/backend/.venv/bin/python -m pytest tests/test_booking_engine.py -v
```
Expected: FAIL（当前 `run` 抛 `BookingEngineError`，断言 `out is fake` 失败）

- [ ] **Step 3: 改 booking_engine.run 委托适配器**

把 `worker/booking_engine.py` 的 `run` 函数整体替换为：
```python
def run(task: Task) -> Result:
    """执行一次抢号（限时循环），委托给 road_adapter。"""
    import road_adapter  # 延迟 import：避免 import 期拉起 vendor.road 依赖链
    return road_adapter.run(task)
```
（保留文件顶部的 `BookingEngineError` / `Task` / `Result` 定义不动，仅替换 `run` 的实现体；删除原 stub 里的 TODO 注释与 `raise`。）

- [ ] **Step 4: 运行测试确认通过**

Run:
```bash
cd /home/xgao/workspace/icbc-roadtest-platform/worker && \
/home/xgao/workspace/icbc-roadtest-platform/backend/.venv/bin/python -m pytest tests/ -v
```
Expected: 全部通过（test_road_adapter 6 + test_booking_engine 1）

- [ ] **Step 5: Commit**

```bash
cd /home/xgao/workspace/icbc-roadtest-platform
git add worker/booking_engine.py worker/tests/test_booking_engine.py
git commit -m "worker: booking_engine.run 委托 road_adapter（接入真实抢号）"
```

---

## Task 7: 文档 + 回归 + dry-run 说明

**Files:**
- Modify: `docs/known-issues.md`
- Modify: `worker/.env.example`

- [ ] **Step 1: known-issues 标记 T1 本阶段完成**

在 `docs/known-issues.md` 的"待办"表里，把 T1 行替换为（移出待办、记入已完成范围）：
```
| T1 | `worker/booking_engine.py` 接入真实抢号：薄封装 vendor road.py，road_adapter 限时循环调 job()。**单用户阶段**完成；多用户化（每用户 keyword/Gmail/偏好 + 多用户 OTP）见 spec 后续阶段。 | ✅ 本阶段完成 |
```
并在表后补一段：
```
> road.py 接入设计见 docs/superpowers/specs/2026-06-09-road-py-booking-engine-integration-design.md。
> 后续遗留：多用户化、road.py 失败路径原生不 restore 邮箱（适配器 finally 兜底）、vendor 与上游手动同步。
```

- [ ] **Step 2: worker/.env.example 补 road 配置说明**

在 `worker/.env.example` 末尾追加：
```
# ===== road.py 抢号 =====
# 实际配置在 worker/config.yml（复制 config.example.yml 填真值，被 gitignore）
ROAD_CONFIG_PATH=./config.yml
BOOKING_TIMEOUT_SECONDS=600   # 须 < backend RUNNING_TIMEOUT_MINUTES(900s)
BOOKING_POLL_SECONDS=30
```

- [ ] **Step 3: 跑全量 worker + backend 测试回归**

Run:
```bash
cd /home/xgao/workspace/icbc-roadtest-platform/worker && \
/home/xgao/workspace/icbc-roadtest-platform/backend/.venv/bin/python -m pytest tests/ -v
cd /home/xgao/workspace/icbc-roadtest-platform/backend && \
.venv/bin/python -m pytest -q
```
Expected: worker 7 passed；backend 33 passed（不受影响）

- [ ] **Step 4: Commit**

```bash
cd /home/xgao/workspace/icbc-roadtest-platform
git add docs/known-issues.md worker/.env.example
git commit -m "docs: T1 标记单用户抢号接入完成 + dry-run 配置说明"
```

---

## 真实验证（人工，自动化之外）

实现完成后，按 spec 第 8 节 **dry-run 先行**：

1. 复制 `worker/config.example.yml` → `worker/config.yml`，填真实账号 + Gmail app password，**保持 `autoBooking.enable: false`**。
2. 启动 backend，建一个任务，启动 worker；观察 worker 日志：登录成功、查到时段、`job()` 返回 `notification_sent_paused`/`no_appointments`，适配器到时限返回 `failed`（dry-run 不下单属预期）。
3. 确认 dry-run 链路无误后，把 `autoBooking.enable: true`，由用户亲自盯着真实抢号（会真占考位、真改 ICBC 邮箱）。

---

## 验收标准（对应 spec 第 10 节）

- [ ] `booking_engine.run()` 不再 stub，委托 road_adapter，`Task`/`Result` 接口未变。
- [ ] `worker/tests/`（test_road_adapter 6 + test_booking_engine 1）全绿；backend 33 测试不受影响。
- [ ] dry-run 真实连 ICBC：登录成功、查到时段、状态正确映射。
- [ ] 真实模式由用户在 dry-run 通过后手动开启并人工验证。
- [ ] known-issues T1 更新，遗留项列明。
