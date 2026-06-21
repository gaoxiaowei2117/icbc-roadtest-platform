# 架构

## 组件
- **VPS（广州腾讯云）**：FastAPI + PostgreSQL + Nginx，承载前端 / API / 数据库
- **本地电脑（温哥华）**：Python worker，跑实际抢约；推荐用 Docker 跑一个或多个实例
- **通信**：worker 主动出站拉任务，云端不知道 worker 在哪

## 数据流

```
用户浏览器
   │  HTTPS
   ▼
Nginx (9443)
   ├─ /booking/*  →  静态 SPA
   └─ /api/*      →  FastAPI (8000)
                       │
                       ▼
                    Postgres
                       ▲
                       │ claim / report
                       │
                  worker.py / Docker worker (本地)
                       │
                       ▼
                  booking_engine.run(task)
                       │
                       ▼
                  road_adapter → vendor/road.py → ICBC HTTP API
```

`booking_engine.run()` 当前委托给 `worker/road_adapter.py`，适配器按任务档案构造 `vendor/road.py` 需要的配置并限时轮询。当前工程不依赖 Playwright。

## 数据模型

### user
| 字段 | 类型 | 说明 |
|---|---|---|
| id | int | 主键 |
| email | varchar(255) | 唯一 |
| password_hash | varchar(255) | bcrypt |
| is_active | bool | |
| is_admin | bool | 管理员标志 |
| email_verified | bool | 邮箱是否已验证 |
| verify_code | varchar(6) | 邮箱验证码 |
| verify_code_expires | timestamp | 验证码过期时间 |
| icbc_license_no | varchar(50) | 驾照号 |
| icbc_last_name | varchar(100) | 姓氏 |
| exam_class | varchar(10) | 考试类型 |
| pos_ids | json | 考点 ID 数组 |
| expect_after_date | date | 期望最早日期 |
| expect_before_date | date | 期望最晚日期 |
| expect_time_range | varchar(20) | 期望时间段，如 `09:00-17:00` |
| pref_days_of_week | json | 星期偏好，0=周一 |
| pref_parts_of_day | json | 时段偏好，0=上午、1=下午 |

### secret
| 字段 | 类型 | 说明 |
|---|---|---|
| id | int | 主键 |
| user_id | int | 唯一外键 → user |
| ciphertext | bytea | SealedBox(X25519+XSalsa20-Poly1305) 加密的 ICBC keyword；只有 worker 私钥可解 |

### booking
| 字段 | 类型 | 说明 |
|---|---|---|
| id | int | 主键 |
| user_id | int | 外键 → user |
| status | enum | pending/running/done/failed/cancelled |
| attempt_count | int | 已尝试次数 |
| last_error | text | 最后一次错误 |
| result | jsonb | 成功时存 confirmation_no 等 |
| started_at | timestamp | 第一次进入 running |
| finished_at | timestamp | 进入终态 |

## 安全要点
1. **凭据加密（非对称封装）**：ICBC 凭据用 libsodium **SealedBox**（X25519 + XSalsa20-Poly1305）加密存 DB。
   - 云端只持**公钥**（`SECRET_PUBLIC_KEY`），**只能加密、无法解密**。
   - **私钥**（`SECRET_PRIVATE_KEY`）只放本地 worker 的 `.env`，是全系统唯一能还原明文的地方。
   - claim 时密文原样下发，明文凭据**不经过云端**，由 worker 本地解密 → 即便 VPS 整机沦陷，攻击者拿到的也只是无法解密的密文。
2. **JWT**：access 30 分钟 + refresh 7 天；refresh 存 localStorage，自动续期
3. **Worker 鉴权**：worker 调 `POST /api/worker/claim` 必须带 `X-Worker-Key: $WORKER_API_KEY` 头
4. **admin 鉴权**：用 `Depends(get_admin_user)` 限制 `/api/admin/*`

## Worker 多实例
- worker 可以裸跑，也可以用 Docker 跑多个容器实例。
- 多实例通过 `POST /api/worker/claim` 抢任务；后端用 `SELECT ... FOR UPDATE SKIP LOCKED` 原子认领，避免两个 worker 拿到同一个任务。
- 每个容器只需要出站 HTTPS 访问 VPS，不需要暴露端口。
- 多容器共用同一组 `API_BASE_URL`、`WORKER_API_KEY`、`SECRET_PRIVATE_KEY` 可以工作；为了互不干扰，建议给每个容器挂载独立的 `config.yml`、日志目录和 `data_directory`。
- VPS 后端仍建议 systemd 直跑。VPS 只有 1.9GB 内存，后端容器化收益不高；worker 在本地机器容器化更适合隔离多实例。

## 为什么用 9443 不用 443
- 443 端口大陆需要 ICP 备案
- 9443 是 443 的"镜像"，免备案，访问 URL 多个端口号而已
