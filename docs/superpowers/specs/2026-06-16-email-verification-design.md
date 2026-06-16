# 注册邮箱验证 — 设计文档

- 日期：2026-06-16
- 状态：已批准设计，待写实现计划

## 1. 背景

当前注册（`POST /auth/register`）只要邮箱格式合法就直接创建账号并返回 token，无法确认邮箱真实可达。需要加邮箱验证，确保用户填入的注册邮箱真实有效。

## 2. 关键决策（来自 brainstorm）

- **验证方式**：6 位数字**验证码**（不用验证链接——避免前端处理 `/verify?token` 路由 + 邮件绝对 URL + `/booking/` base path 的复杂）。
- **强制时机**：**注册时强制**——注册后立即发码，验证前不能登录/进面板。
- **发邮件**：复用系统 Gmail 账号，后端 `smtplib` **同步** SMTP 发送（注册不频繁，阻塞几秒可接受；不引入异步队列）。
- **验证码存储**：存 user 字段（不单独建表）。

## 3. 数据模型（user 加 3 字段，迁移 0003）

| 字段 | 类型 | 说明 |
|---|---|---|
| `email_verified` | bool，默认 false | 邮箱是否已验证 |
| `verify_code` | varchar(6)，可空 | 当前验证码（验证成功后清空） |
| `verify_code_expires` | timestamptz，可空 | 验证码过期时间（发码时 + 10 分钟） |

迁移 0003：user 加这 3 列。现有库是测试数据；存量用户 `email_verified` 默认 false（迁移后需重新验证或手动置 true，文档化）。

## 4. 后端 auth 流程

| 端点 | 行为 |
|---|---|
| `POST /auth/register` `{email, password}` | 若邮箱已存在 → 409。否则创建 user（`email_verified=false`）→ 生成 6 位码、存库（`verify_code` + `verify_code_expires=now+10min`）→ 发验证邮件 → **返回 `{message: "验证码已发送到邮箱"}`，HTTP 201，不返回 token**。 |
| `POST /auth/verify-email` `{email, code}` | 取 user；若已验证 → 返回友好提示（200，幂等）。校验 `verify_code` 匹配且未过期 → `email_verified=true`、清 `verify_code`/`verify_code_expires` → 返回 `TokenOut`（access+refresh，完成登录）。码错/过期 → 400。 |
| `POST /auth/resend-code` `{email}` | 取 user；已验证 → 友好提示。否则重新生成码 + 刷新过期 + 发邮件 → 返回 `{message}`。 |
| `POST /auth/login` | 认证通过后，若 `email_verified=false` → **403"邮箱未验证，请先验证"**；否则照常返回 token。 |

- `verify-email` / `resend-code` 加 slowapi 限速（沿用 `auth_rate_limit`，防验证码爆破/邮件轰炸）。
- 验证码生成：`secrets.randbelow` 生成 6 位（`f"{n:06d}"`）。

### schema（`app/schemas/auth.py`）
- 新增 `RegisterOut {message: str}`（register 不再返回 token）。
- 新增 `VerifyEmailIn {email: EmailStr, code: str}`、`ResendCodeIn {email: EmailStr}`、`MessageOut {message: str}`。
- `register` 的 response_model 改 `RegisterOut`；`verify-email` 返回 `TokenOut`。

## 5. 发邮件（新模块 `app/core/email.py`）

- 后端 `config.py` 新增：`smtp_host`（默认 `smtp.gmail.com`）、`smtp_port`（默认 587）、`smtp_user`、`smtp_password`、`smtp_from`（默认 = smtp_user）。
- `send_email(to: str, subject: str, body: str)`：用 `smtplib.SMTP` + STARTTLS + 登录 + 发送。失败抛异常（注册端点捕获 → 500 友好错误，不泄漏 SMTP 细节）。
- `send_verification_code(to: str, code: str)`：组装验证码邮件（中文正文，含码 + 10 分钟有效提示），调 `send_email`。
- 配置缺失（`smtp_user` 空）时 `send_email` 抛清晰错误。

## 6. 前端

- `api/auth`（store）：`register` 改为不存 token、返回后跳验证页；新增 `verifyEmail(email, code)`、`resendCode(email)`。
- **新增"验证邮箱"页** `views/VerifyEmail.vue`：显示目标邮箱、6 位码输入框、「验证」按钮、「重发验证码」按钮（60s 倒计时）。验证成功 → 存 token、进面板。
- `router`：加 `/verify` 路由（无需登录态）。
- `Register.vue`：注册成功后 `router.push('/verify?email=...')`（或经 store 暂存 email）。
- `Login.vue`：登录返回 403"邮箱未验证" → 提示并提供「去验证」链接到验证页。
- 弹窗风格沿用本轮的 `alert`（成功/失败提示）。

## 7. 安全

- 验证码 10 分钟过期；6 位随机（`secrets`）。
- `verify-email`/`resend-code` 限速（slowapi）。
- 验证成功立即清码（一次性）。
- 已验证邮箱重复 verify/resend 幂等友好处理，不报错、不泄漏账号是否存在的差异（resend 对不存在邮箱也返回同样的 `{message}`，避免枚举）。

## 8. 测试（后端，mock SMTP）

- **全程 mock `app.core.email.send_email`**，不真发邮件。
- 用例：
  - register → 201 + 返回 message（无 token）+ DB user `email_verified=false` 且 `verify_code` 已存。
  - verify-email 正确码 → 200 + 返回 token + DB `email_verified=true` 且码清空。
  - verify-email 错码 → 400；过期码 → 400（monkeypatch 过期时间）。
  - login 未验证 → 403；验证后 login → 200。
  - resend-code → 重新生成码（与旧码不同或刷新过期）+ mock send_email 被调。
  - 限速：连续多次 verify → 429（沿用现有限速测试模式，必要时单独开关）。
- conftest `auth_headers` / `ready_user` 需适配：注册后要先 verify 才能登录拿 token（或测试 fixture 直接在 DB 置 `email_verified=true` 跳过邮件流程，保持其它测试不被邮件流程拖累）。

## 9. 验收标准

- [ ] 注册不再直接返回 token；发了验证码（mock 可断言）。
- [ ] 未验证邮箱无法登录（403）。
- [ ] 正确验证码 → 激活 + 登录；错误/过期 → 拒。
- [ ] 重发验证码可用且限速。
- [ ] 前端：注册 → 验证页 → 输码 → 进面板；重发倒计时；登录未验证有引导。
- [ ] 后端测试全绿（mock SMTP）；前端 build 通过。
- [ ] 运维文档：后端 `.env` 配 SMTP_*（系统 Gmail）。

## 10. 已知遗留 / 约束

- 同步 SMTP 发送会让注册/重发阻塞几秒；上规模再转异步队列。
- 存量测试用户迁移后 `email_verified=false`，需重新验证或手动置 true。
- 注册邮箱 ≠ ICBC 账户邮箱 ≠ 系统收 OTP 的 Gmail：本功能只验证「平台登录邮箱」的真实性。
- 未做"修改注册邮箱"流程（YAGNI，需要再加）。
