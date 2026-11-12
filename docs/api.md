# API 文档

Base URL：`https://roadtestgo.com/api`

## 鉴权
除 `/auth/*`、`/health`、`GET /pos-list`、`GET /route-packs`、`GET /route-packs/{slug}` 和 Stripe webhook 外都需要 `Authorization: Bearer <access_token>` 头。
`GET /route-packs[/{slug}]` 可匿名访问；带上 token 时会额外返回 `purchased`，token 无效时返回 401（前端据此刷新 token）。

## 认证

### POST /auth/register
```json
{ "email": "user@example.com", "password": "********" }
```
返回 `201`：
```json
{ "message": "验证码已发送到邮箱，请查收并验证" }
```

### POST /auth/verify-email
```json
{ "email": "user@example.com", "code": "123456" }
```
返回 `TokenOut`（access + refresh）。

### POST /auth/resend-code
```json
{ "email": "user@example.com" }
```
返回通用提示，不泄露邮箱是否存在。

### POST /auth/login
```json
{ "email": "user@example.com", "password": "********" }
```
返回 `TokenOut`。

### POST /auth/refresh
```json
{ "refresh_token": "..." }
```
返回新的 `AccessTokenOut`。

## 用户

### GET /users/me
返回当前用户完整资料（含 `is_admin`、`icbc_*` 字段）。

### PATCH /users/me
更新资料（所有字段可选）：
```json
{
  "icbc_license_no": "1234567",
  "icbc_last_name": "Smith",
  "exam_class": "5",
  "pos_ids": [274],
  "expect_after_date": "2026-07-01",
  "expect_before_date": "2026-07-31",
  "expect_time_range": "09:00-17:00",
  "pref_days_of_week": [0, 1, 2, 3, 4, 5, 6],
  "pref_parts_of_day": [0, 1]
}
```

### PUT /users/me/secret
```json
{ "keyword": "********" }
```
ICBC keyword 会用 libsodium SealedBox 公钥加密后存 DB。云端只持 `SECRET_PUBLIC_KEY`，不能解密；worker 持 `SECRET_PRIVATE_KEY` 后才能解密执行任务。

### GET /users/me/secret
返回 `{ has_secret, updated_at }`，不会返回明文。

### DELETE /users/me/secret
删除凭据。

## 任务

### GET /bookings
返回当前用户所有任务，按 `created_at desc`。
每条任务包含：
- `attempt_count`：worker 认领该任务的次数
- `progress_rounds`：worker 已成功上报的累计考点查询次数；多个考点会分别计数
- `last_progress` / `last_progress_at`：最近一次脱敏进度摘要与时间

### POST /bookings
请求体为空或 `{}`。抢号参数来自用户档案。

**前置条件**：用户必须已填驾照号、姓氏、考试类型、考点、日期区间和 keyword。每个用户同一时间只能有一个 `pending` 或 `running` 任务。

### GET /bookings/{id}
### POST /bookings/{id}/cancel

## 路线包（练习路线）

按考场售卖的练习路线包：每个包有若干路线，每条路线 1–3 段（Google 地图 App 链接最多 9 个途经点，长路线拆段），每段一个 Google 地图导航链接。包定义在后端数据文件（默认 `backend/app/data/route_packs.json`，见部署文档）。**链接只会通过 `/links` 返回给已购买的用户。**

### GET /route-packs
公开。返回所有路线包（不含链接）：
```json
[{
  "slug": "burnaby-4399",
  "name": "ICBC Burnaby Claim Centre (4399 Wayburne Dr)",
  "name_zh": "ICBC 本拿比考场（4399 Wayburne Dr）",
  "centre": "4399 Wayburne Dr, Burnaby, BC",
  "price_cents": 1499,
  "currency": "cad",
  "route_count": 4,
  "routes": [{ "title": "路线 1", "segment_count": 2 }],
  "checkout_enabled": false,
  "purchased": null
}]
```
- `purchased`：匿名请求为 `null`；登录用户为 `true/false`（管理员收回后为 `false`）。
- `checkout_enabled`：Stripe 密钥、Webhook 密钥和该包的 Price ID 都配置后才为 `true`；否则前端显示“即将开放 / 联系我们”。

### GET /route-packs/{slug}
同上，单个包。未知 slug 返回 404。

### GET /route-packs/{slug}/links
需登录。已购买返回：
```json
{ "slug": "burnaby-4399",
  "routes": [{ "title": "路线 1", "segments": [{ "label": "第 1 段", "url": "https://www.google.com/maps/dir/?api=1&..." }] }] }
```
未购买或已被收回返回 `403`。

### POST /route-packs/{slug}/checkout
需登录。创建一次性付款（`mode=payment`）的 Stripe Checkout，返回 `{ "url", "session_id" }`，前端跳转到 `url`。
- 未配置返回 `503`；已购买返回 `409`；未知 slug 返回 `404`；Stripe 出错返回 `502`。
- 23 小时内未完成的同一包会话会被复用，不会重复创建。
- Session metadata：`{ "kind": "route_pack", "pack_slug": "...", "user_id": "..." }`；PaymentIntent 带同样的 metadata。
- 成功/取消后回到 `{APP_BASE_URL}{FRONTEND_BASE_PATH}/routes?pack=<slug>&checkout=success|cancelled`。

## 付款（Stripe）

### POST /payments/stripe/webhook
Stripe 调用，校验 `Stripe-Signature`。处理 `checkout.session.completed`、`checkout.session.async_payment_succeeded`、`checkout.session.async_payment_failed`、`checkout.session.expired`：
- metadata `kind=route_pack`：付款成功后为该用户开通路线包（每个用户每个包一条记录，重复投递幂等）。
- 其它（`booking_id`）：原有执行次数流程，不变。

`payment` 表新增 `kind`（`execution_pass` / `route_pack`）和 `product_ref`（路线包 slug）。

## Worker（共享密钥）

### POST /worker/claim
头：`X-Worker-Key: $WORKER_API_KEY`

无 pending 任务时返回 `null`。有任务时返回：
```json
{
  "booking_id": 42,
  "user_id": 7,
  "drvr_last_name": "Smith",
  "licence_number": "1234567",
  "keyword_ciphertext": "base64...",
  "exam_class": "5",
  "pos_ids": [274],
  "expect_after_date": "2026-07-01",
  "expect_before_date": "2026-07-31",
  "expect_time_range": "09:00-17:00",
  "pref_days_of_week": [0, 1, 2, 3, 4, 5, 6],
  "pref_parts_of_day": [0, 1]
}
```

后端用数据库行锁原子认领任务；多个 worker 或多个 worker 容器可以同时轮询，不会领取同一个 `pending` 任务。

### POST /worker/bookings/{id}/result
头：`X-Worker-Key: $WORKER_API_KEY`
```json
{
  "status": "done",        // pending | done | failed
  "last_error": null,      // failed 时填
  "result": { "confirmation_no": "ABC123", "booked_at": "..." }
}
```

`pending` 表示本次 600 秒执行周期没有抢到号，但任务仍可重试。后端会清空本轮运行状态并重新排队，`last_error` 应为 `null`。

### POST /worker/bookings/{id}/progress
头：`X-Worker-Key: $WORKER_API_KEY`
```json
{ "message": "考点 274 查询结果 no_appointments" }
```
后端只保存累计轮次、最近进度摘要和时间，供用户页面判断任务是否仍在运行；不要上传明文 credential、验证码、HTTP token 或完整 ICBC/Gmail 响应。

### GET /worker/bookings/{id}/status

头：`X-Worker-Key: $WORKER_API_KEY`

返回 `{ "id": 42, "status": "running" }`。worker 在查询期间用它检测用户是否已取消任务。

## Admin

### GET /admin/bookings?status_filter=...&limit=...
返回所有用户的任务，每条包含 `user_id` 和 `user_email`，仅 `is_admin=true` 可访问。

### GET /admin/users?limit=...
返回用户列表和当前 ICBC/预约配置。`has_secret` 仅表示 keyword 是否已配置，不返回密码哈希、keyword 密文或明文。仅 `is_admin=true` 可访问。

### DELETE /admin/users/{user_id}
删除普通用户，并级联删除该用户的任务和加密凭据。管理员账号不允许通过此接口删除。

### GET /admin/route-packs/purchases?limit=...
返回路线包开通记录（含 `user_email`、`pack_slug`、`status`=`active|revoked`、`source`=`stripe|manual`）。

### POST /admin/route-packs/{slug}/grant
```json
{ "email": "user@example.com" }
```
手动开通（线下收款或测试）。重复开通无副作用；对已收回的记录会重新激活。slug 或用户不存在返回 404。

### POST /admin/route-packs/{slug}/revoke
```json
{ "email": "user@example.com" }
```
收回访问权（例如 Stripe 退款后需手动收回；本接口不会退款）。没有开通记录返回 404。
