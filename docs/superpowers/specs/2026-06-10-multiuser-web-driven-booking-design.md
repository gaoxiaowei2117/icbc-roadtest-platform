# 网页配置驱动抢号（多用户化）— 设计文档

- 日期：2026-06-10
- 状态：已批准设计，待写实现计划
- 前置：单用户阶段已完成（见 `2026-06-09-road-py-booking-engine-integration-design.md`）

## 1. 背景

单用户阶段已把 road.py 真实抢号接进 worker，但抢号参数全部来自本地 `worker/config.yml`，**网页上配的东西并没有驱动抢号**——`road_adapter.run(task)` 基本忽略 task。

本阶段目标：让用户在网页上配置的抢号参数真正驱动抢号。核心是把"参数来源"从本地 yaml 改成"云端 DB 中每个用户的抢号档案"。

## 2. 关键决策（来自 brainstorm）

- **多用户无协调，直接抢**：号冲突由 ICBC 服务端 `put_lock` 仲裁，客户端不需要任何全局锁/串行化。worker 各 booking 任务独立并发跑。
- **共享系统 Gmail 收 OTP**：所有用户的 ICBC 邮箱经 `emailReplace` 临时改成同一个系统 Gmail；Gmail 配置是**系统级**（worker `.env`，由运维在后台配），不进前端、不每用户存。OTP 邮件无用户标识，罕见的秒级并发下单冲突 → 靠 road.py 现有去重/时间窗 + 失败重试兜底，不加控制逻辑。
- **薄封装不变**：road_adapter 仍调 `road.job(config)`，只是 `config` 从 DB 档案构造，而非读 yaml。
- **secret 改存 keyword**：ICBC 登录用 lastName+licenceNumber+keyword，当前 secret 存的 username/password 对登录无用，直接替换为加密存 keyword（复用现有 SealedBox 链路）。
- **完整对齐 road.py**：前端表单与数据模型覆盖 road.py 用到的全部抢号参数。

## 3. 数据模型

### user 表新增字段（抢号档案）

| 字段 | 类型 | 对应 road.py config['icbc'] | 说明 |
|---|---|---|---|
| `exam_class` | varchar | examClass | 考试类型，如 "5"（拼成 examType=`{exam_class}-R-1`） |
| `pos_ids` | JSON 数组 | posID | 考点 ID 数组（前端从 csv 多选）；worker 对每个轮询 |
| `expect_after_date` | date | expactAfterDate | 期望日期区间起 |
| `expect_before_date` | date | expactBeforeDate | 期望日期区间止 |
| `expect_time_range` | varchar | expactTimeRange | 时间区间，如 "10:00-17:00" |
| `pref_days_of_week` | JSON 数组 | prfDaysOfWeek | 星期偏好 [0-6] |
| `pref_parts_of_day` | JSON 数组 | prfPartsOfDay | 一天部分 [0,1]（0=上午,1=下午） |

- **保留**：`icbc_license_no`、`icbc_last_name`（登录用）。
- **移除**：`preferred_pos`（被 `pos_ids` 取代）、`time_windows`（被 `expect_time_range`+`pref_parts_of_day` 取代）、`max_wait_days`（被日期区间取代）。

### secret 表（语义变更）

- `ciphertext` 改为存 **keyword**（SealedBox 加密），不再是 "username\npassword"。
- 加解密链路不变（后端公钥加密、worker 私钥解密）。

### booking 表（简化为纯触发器）

抢号参数已全部移到 user 档案，booking 不再承载参数：
- **移除** `target_date`、`time_window`、`pos_code`（这些现在来自 user 档案）。
- **保留** `status`、`attempt_count`、`last_error`、`result`、`started_at`、`finished_at`、时间戳。
- booking 的语义变成"对当前 user 档案发起一次抢号"。

### 迁移

- 一个 alembic 迁移：user 加 7 列、删 3 列；secret 语义变更（无需改列结构，仅内容含义变）。
- 现有库是测试数据，迁移时清空 user/secret/booking 重建，不写数据搬迁逻辑。

## 4. 参数流

```
前端 Settings 表单 → 后端存 user 档案 + secret(keyword 密文)
worker claim → WorkerClaimOut 返回该 user 完整档案 + keyword 密文
  → road_adapter:
       私钥解 keyword
       config['icbc'] = {drvrLastName, licenceNumber, keyword, examClass,
                         posID(逐个), prfDaysOfWeek, prfPartsOfDay,
                         expactAfterDate, expactBeforeDate, expactTimeRange}
       config['gmail'] = 系统级（worker .env: GMAIL_EMAIL/GMAIL_APP_PASSWORD）
       config['emailReplace'] = {enable: true}
       config['autoBooking'] = {enable: true, ...默认策略}
       for pos_id in pos_ids:
           config['icbc']['posID'] = pos_id
           限时循环内调 road.job(config)；任一 posID 成交即返回 Result(success)
```

### WorkerClaimOut 扩展

现有：`booking_id, user_id, target_date, time_window, pos_code, secret_ciphertext, max_wait_days`
改为：`booking_id, user_id, drvr_last_name, licence_number, keyword_ciphertext, exam_class, pos_ids, expect_after_date, expect_before_date, expect_time_range, pref_days_of_week, pref_parts_of_day`

### road_adapter 变化

- `run(task)` 不再读 `road_config_path`；改从 task 字段构造 config dict。
- Gmail 段从 worker `settings`（新增 `gmail_email` / `gmail_app_password`）填。
- 多 posID：在限时循环里对 `pos_ids` 逐个调 `road.job`，命中即返回。
- 仍保留：限时循环、超时、单轮 job 异常重试、邮箱 restore 兜底。

## 5. 后端 API / schema

- `UserUpdate` / `UserPublic` schema 加抢号档案字段；`PATCH /users/me` 接收。
- `SecretIn` 从 `{icbc_username, icbc_password}` 改为 `{keyword}`。
- `BookingCreate` 简化：不再接收 target_date/time_window/pos_code（参数来自档案），建任务无 body 或仅空对象。`BookingOut` 去掉对应字段。
- 新增 `GET /api/pos-list`：返回考点字典（name→posID），供前端下拉。后端从 `icbc_pos_list.csv` 加载（文件随仓库附带 `backend/app/data/icbc_pos_list.csv`）。
- 建 booking 的前置校验更新：要求档案完整（license/lastName/keyword/exam_class/pos_ids/日期区间）才能建任务。

## 6. 前端（Settings 页完整对齐）

- ICBC 登录区：驾照号、姓氏、**keyword**（密码框）。
- 抢号偏好区：
  - 考试类型：下拉
  - 考点：多选（从 `GET /api/pos-list` 渲染，显示名称、提交 posID）
  - 日期区间：两个 date picker（after/before）
  - 时间区间：起止时间输入（拼成 "HH:MM-HH:MM"）
  - 星期：7 个 checkbox → [0-6]
  - 一天部分：上午/下午 checkbox → [0,1]
- `vue-tsc` 类型通过、`npm run build` 通过。

## 7. 系统级 Gmail 配置

- worker `config.py` 新增 `gmail_email` / `gmail_app_password`（从 `.env` 读）。
- `worker/.env.example` 补占位与说明；真实值由运维填 `worker/.env`（已 gitignore）。

## 8. 测试

- **后端**：user 档案 CRUD、`PATCH /users/me` 存取档案、`PUT /users/me/secret` 存 keyword 且 DB 为密文、claim 返回完整档案 + keyword 密文（私钥解密往返）、`GET /pos-list` 返回非空、建 booking 前置校验。
- **worker**：road_adapter 从档案 dict 正确构造 config['icbc']（mock road.job 断言传入 config）、多 posID 轮询（mock job 第一个 posID no_appointments、第二个 booking_success）、keyword 解密、Gmail 系统配置注入。
- **前端**：vue-tsc + build。

## 9. 验收标准

- [ ] 用户在网页填完整抢号档案 + keyword → 建任务 → worker 用**该用户档案**真实抢号（dry-run 验证 config 构造正确）。
- [ ] secret 存的是 keyword 密文，DB 无明文，worker 私钥可解。
- [ ] 多 posID 轮询生效。
- [ ] 后端测试 + worker road_adapter 测试全绿；前端构建通过。
- [ ] 系统 Gmail 由 worker `.env` 注入，不出现在前端/DB/仓库。
- [ ] known-issues：多用户化标记完成，OTP 共享 Gmail 的并发局限记为已知约束。

## 10. 已知遗留 / 约束

- OTP 共享 Gmail：秒级并发下单可能 OTP 串（罕见，失败重试兜底）；规模上去需转每用户 Gmail。
- emailReplace 把用户 ICBC 邮箱临时改系统 Gmail：抢号期间用户收不到 ICBC 自家通知；成功/兜底后 restore。
- autoBooking 策略（重试次数、超时、timeSelectionStrategy）本阶段用系统默认，暂不开放给用户配。
- vendor road.py 与上游手动同步（沿用上阶段约束）。
