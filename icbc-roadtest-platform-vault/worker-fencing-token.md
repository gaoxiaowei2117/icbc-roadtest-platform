---
title: Worker fencing token — 防止过期认领覆盖正在进行的运行
date: 2026-06-30
tags:
  - icbc-platform
  - bug-fix
  - worker
  - 并发
pr: 4
severity: 高
aliases:
  - fencing token
  - 过期认领
  - 认领令牌
---

# Worker fencing token

> [!bug] 问题（High）
> `/api/worker/*` 的 progress/result/status 端点只按 `booking_id` + 共享 `X-Worker-Key` 鉴权，**不绑定具体哪一次认领**。worker A 慢/断网 → reaper 把任务重排回 pending → worker B 重新认领 → A 恢复后回报 done，A 会**覆盖 B 正在进行的那次运行**；A 若回报 `pending` 还能把 B 的 running 任务 requeue，导致**两个 worker 并行抢同一账号**（用真实凭据对 ICBC/Gmail 重复操作）。

## 为什么协作式检查挡不住

worker 的 `should_continue()` 只比较 `status == "running"`。reaper 重置 + B 重认领后状态又变回 `running`，A 无法区分是"自己那次"还是"B 那次"；而且状态查询失败时它会**保守地继续**（fail-open）。所以仅靠状态轮询无法防覆盖。

## 修复：fencing token（复用 `attempt_count`，无需迁移）

`booking.attempt_count` 每次认领自增，天然就是 fencing token。

- `/claim` 在响应里下发 `attempt`（= 本次认领时的 `attempt_count`）
- `/result`、`/progress`、`/status` **必须携带 `attempt`**，与当前 `attempt_count` 不一致即 **409**
- worker 全程透传 `attempt`：
  - `booking_status` 收到 404/409 → 返回 `None` → `should_continue` 停止本轮
  - `report` / `report_progress` 收到 409 → 抛 `StaleClaimError`，worker 捕获后**放弃回写**

```python
# backend：后端守卫
def _check_fencing(booking, attempt):
    if attempt != booking.attempt_count:
        raise HTTPException(409, "认领已过期（任务已被重排并重新认领）")
```

> [!important] requeue 必须保留 attempt_count
> `requeue()` 把任务退回 pending 时**不能重置 attempt_count**，否则下次认领的 token 会和上一次撞上，fencing 失效。当前实现正确保留。

## 验证（线上实测）

| 请求 | 期望 | 实测 |
|---|---|---|
| `/result` 无 `attempt` | 422 | ✅ |
| `/result` 过期 `attempt` | 409 | ✅ |
| `/status` 过期 `attempt` | 409 | ✅ |
| 端到端：claim→requeue→重认领→旧 attempt 回报 | 被拒，新运行不被覆盖 | ✅ |

## 后续加固（PR #5）

- `road_adapter._report_progress` 原本用裸 `except Exception` **吞掉了 `StaleClaimError`**，导致进度路径的 409 到不了处理逻辑 —— 在 [[并发竞态-booking状态机#StaleClaimError 被吞]] 中修复。
- worker `result` 端点改为**行锁**读取，与 cancel 串行化 —— 见 [[并发竞态-booking状态机#cancel 与 complete 后写者覆盖]]。

## 关联

- 这是 [[代码审查-验证与误报]] 里"finding #1"对应的修复，也是整轮并发审查的起点。
- 部署需后端 + worker **协同发布**（`attempt` 必填）—— 见 [[部署流程-mycloud]]。
