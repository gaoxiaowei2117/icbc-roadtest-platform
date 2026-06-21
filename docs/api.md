# API 文档

Base URL：`https://gogoxoxo.duckdns.org:9443/api`

## 鉴权
除 `/auth/*` 和 `/health` 外都需要 `Authorization: Bearer <access_token>` 头。

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

### POST /bookings
请求体为空或 `{}`。抢号参数来自用户档案。

**前置条件**：用户必须已填驾照号、姓氏、考试类型、考点、日期区间和 keyword。每个用户同一时间只能有一个 `pending` 或 `running` 任务。

### GET /bookings/{id}
### POST /bookings/{id}/cancel

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
  "status": "done",        // done | failed
  "last_error": null,      // failed 时填
  "result": { "confirmation_no": "ABC123", "booked_at": "..." }
}
```

## Admin

### GET /admin/bookings?status_filter=...&limit=...
返回所有用户的任务，仅 `is_admin=true` 可访问。
