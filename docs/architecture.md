# 架构

## 组件
- **VPS（广州腾讯云）**：FastAPI + PostgreSQL + Nginx，承载前端 / API / 数据库
- **本地电脑（温哥华）**：Python worker，跑实际抢约
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
                  worker.py (本地)
                       │
                       ▼
                  booking_engine.run(task)
                       │
                       ▼
                  Playwright → ICBC 网站   ← 设计意图，未实现
```

> ⚠️ `booking_engine.run()` 目前仍是 stub（见 known-issues T1），尚未接入真实抢约逻辑。
> 图中 "Playwright" 只是最初的设计假设；实际采用的自动化方式（浏览器自动化 or HTTP API 直连）
> 待接入时确定，当前工程未依赖 Playwright（`worker/requirements.txt` 中已注释）。

## 数据模型

### user
| 字段 | 类型 | 说明 |
|---|---|---|
| id | int | 主键 |
| email | varchar(255) | 唯一 |
| password_hash | varchar(255) | bcrypt |
| is_active | bool | |
| is_admin | bool | 管理员标志 |
| icbc_license_no | varchar(50) | 驾照号 |
| icbc_last_name | varchar(100) | 姓氏 |
| preferred_pos | text[] | 首选考点代码数组 |
| time_windows | jsonb | {morning, afternoon, evening} |
| max_wait_days | int | 可接受等待天数 |

### secret
| 字段 | 类型 | 说明 |
|---|---|---|
| id | int | 主键 |
| user_id | int | 唯一外键 → user |
| ciphertext | bytea | SealedBox(X25519+XSalsa20-Poly1305) 加密的 "username\npassword"；只有 worker 私钥可解 |

### booking
| 字段 | 类型 | 说明 |
|---|---|---|
| id | int | 主键 |
| user_id | int | 外键 → user |
| status | enum | pending/running/done/failed/cancelled |
| target_date | date | 期望日期，可空 |
| time_window | jsonb | {morning, afternoon, evening} |
| pos_code | varchar(50) | 指定考点，可空 |
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

## 为什么不用 Docker
- VPS 只有 1.9GB 内存，Docker daemon + 容器化 runtime 至少占 200-400MB
- 单服务直接 systemd 跑更省内存
- 没有跨机器迁移需求

## 为什么用 9443 不用 443
- 443 端口大陆需要 ICP 备案
- 9443 是 443 的"镜像"，免备案，访问 URL 多个端口号而已
