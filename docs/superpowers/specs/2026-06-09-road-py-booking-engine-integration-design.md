# 接入 road.py 真实抢号逻辑（单用户阶段）— 设计文档

- 日期：2026-06-09
- 状态：已批准设计，待写实现计划
- 范围阶段：**单用户先真实跑通**（多用户化是后续独立阶段）

## 1. 背景

`worker/booking_engine.py` 当前是 stub：`run(task)` 直接抛 `BookingEngineError("booking_engine 尚未接入 road.py 真实逻辑")`。platform 的其余链路（注册 / 建任务 / worker claim / SealedBox 凭据加解密 / 回报 / reaper / 限速）已全部验证通过——只差这一个 stub 没接真实抢号。

权威抢号逻辑在独立项目 `/home/xgao/workspace/icbc-roadtest-auto-booking/road.py`（约 79KB）。它是成熟的、用 `requests` 直连 ICBC `deas-api` 的脚本，**不用浏览器自动化**。

## 2. 目标与非目标

### 目标
- 把 road.py 的真实抢号接进 `booking_engine.run()`，用 road.py 现有 `config.yml`（单用户账号 + Gmail）真实跑通，验证能真抢到号。
- 接入方式不破坏 platform 现有 `Task` / `Result` 接口与 worker 主循环。

### 非目标（本阶段不做，记入已知遗留）
- 多用户化：每用户独立的 keyword / Gmail / examClass / 时间偏好，以及多用户 OTP 架构。
- 数据模型扩展（user/secret 加字段）。
- road.py 本身的重构。

## 3. road.py 关键事实（设计依据）

- **顶层 import 干净**：road.py 顶部只有 import、函数定义、两个常量；`main()` 在 `if __name__ == "__main__"` 守卫内。→ 可安全 `import` 当库用，无副作用。
- **依赖少**：`requests`、`PyYAML`、`faker`。
- **`job(config)` 即"一轮抢号"**：内部依次做
  登录（`get_weblogin`，三要素 lastName+licenceNumber+keyword）
  → `ensure_email_synced`（emailReplace：把 ICBC 账户邮箱临时改成可读的 Gmail 以收 OTP）
  → 查时段（`get_appointments`）→ `select_best_appointment`
  → `attempt_booking`（锁位 → sendOTP → 从 Gmail IMAP 读验证码 → 提交 → 确认）
  → 成功后 `save_booking_status` + `restore_original_email` + 通知。
  返回状态字符串：`booking_success` / `already_booked` / `no_appointments` / `token_failed` / `completed` / `notification_sent_paused` 等。
- **dry-run 天然支持**：`autoBooking.enable=false` 时 `job()` 只"查到号发通知"不下单。

## 4. 架构

```
platform worker（已有，无需改）
  └─ claim task → booking_engine.run(task)          [改：委托，不再 stub]
        └─ road_adapter.run(task) -> Result          [新]
              ├─ load_config(ROAD_CONFIG_PATH)        读 config.yml
              └─ 限时循环（默认 10min，< reaper 15min）:
                    status = vendor.road.job(config)  ← 一轮：登录→查→抢→确认
                    ├─ booking_success / already_booked → Result(success=True, …)
                    ├─ no_appointments / completed / token_failed / 其它 → sleep(间隔) 继续
                    └─ 到时限 → Result(success=False, error="超时未抢到")
  └─ report 结果回 platform（已有）
```

## 5. 组件清单

| 文件 | 动作 | 职责 |
|---|---|---|
| `worker/vendor/road.py` | 新（复制） | 原样 vendor 进来；import 干净，不修改 |
| `worker/vendor/__init__.py` | 新 | 空包标记 |
| `worker/road_adapter.py` | 新 | 核心适配器：config 加载、限时循环、`job()` 状态→`Result` 映射、confirmation 提取、emailReplace 失败兜底 |
| `worker/booking_engine.py` | 改 | `run(task)` 委托给 `road_adapter.run(task)`；`Task` / `Result` / `BookingEngineError` 接口不变 |
| `worker/config.yml` | 新（占位化复制） | road.py 所需 yaml；敏感真值放 gitignore 的实际文件，仓库内为占位 |
| `worker/config.py` | 改 | 新增 `road_config_path`（默认 `./config.yml`）、`booking_timeout_seconds`（默认 600）、`booking_poll_seconds`（默认 30） |
| `worker/requirements.txt` | 改 | 放开/新增 `requests`、`PyYAML`、`faker` |
| `worker/tests/test_road_adapter.py` | 新 | mock `road.job()` 覆盖限时循环 / 状态映射 / 超时 / config 加载 |

## 6. 接口契约（不变）

`booking_engine.run(task: Task) -> Result` 签名与现有完全一致。`Task` / `Result` dataclass 不改。

**单用户简化**：`run(task)` 此阶段基本忽略 `task` 的凭据 / 偏好字段（全部来自 config.yml），`task` 仅用于日志关联 `booking_id`。platform 在本阶段扮演"触发器 + 状态记录"。

## 7. 限时循环算法（road_adapter.run）

```
config = load_config(road_config_path)
deadline = monotonic() + booking_timeout_seconds
while monotonic() < deadline:
    status = road.job(config)        # @safely_run 包裹，自身不会抛
    if status in ("booking_success", "already_booked"):
        info = road.load_booking_status(config)
        return Result(success=True, booked_at=info.date+time, confirmation_no=…, details=info)
    # no_appointments / completed / token_failed / notification_sent_paused / None 等 → 继续
    sleep(min(booking_poll_seconds, 剩余时间))
return Result(success=False, error="到达时限仍未抢到号")
```

- `booking_timeout_seconds`（默认 600s = 10min）严格 < reaper 的 `RUNNING_TIMEOUT_MINUTES`（15min），避免运行中任务被误判卡死。
- `token_failed`（含 ICBC 403 限流）按"继续重试"处理，由 road.py 内部与本循环共同退避。
- 并发：单用户阶段建议 worker `MAX_CONCURRENT=1`，规避 road.py 中 `global _web_appointments` 的并发竞争。

## 8. 安全 / 风险控制

1. **dry-run 先行**：上线真实下单前，先 `autoBooking.enable=false` 跑，验证登录通、能查到号、`job()` 状态流转正常；确认无误再切 `enable=true` 真实下单。真实抢号会**真占考位、真改 ICBC 账户邮箱**。
2. **凭据不入库不进日志**：config.yml 真值（含 Gmail app password、licenceNumber）走 gitignore；仓库内只留占位。road_adapter 不打印凭据明文。
3. **emailReplace 兜底**：road.py 仅在成功路径 `restore_original_email`。适配器在循环结束（含异常 / 超时）的 `finally` 中尽力 restore，避免 ICBC 账户邮箱长期停在替换态。

## 9. 测试策略

- 真实抢号端到端无法自动化（会真实下单），靠 dry-run + 人工观察。
- `test_road_adapter.py`（mock `vendor.road.job`）覆盖：
  - `booking_success` → `Result.success=True` 且带 confirmation
  - `no_appointments` 反复 → 到时限 → `Result.success=False`
  - 超时边界：循环在 deadline 后停止，不超调
  - config 加载失败 → 清晰错误
  - `finally` 调用 `restore_original_email`（mock 断言被调用）

## 10. 验收标准

- [ ] `booking_engine.run()` 不再是 stub，委托 road_adapter，接口未变。
- [ ] dry-run 模式下，真实连 ICBC：登录成功、能查到时段、`job()` 状态正确映射为 `Result`。
- [ ] `test_road_adapter.py` 全绿；现有 backend pytest 套件不受影响。
- [ ] 真实模式（`enable=true`）由用户在确认 dry-run 通过后手动开启并人工验证抢到号。
- [ ] known-issues 更新：T1 标记本阶段完成范围，多用户化 / 失败 restore / vendor 同步列为后续。

## 11. 已知遗留（本阶段不解决）

- 多用户化（每用户 keyword/Gmail/偏好 + 多用户 OTP 架构）——下一阶段独立 spec。
- road.py 失败路径原生不 restore 邮箱（适配器 finally 兜底，但 road.py 本身不改）。
- vendor 的 road.py 与上游 auto-booking 项目需手动同步升级。
