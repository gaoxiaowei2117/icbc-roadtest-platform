---
title: 并发竞态 — booking 任务状态机
date: 2026-06-30
tags:
  - icbc-platform
  - bug-fix
  - 并发
  - 数据库
pr: 5
severity: 高
aliases:
  - booking 竞态
  - 状态机竞态
  - 行锁
---

# 并发竞态 — booking 任务状态机

PR #5 修复的一组"读-改-写"竞态。共同教训：**跨请求/跨进程的状态转换，必须用行锁或带条件的 UPDATE 保护，不变量要落到 DB 约束。**

> [!summary] 涉及文件
> `backend/app/crud/booking.py`、`backend/app/api/worker.py`、`backend/app/api/bookings.py`、`backend/app/models/booking.py`、`worker/road_adapter.py`、`worker/worker.py`

---

## reaper 覆盖终态任务

`reset_stale_running` 普通 SELECT 出候选，再逐个改对象提交。SQLAlchemy 发出的 `UPDATE ... WHERE id=X` **不带 `status='running'`**。若某行在"读取候选→提交"之间被 worker 改成 `done`，会被覆盖回 `pending` → 任务重排 → **重复抢号**。

**修复**：改用带守卫的批量 UPDATE，只在仍为 `running` 时才重置，用 `rowcount` 作为返回数。

```python
db.execute(
    update(Booking)
    .where(Booking.id.in_(stale_ids), Booking.status == BookingStatus.running)
    .values(status=BookingStatus.pending, started_at=None, last_error=...)
    .execution_options(synchronize_session=False)
)
```

---

## 每用户单活跃任务

`has_active()`（SELECT）与 `create()`（INSERT）之间是 **TOCTOU**，DB 层没有约束。两个几乎同时的 `POST /bookings`（双击）都通过检查 → 建出两个 pending → 两个 worker 并行抢同一账号。

**修复**：部分唯一索引 + 接口兜底。

```python
# 模型 __table_args__（migration 0005 同步创建）
Index(
    "uq_booking_one_active_per_user", "user_id", unique=True,
    postgresql_where=text("status IN ('pending', 'running')"),
)
```

```python
# 接口：撞索引 → 409
try:
    return booking_crud.create(db, user.id)
except IntegrityError:
    db.rollback()
    raise HTTPException(409, "已有进行中的任务，完成或取消后再新建")
```

> [!note] 模型与迁移要同步
> 测试用 `Base.metadata.create_all`（读模型），生产用 alembic。所以唯一索引**模型 `__table_args__` 和迁移 `0005` 两边都要有**，否则测试环境拿不到约束。

---

## cancel 与 complete 后写者覆盖

`cancel()` 和 `complete()`（worker result 调用）都无行锁读取、UPDATE 也无状态守卫 → 谁后提交谁赢。cancel 与 worker 完成并发时，可能把 `done` 覆盖成 `cancelled`（考位已抢到却显示取消，用户拿不到确认）。

**修复**：两条路径都改用行锁 + 锁后复检。

```python
def get_for_update(db, booking_id):
    return db.get(Booking, booking_id, with_for_update=True)
```

- `cancel()`：`db.get(..., with_for_update=True)` 后复检状态再写。
- worker `report_result`：改用 `get_for_update`，使 **fencing 校验 + 状态校验 + 写终态**在同一行锁下原子完成，与 cancel 串行化。

---

## StaleClaimError 被吞

`worker/road_adapter.py` 的 `_report_progress` 用裸 `except Exception` 捕获，**把 `StaleClaimError` 也吞了**（见 [[worker-fencing-token]]）。被接管的旧 worker 进度上报 409 后不会立即停，要等下一次 `should_continue` 轮询。无数据损坏（后端仍拒绝写入），但削弱了响应速度。

**修复**：单独 `except StaleClaimError: raise`，让它穿过 `run()` 抛到 `_execute_task` 的处理逻辑。

---

## worker 超额认领

主循环 `pool.submit` 无容量闸门，超出并发数的任务被标 `running` 却在队列空等 → 被 reaper 误判超时重排（attempt 反复自增）。

**修复**：`threading.Semaphore(max_concurrent)`，认领前 `acquire`，任务结束 `release`。

```python
slots = threading.Semaphore(settings.max_concurrent)
...
if not slots.acquire(timeout=settings.poll_interval_seconds):
    continue
# claim 失败 / 无任务时记得 slots.release()
pool.submit(_run_and_release, task)   # _run_and_release 在 finally 里 release
```

---

## 验证

- 新增 `test_db_unique_index_blocks_second_active`（绕过 has_active 直插第二个活跃任务 → `IntegrityError`）、`test_admin_limit_is_bounded`。
- 既有用例全绿；迁移链 `0001→0005` 干净库验证通过，索引 DDL 正确。

## 关联

- 起点是 [[worker-fencing-token]]；安全维度见 [[安全加固清单]]；审查方法见 [[代码审查-验证与误报]]。
- 部署含迁移 `0005`，见 [[部署流程-mycloud#含迁移的发布]]。
