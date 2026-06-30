---
title: 部署流程 — mycloud（rsync 发布 + 迁移 + worker 协同）
date: 2026-06-30
tags:
  - icbc-platform
  - 部署
  - 运维
pr: 4
aliases:
  - 部署
  - 发布流程
  - mycloud
---

# 部署流程 — mycloud

整理自本轮三次实际发布（PR #4 #5 #6）。权威步骤见仓库 `docs/deploy.md`，这里记**要点与踩坑**。

> [!info] 环境速记
> SSH 别名 `mycloud`；云端 `/opt/icbc-platform`；后端 systemd 服务 `icbc-api`（127.0.0.1:8000）；前端静态目录 `/var/www/icbc-platform`；nginx HTTPS 9443；worker 跑在**本地 Docker**，不在云端。`/opt` 不是 git 工作区，用 rsync 发布。

## 纯前端发布

```bash
npm --prefix frontend run build
rsync -az --delete --rsync-path='sudo rsync' frontend/dist/ mycloud:/var/www/icbc-platform/
ssh mycloud 'sudo chown -R www-data:www-data /var/www/icbc-platform'
```

## 后端发布（标准）

1. 预检：服务 active、`alembic current`、`/health`、**有无 running/pending 任务**（重启 worker 前必查）。
2. 备份：后端代码 rsync + `sudo -u postgres pg_dump icbc_platform`（带迁移时务必 dump）。
3. 同步代码：先 rsync 到 `/tmp/icbc-platform-release`，再 `sudo rsync` 提升到 `/opt`（保护 `.env`/venv）。
4. 依赖/迁移：`requirements.txt` 变了才 `pip install`；有迁移才 `alembic upgrade head`。
5. `sudo systemctl restart icbc-api` + 轮询 `/health`。

## 含迁移的发布

PR #5 带了 `0005`（部分唯一索引）。要点：

- **建唯一索引前确认无违反约束的数据**：先查"是否存在重复活跃任务的用户"，为空才安全（`CREATE INDEX` 失败会中断迁移）。
- 索引是 `CREATE INDEX`（非 CONCURRENTLY），会短暂持表锁；表小（个位数行）可忽略。
- 验证：`alembic current` = 新 head，且 `\d booking` 能看到索引。

## worker 协同发布（重要）

PR #4/#5 改了 worker，且 `attempt` 为**必填**字段 → 后端与 worker **必须一起发**：

> [!warning] 顺序
> 1. 确认**无 running 任务**（worker 状态在进程内，硬重启会留下无人收尾的任务）。
> 2. `docker compose -f docker-compose.worker.yml down`（先停，消除"旧 worker 打新后端缺 attempt → 422"的窗口）。
> 3. 发后端（+迁移+重启）。
> 4. `docker compose ... up -d --build` 用新代码重建 worker。
> 5. `docker compose ... logs` 看 `/claim` 是否 200。

## 发布后验证

```bash
ssh mycloud 'systemctl is-active icbc-api nginx postgresql'
curl -fsS https://gogoxoxo.duckdns.org:9443/health
curl -fsSI https://gogoxoxo.duckdns.org:9443/booking/ | head -1
```

## 踩坑

> [!bug] rsync 误传 worker/.venv（PR #6 修）
> 排除清单原本没有 `worker/.venv`（约 50M）。worker 在 Docker 里跑、服务器根本不需要它，但 rsync 把它一起传 → 同步**卡住**。已在 `docs/deploy.md` 三处排除清单补 `--exclude='worker/.venv/'`。
> 教训：rsync 发布前 `du -sh` 看一眼最大的目录；本地 venv / 缓存务必排除。

> [!tip] nginx 配置激活
> 改了 `deploy/nginx-icbc.conf` 后：`scp` 到 `/tmp` → `sudo install` 到 sites-available → `sudo nginx -t` → `sudo systemctl reload nginx`。务必先 `nginx -t`。

## 关联

- 前端缓存配置见 [[nginx-SPA-缓存策略]]。
- worker 协同的原因见 [[worker-fencing-token]]。
- 迁移内容见 [[并发竞态-booking状态机#每用户单活跃任务]]。
