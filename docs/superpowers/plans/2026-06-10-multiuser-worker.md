# 多用户化 — worker 实现计划（计划 2/3）

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** worker 端从 claim 下发的完整档案构造 road.py 的 config（不再读死的单用户 config.yml 的 icbc 段），多 posID 轮询，系统级 Gmail 从 .env 注入——让网页配置真正驱动抢号。

**Architecture:** `Task` dataclass 改为承载完整抢号档案；`crypto` 解 keyword 单值；`worker.py` 从 claim 字段构造 Task；`road_adapter` 用一个系统级 base config（含通知禁用/autoBooking 策略/data_directory/gmail imap）做骨架，注入 icbc（来自 Task，逐 posID）+ gmail 凭据（来自 settings），限时循环对每个 posID 调 `road.job`。

**Tech Stack:** Python 3.12、pytest、unittest.mock、pynacl、vendor road.py。测试用 backend 的 venv：`/home/xgao/workspace/icbc-roadtest-platform/backend/.venv/bin/python`（已装 pynacl/PyYAML/requests/faker）。

**总体说明：**
- 设计见 `docs/superpowers/specs/2026-06-10-multiuser-web-driven-booking-design.md` 第 4、7 节。
- 计划 1（后端）已完成合并：claim 现在返回 `{booking_id, user_id, drvr_last_name, licence_number, keyword_ciphertext, exam_class, pos_ids, expect_after_date, expect_before_date, expect_time_range, pref_days_of_week, pref_parts_of_day}`。
- worker 测试命令：`cd worker && /home/xgao/workspace/icbc-roadtest-platform/backend/.venv/bin/python -m pytest tests/ -q`。

---

## 文件结构

| 文件 | 动作 | 责任 |
|---|---|---|
| `worker/booking_engine.py` | 改 | `Task` dataclass 换成完整档案字段；`run` 委托不变 |
| `worker/crypto.py` | 改 | `decrypt_secret` 改为解单值 keyword（不再 split） |
| `worker/worker.py` | 改 | `_execute_task` 解 keyword + 从 claim 字段构造 Task；抽出可测的 `build_task(raw, keyword)` |
| `worker/config.py` | 改 | 加 `gmail_email` / `gmail_app_password` |
| `worker/.env.example` | 改 | 补系统 Gmail 占位 + 说明 |
| `worker/road_adapter.py` | 改 | `_icbc_from_task` + `_build_config` + `run` 多 posID 轮询 |
| `worker/tests/test_road_adapter.py` | 改 | 重写：mock road.job/load_config，验证 config 构造 + 多 posID |
| `worker/tests/test_build_task.py` | 新 | 测 `build_task` 从 claim raw 构造 Task |

---

## Task 1: Task dataclass + 解 keyword + worker 构造

**Files:**
- Modify: `worker/booking_engine.py`
- Modify: `worker/crypto.py`
- Modify: `worker/worker.py`
- Test: `worker/tests/test_build_task.py`

- [ ] **Step 1: 改 Task dataclass**

把 `worker/booking_engine.py` 的 `Task` dataclass 替换为完整档案：
```python
@dataclass
class Task:
    booking_id: int
    user_id: int
    drvr_last_name: str
    licence_number: str
    keyword: str
    exam_class: str
    pos_ids: list[int]
    expect_after_date: str
    expect_before_date: str
    expect_time_range: str
    pref_days_of_week: list[int]
    pref_parts_of_day: list[int]
```
（`Result`、`BookingEngineError`、`run` 委托保持不变。）

- [ ] **Step 2: 改 crypto 解单值 keyword**

把 `worker/crypto.py` 的 `decrypt_secret` 改为返回单值字符串：
```python
def decrypt_secret(keyword_ciphertext_b64: str) -> str:
    """解密 claim 下发的 keyword 密文，返回明文 keyword。"""
    if not settings.secret_private_key:
        raise ValueError("SECRET_PRIVATE_KEY 未配置：worker 无法解密凭据")
    sk = PrivateKey(settings.secret_private_key.encode(), encoder=Base64Encoder)
    box = SealedBox(sk)
    return box.decrypt(base64.b64decode(keyword_ciphertext_b64)).decode()
```
（删掉原来的 split("\n") 与 parts 校验。）

- [ ] **Step 3: 写 build_task 失败测试**

Create `worker/tests/test_build_task.py`:
```python
from worker import build_task

RAW = {
    "booking_id": 7, "user_id": 3,
    "drvr_last_name": "GAO", "licence_number": "1234567",
    "keyword_ciphertext": "ignored-here",
    "exam_class": "5", "pos_ids": [1, 274],
    "expect_after_date": "2026-07-01", "expect_before_date": "2026-08-01",
    "expect_time_range": "10:00-17:00",
    "pref_days_of_week": [0, 1, 2], "pref_parts_of_day": [0, 1],
}


def test_build_task_maps_fields():
    task = build_task(RAW, keyword="my-keyword")
    assert task.booking_id == 7
    assert task.drvr_last_name == "GAO"
    assert task.licence_number == "1234567"
    assert task.keyword == "my-keyword"
    assert task.exam_class == "5"
    assert task.pos_ids == [1, 274]
    assert task.expect_after_date == "2026-07-01"
    assert task.pref_days_of_week == [0, 1, 2]
```

- [ ] **Step 4: 运行确认失败**

Run: `cd worker && /home/xgao/workspace/icbc-roadtest-platform/backend/.venv/bin/python -m pytest tests/test_build_task.py -v`
Expected: FAIL（`cannot import name 'build_task'`）

- [ ] **Step 5: 改 worker.py（抽 build_task + _execute_task 用新字段）**

在 `worker/worker.py`，新增模块级函数 `build_task`，并改 `_execute_task` 用它。把现有 `_execute_task` 里"解密 + 构造 Task"那段替换：
```python
def build_task(raw: dict, keyword: str) -> Task:
    return Task(
        booking_id=raw["booking_id"],
        user_id=raw["user_id"],
        drvr_last_name=raw["drvr_last_name"],
        licence_number=raw["licence_number"],
        keyword=keyword,
        exam_class=raw["exam_class"],
        pos_ids=raw["pos_ids"],
        expect_after_date=raw["expect_after_date"],
        expect_before_date=raw["expect_before_date"],
        expect_time_range=raw["expect_time_range"],
        pref_days_of_week=raw["pref_days_of_week"],
        pref_parts_of_day=raw["pref_parts_of_day"],
    )


def _execute_task(client: APIClient, raw: dict) -> None:
    booking_id = raw["booking_id"]
    logger.info("拿到任务 #%s（user=%s）", booking_id, raw["user_id"])
    try:
        keyword = decrypt_secret(raw["keyword_ciphertext"])
    except Exception as e:  # noqa: BLE001 — 解密失败即任务失败，回报后跳过
        logger.error("任务 #%s 凭据解密失败：%s", booking_id, e)
        client.report(booking_id, "failed", f"凭据解密失败：{e}", None)
        return
    task = build_task(raw, keyword)
    try:
        result: Result = run(task)
        if result.success:
            client.report(booking_id, "done", None, {
                "booked_at": result.booked_at,
                "confirmation_no": result.confirmation_no,
                **({"details": result.details} if result.details else {}),
            })
            logger.info("任务 #%s 完成 ✓", booking_id)
        else:
            client.report(booking_id, "failed", result.error or "未知失败", None)
            logger.warning("任务 #%s 失败：%s", booking_id, result.error)
    except BookingEngineError as e:
        client.report(booking_id, "failed", str(e), None)
        logger.warning("任务 #%s 失败：%s", booking_id, e)
    except Exception as e:
        logger.exception("任务 #%s 异常", booking_id)
        client.report(booking_id, "failed", f"worker 异常：{e!r}", None)
```
（顶部 import 不变：`from crypto import decrypt_secret`、`from booking_engine import BookingEngineError, Result, Task, run`。）

- [ ] **Step 6: 运行确认通过**

Run: `cd worker && /home/xgao/workspace/icbc-roadtest-platform/backend/.venv/bin/python -m pytest tests/test_build_task.py -v`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
cd /home/xgao/workspace/icbc-roadtest-platform
git add worker/booking_engine.py worker/crypto.py worker/worker.py worker/tests/test_build_task.py
git commit -m "worker: Task 改完整档案 + 解 keyword 单值 + build_task"
```

---

## Task 2: config.py 系统 Gmail + .env.example

**Files:**
- Modify: `worker/config.py`
- Modify: `worker/.env.example`

- [ ] **Step 1: 加 gmail 配置项**

在 `worker/config.py` 的 `Settings` 类里，`booking_poll_seconds` 之后加：
```python
    # 系统级 Gmail（收 OTP），由运维配在 worker .env，不每用户存
    gmail_email: str = ""
    gmail_app_password: str = ""
```

- [ ] **Step 2: 补 .env.example**

在 `worker/.env.example` 末尾追加：
```
# ===== 系统级 Gmail（收 ICBC OTP，所有用户共享）=====
# 用 Gmail 应用专用密码（非登录密码）：Google 账号 → 安全 → 两步验证 → 应用专用密码
GMAIL_EMAIL=system-icbc@gmail.com
GMAIL_APP_PASSWORD=your 16char app password
```

- [ ] **Step 3: 验证 config import**

Run:
```bash
cd /home/xgao/workspace/icbc-roadtest-platform/worker && \
/home/xgao/workspace/icbc-roadtest-platform/backend/.venv/bin/python -c "from config import settings; print('gmail cfg OK', settings.gmail_email == '', settings.gmail_app_password == '')"
```
Expected: `gmail cfg OK True True`（默认空字符串）

- [ ] **Step 4: Commit**

```bash
cd /home/xgao/workspace/icbc-roadtest-platform
git add worker/config.py worker/.env.example
git commit -m "worker: 系统级 Gmail 配置（.env 注入）"
```

---

## Task 3: road_adapter 从 DB 构造 config + 多 posID 轮询

**Files:**
- Modify: `worker/road_adapter.py`
- Modify: `worker/tests/test_road_adapter.py`

- [ ] **Step 1: 重写 road_adapter**

把 `worker/road_adapter.py` 整体替换为：
```python
"""把 vendor 的 road.py 封装成 booking_engine 能调用的限时循环。

多用户阶段：config 的 icbc 段来自 Task（网页档案）、gmail 凭据来自系统级 settings；
其余结构（通知禁用/autoBooking 策略/data_directory/gmail imap）来自系统级 base config
（settings.road_config_path 指向的 yaml）。对 Task 的每个 posID 逐个轮询抢号。
"""
import logging
import time

from booking_engine import Result
from config import settings
from vendor import road

logger = logging.getLogger("worker.road_adapter")

_SUCCESS_STATES = {"booking_success", "already_booked"}


def _icbc_from_task(task, pos_id: int) -> dict:
    """从 Task 构造 road.py 的 config['icbc'] 段（单个 posID）。"""
    return {
        "drvrLastName": task.drvr_last_name,
        "licenceNumber": task.licence_number,
        "keyword": task.keyword,
        "examClass": task.exam_class,
        "posID": pos_id,
        # road.py 把这两个直接塞进 ICBC 请求体；原 config.yml 用紧凑字符串形式
        "prfDaysOfWeek": str(task.pref_days_of_week).replace(" ", ""),
        "prfPartsOfDay": str(task.pref_parts_of_day).replace(" ", ""),
        "expactAfterDate": task.expect_after_date,
        "expactBeforeDate": task.expect_before_date,
        "expactTimeRange": task.expect_time_range,
    }


def _build_config(task) -> dict:
    """系统级 base + 注入 gmail 凭据 + 强制真实下单/收码。icbc 段在轮询时逐 posID 覆盖。"""
    config = road.load_config(settings.road_config_path)
    config.setdefault("gmail", {})
    config["gmail"]["email"] = settings.gmail_email
    config["gmail"]["password"] = settings.gmail_app_password
    config.setdefault("autoBooking", {})["enable"] = True
    config.setdefault("emailReplace", {})["enable"] = True
    return config


def run(task):
    config = _build_config(task)
    pos_ids = task.pos_ids or []
    deadline = time.monotonic() + settings.booking_timeout_seconds
    rounds = 0
    try:
        while time.monotonic() < deadline:
            rounds += 1
            for pos_id in pos_ids:
                config["icbc"] = _icbc_from_task(task, pos_id)
                try:
                    status = road.job(config)
                except Exception:  # noqa: BLE001 — 单轮异常不中断循环
                    logger.exception("booking #%s 第 %d 轮 posID=%s job 异常", task.booking_id, rounds, pos_id)
                    status = None
                logger.info("booking #%s 第 %d 轮 posID=%s：job 返回 %s", task.booking_id, rounds, pos_id, status)
                if status in _SUCCESS_STATES:
                    return _success_result(config, status)
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            time.sleep(min(settings.booking_poll_seconds, remaining))
        return Result(success=False,
                      error=f"到达时限（{settings.booking_timeout_seconds}s）仍未抢到号")
    finally:
        _best_effort_restore(config)


def _success_result(config, status):
    info = road.load_booking_status(config) or {}
    appt = info.get("appointment") or {}
    booked_at = None
    if appt.get("date"):
        booked_at = f"{appt.get('date')} {appt.get('time', '')}".strip()
    return Result(
        success=True,
        booked_at=booked_at,
        confirmation_no=appt.get("date"),
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

- [ ] **Step 2: 重写 test_road_adapter**

把 `worker/tests/test_road_adapter.py` 整体替换为：
```python
"""road_adapter 单测：全部 mock vendor.road，不触真实 ICBC。"""
from unittest.mock import patch

import road_adapter
from booking_engine import Task

TASK = Task(
    booking_id=1, user_id=1, drvr_last_name="GAO", licence_number="1234567",
    keyword="kw", exam_class="5", pos_ids=[1, 274],
    expect_after_date="2026-07-01", expect_before_date="2026-08-01",
    expect_time_range="10:00-17:00", pref_days_of_week=[0, 1, 2], pref_parts_of_day=[0, 1],
)


def _base():
    return {"gmail": {}, "autoBooking": {}, "emailReplace": {"enable": True}}


def test_build_config_injects_icbc_and_gmail(monkeypatch):
    monkeypatch.setattr(road_adapter.settings, "gmail_email", "sys@gmail.com")
    monkeypatch.setattr(road_adapter.settings, "gmail_app_password", "applekey")
    monkeypatch.setattr(road_adapter.settings, "booking_timeout_seconds", 0.2)
    monkeypatch.setattr(road_adapter.settings, "booking_poll_seconds", 0.05)
    captured = {}
    def fake_job(cfg):
        captured["cfg"] = {**cfg, "icbc": dict(cfg["icbc"])}
        return "no_appointments"
    with patch.object(road_adapter.road, "load_config", return_value=_base()), \
         patch.object(road_adapter.road, "job", side_effect=fake_job), \
         patch.object(road_adapter.road, "get_weblogin", return_value=None):
        road_adapter.run(TASK)
    cfg = captured["cfg"]
    assert cfg["gmail"]["email"] == "sys@gmail.com"
    assert cfg["gmail"]["password"] == "applekey"
    assert cfg["autoBooking"]["enable"] is True
    assert cfg["icbc"]["drvrLastName"] == "GAO"
    assert cfg["icbc"]["keyword"] == "kw"
    assert cfg["icbc"]["examClass"] == "5"
    assert cfg["icbc"]["prfDaysOfWeek"] == "[0,1,2]"
    assert cfg["icbc"]["expactTimeRange"] == "10:00-17:00"


def test_success_maps_result(monkeypatch):
    monkeypatch.setattr(road_adapter.settings, "booking_timeout_seconds", 5)
    monkeypatch.setattr(road_adapter.settings, "booking_poll_seconds", 0.01)
    status = {"appointment": {"date": "2026-07-15", "time": "10:30", "dayOfWeek": "Tue"}}
    with patch.object(road_adapter.road, "load_config", return_value=_base()), \
         patch.object(road_adapter.road, "job", return_value="booking_success"), \
         patch.object(road_adapter.road, "load_booking_status", return_value=status), \
         patch.object(road_adapter.road, "get_weblogin", return_value=None):
        result = road_adapter.run(TASK)
    assert result.success is True
    assert result.booked_at == "2026-07-15 10:30"


def test_multi_pos_polling(monkeypatch):
    """第一个 posID 没号、第二个成交。"""
    monkeypatch.setattr(road_adapter.settings, "booking_timeout_seconds", 5)
    monkeypatch.setattr(road_adapter.settings, "booking_poll_seconds", 0.01)
    seen_pos = []
    def fake_job(cfg):
        pos = cfg["icbc"]["posID"]
        seen_pos.append(pos)
        return "booking_success" if pos == 274 else "no_appointments"
    with patch.object(road_adapter.road, "load_config", return_value=_base()), \
         patch.object(road_adapter.road, "job", side_effect=fake_job), \
         patch.object(road_adapter.road, "load_booking_status", return_value=None), \
         patch.object(road_adapter.road, "get_weblogin", return_value=None):
        result = road_adapter.run(TASK)
    assert result.success is True
    assert seen_pos == [1, 274]  # 第一轮先试 1（没号）再试 274（成交）


def test_timeout_returns_failure(monkeypatch):
    monkeypatch.setattr(road_adapter.settings, "booking_timeout_seconds", 0.2)
    monkeypatch.setattr(road_adapter.settings, "booking_poll_seconds", 0.05)
    with patch.object(road_adapter.road, "load_config", return_value=_base()), \
         patch.object(road_adapter.road, "job", return_value="no_appointments"), \
         patch.object(road_adapter.road, "get_weblogin", return_value=None):
        result = road_adapter.run(TASK)
    assert result.success is False
    assert "时限" in result.error


def test_job_exception_is_retried(monkeypatch):
    monkeypatch.setattr(road_adapter.settings, "booking_timeout_seconds", 5)
    monkeypatch.setattr(road_adapter.settings, "booking_poll_seconds", 0.01)
    seq = [ConnectionError("boom"), "booking_success"]
    with patch.object(road_adapter.road, "load_config", return_value=_base()), \
         patch.object(road_adapter.road, "job", side_effect=seq), \
         patch.object(road_adapter.road, "load_booking_status", return_value=None), \
         patch.object(road_adapter.road, "get_weblogin", return_value=None):
        result = road_adapter.run(TASK)
    assert result.success is True


def test_finally_restores_email_when_enabled(monkeypatch):
    monkeypatch.setattr(road_adapter.settings, "booking_timeout_seconds", 5)
    monkeypatch.setattr(road_adapter.settings, "booking_poll_seconds", 0.01)
    class _Resp:
        headers = {"Authorization": "tok"}
        def json(self):
            return {"email": "replaced@gmail.com"}
    with patch.object(road_adapter.road, "load_config", return_value=_base()), \
         patch.object(road_adapter.road, "job", return_value="booking_success"), \
         patch.object(road_adapter.road, "load_booking_status", return_value=None), \
         patch.object(road_adapter.road, "get_weblogin", return_value=_Resp()), \
         patch.object(road_adapter.road, "restore_original_email") as restore_mock:
        road_adapter.run(TASK)
    restore_mock.assert_called_once()
```

- [ ] **Step 3: 运行测试**

Run: `cd worker && /home/xgao/workspace/icbc-roadtest-platform/backend/.venv/bin/python -m pytest tests/test_road_adapter.py -v`
Expected: 6 passed

- [ ] **Step 4: Commit**

```bash
cd /home/xgao/workspace/icbc-roadtest-platform
git add worker/road_adapter.py worker/tests/test_road_adapter.py
git commit -m "worker: road_adapter 从档案构造 config + 多 posID 轮询 + 系统 Gmail"
```

---

## Task 4: 回归 + config.example 收尾

**Files:**
- Modify: `worker/config.example.yml`（注释说明）

- [ ] **Step 1: config.example.yml 标注多用户语义**

在 `worker/config.example.yml` 顶部加一段注释（文件第一行前）：
```yaml
# ⚠️ 多用户阶段：本文件作为 worker 的【系统级 base config】。
# icbc 段会被每个用户的网页档案在运行时覆盖（这里的 icbc 占位值仅占位、不生效）。
# gmail 的 email/password 由 worker/.env 的 GMAIL_EMAIL/GMAIL_APP_PASSWORD 覆盖。
# autoBooking.enable 与 emailReplace.enable 运行时强制为 true。
# 真正需要运维维护的是：通知开关、data_directory、autoBooking 的重试/超时策略、gmail 的 imap 设置。
```

- [ ] **Step 2: 全量 worker 测试回归**

Run:
```bash
cd /home/xgao/workspace/icbc-roadtest-platform/worker && \
/home/xgao/workspace/icbc-roadtest-platform/backend/.venv/bin/python -m pytest tests/ -q
```
Expected: 全部 passed（test_build_task + test_road_adapter + test_booking_engine）。
若 test_booking_engine 因 Task 字段变化而构造失败，更新其 TASK 常量为新档案字段（参考 test_road_adapter 的 TASK）。

- [ ] **Step 3: 确认 worker 无残留旧字段**

Run:
```bash
cd /home/xgao/workspace/icbc-roadtest-platform/worker && \
grep -rnE "icbc_username|icbc_password|secret_ciphertext|target_date|max_wait_days|road_config_path.*icbc" *.py tests/*.py || echo "✅ 无残留旧字段"
```
Expected: `✅ 无残留旧字段`（road_config_path 本身仍用于 base config，属正常；只确认没有旧的 icbc 单用户取值残留）。

- [ ] **Step 4: Commit**

```bash
cd /home/xgao/workspace/icbc-roadtest-platform
git add worker/config.example.yml
git commit -m "worker: config.example 标注多用户系统级 base 语义"
```

---

## 验收标准

- [ ] `Task` 承载完整档案；`build_task` 从 claim raw 正确构造。
- [ ] `decrypt_secret` 解单值 keyword。
- [ ] `road_adapter._build_config` 注入 gmail 凭据 + 强制 autoBooking/emailReplace.enable；`_icbc_from_task` 字段映射正确（含 prfDaysOfWeek 紧凑字符串）。
- [ ] 多 posID 轮询：逐个 posID 调 job，任一成交即返回。
- [ ] worker 全量测试绿；无旧字段残留。
- [ ] 系统 Gmail 从 .env 注入，不每用户存。

## 后续（不在本计划）

- 计划 3：前端 Settings 表单完整对齐 + pos-list 下拉 + users.ts api 改 keyword/档案字段。
- 真实联调（dry-run → 真实抢号）在前端完成后由用户手动验证。
