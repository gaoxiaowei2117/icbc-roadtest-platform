# API 文档

Base URL：`https://gogoxoxo.duckdns.org:9443/api`

## 鉴权
除 `/auth/*` 和 `/health` 外都需要 `Authorization: Bearer <access_token>` 头。

## 认证

### POST /auth/register
```json
{ "email": "user@example.com", "password": "********" }
```
返回 `201` + `TokenOut`（access + refresh）。

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
  "preferred_pos": ["Vancouver", "Burnaby"],
  "time_windows": { "morning": true, "afternoon": true, "evening": false },
  "max_wait_days": 60
}
```

### PUT /users/me/secret
```json
{ "icbc_username": "user", "icbc_password": "********" }
```
凭据会以 Fernet 加密后存 DB。

### GET /users/me/secret
返回 `{ has_secret, updated_at }`，不会返回明文。

### DELETE /users/me/secret
删除凭据。

## 任务

### GET /bookings
返回当前用户所有任务，按 `created_at desc`。

### POST /bookings
```json
{
  "target_date": "2026-07-01",   // 可空
  "time_window": { "morning": true, ... },
  "pos_code": "Vancouver"          // 可空
}
```
**前置条件**：用户必须已填 ICBC 资料和凭据。

### GET /bookings/{id}
### POST /bookings/{id}/cancel

## Worker（仅 admin 共享密钥）

### POST /worker/claim
头：`X-Worker-Key: $WORKER_API_KEY`

无 pending 任务时返回 `null`。有任务时返回：
```json
{
  "booking_id": 42,
  "user_id": 7,
  "target_date": "2026-07-01",
  "time_window": { "morning": true, ... },
  "pos_code": null,
  "icbc_username": "user",
  "icbc_password": "********",   // 明文（仅本机）
  "max_wait_days": 60
}
```

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
