# 已知问题与后续工作

本文档记录项目当前的状态、被忽略的事项、以及未来需要做的工作。

## 已修复（smoke test 阶段发现）

| ID | 严重 | 描述 | 状态 |
|---|---|---|---|
| F1 | 高 | `app/core/crypto.py` 在 import 期强校验 `ENCRYPTION_KEY`，占位符直接让整个 app 起不来。改为 lazy + 友好错误。 | ✅ 已修 |
| F2 | 高 | `requirements.txt` 没钉 `bcrypt`，pip 解出 5.x 与 `passlib==1.7.4` 不兼容。钉 `bcrypt<4.1`。 | ✅ 已修 |
| F3 | 中 | 迁移用 `postgresql.ARRAY` / `postgresql.JSONB`，本地无 postgres 跑不动。改为 `sa.JSON()` 跨 DB。 | ✅ 已修 |
| C1 | 低 | `_bootstrap_admin` 邮箱没 `.lower()`，与 `get_by_email` 行为不一致。 | ✅ 已修 |
| C2 | 低 | 多处未使用 import（`select`/`update`/`UserPublic`/`BookingStatus` 等）。 | ✅ 已修 |
| C3 | 低 | （分析误报：`ast.walk` 把函数内 lazy import 当 top-level 算了，实际无重复） | ➖ 无需改 |
| C4 | 低 | `_bootstrap_admin` 没处理并发场景的 IntegrityError。 | ✅ 已修 |
| D1 | 低 | `deploy/env.example` 里 `JWT_SECRET=$(python3 -c ...)` 是命令替换示例，但放进真 .env 会被 shell 求值。改为占位字符串。 | ✅ 已修 |
| D2 | 低 | `docs/deploy.md` 里的 GitHub 用户名是 `你的用户名` 占位符。 | ✅ 已修（替换为 gaoxiaowei2117） |

## 已修复（凭据链路 + 安全加固，2026-06-09）

| ID | 严重 | 描述 | 状态 |
|---|---|---|---|
| F4 | 高 | `crud/secret.py` 先 `.encode()` 成 bytes 再传给 `encrypt_secret(plaintext: str)`，后者又 `.encode()` → `AttributeError`，**保存 ICBC 凭据必 500**（连带堵死建任务主链路）。改为传 str。 | ✅ 已修 |
| F5 | 高 | `api/worker.py` 用了 `BookingStatus` 但漏 import；claim 无待办任务时侥幸不触发，但 worker 回报结果路径必 `NameError` 500（抢约成功也写不回库）。补 import。 | ✅ 已修 |
| S1 | 高 | **A1 安全承诺与实现相反**：原用对称 Fernet，密钥（`ENCRYPTION_KEY`）在云端 `.env`，云端能解密、claim 响应里下发明文 → VPS 沦陷即凭据全失。改为非对称 **SealedBox**：云端只持公钥（只加密），私钥仅在本地 worker，密文下发、worker 端解密。A1 现已名副其实。 | ✅ 已修 |

## 待办（暂不修，scope 外）

| ID | 描述 | 建议 |
|---|---|---|
| T1 | `worker/booking_engine.py` 是 stub，真正的抢约逻辑（来自原 `road.py`）还没接进来 | 单独一个 PR 接真实逻辑；接口已稳定 |
| T2 | 没有"任务卡死"清理机制：worker 崩溃后任务会一直停在 `running` | 短期可加后台 reaper（`started_at` 超过 N 分钟 → 重置为 `pending`）；或 worker 启动时检查并重新认领 |
| T3 | 无单元测试 / 集成测试（F4/F5 正是缺测试漏掉的） | 加 `pytest` 套件覆盖：JWT 签发、SealedBox 加密 + worker 解密往返、auth flow、claim 原子性 + 返回密文、worker 回报、admin 鉴权 |
| T4 | 凭据密钥对无轮换机制：换 `SECRET_PUBLIC/PRIVATE_KEY` 后所有存量 `secret.ciphertext` 失效 | 短期：文档化警告 + 让用户重提交凭据；长期：多密钥过渡（`key_id` + 按 id 选 SealedBox） |
| T5 | `bookings.time_window` 和 `user.time_windows` 的 schema 重复：都是 `{morning, afternoon, evening}` 但分两个字段 | 考虑归一或重新设计；现在能工作，先不动 |
| T6 | 前端无 404 fallback，未知 URL 显示空 RouterView | 加一个 catch-all 路由展示 "页面不存在" |
| T7 | 无 CI（lint / typecheck / test / build） | 加 GitHub Actions；至少跑 `vue-tsc` + `ruff check backend` + `pytest`（如果 T3 做了） |
| T8 | 无日志聚合：backend 写到 stdout（systemd 重定向到 `/var/log/icbc-api.log`），worker 写到 `worker.log` | 上规模后接 Loki/CloudWatch；当前体量不需要 |
| T9 | `vue-tsc` 在 `npm run build` 里跑，但 `npm run dev` 不做类型检查 | IDE 编译时检查就够；不强求 |
| T10 | 无速率限制：`/api/auth/login` 会被暴力枚举 | 加 `slowapi` 或 nginx `limit_req` |

## 设计决策（写下来免得以后被"修正"）

| ID | 决策 | 理由 |
|---|---|---|
| A1 | 凭据 **SealedBox 非对称**加密存 DB，云端只持公钥、私钥只在本地 worker | 假设 VPS 被攻破，攻击者拿不到 ICBC 凭据明文（见 S1：原对称实现已废弃） |
| A2 | Worker 主动 poll `POST /api/worker/claim`，不放 push | VPS 1.9G 内存跑不了长连接/WebSocket 组件；轮询 5s 可接受 |
| A3 | 用 `select ... for update skip locked` 实现原子认领 | postgres 9.5+ 原生支持；不用外部队列 |
| A4 | 不上 Docker（backend 直 systemd） | 1.9G VPS 上 Docker daemon 占 200-400M；无跨机迁移需求 |
| A5 | 用 9443 不用 443 | 大陆 443 要 ICP 备案；9443 是 443 镜像端口，免备案 |

## Smoke test 结论（2026-06-03）

- ✅ `pip install` 干净
- ✅ `alembic upgrade head` 在 postgres 16 上通过
- ✅ uvicorn 启动 OK，bootstrap admin 建好
- ✅ `/health`、`/docs`、`/openapi.json` 全部 200
- ⚠️ 路由 `POST /api/auth/login` 拒绝保留 TLD（如 `admin@local.test`）—— `email-validator` 严格性正确，生产域名不受影响
