# ICBC Road Test Platform

多用户 ICBC 路考自动预约平台。

## 架构
- **VPS（广州腾讯云）**：FastAPI + PostgreSQL + Nginx（9443），负责注册/登录、任务管理
- **本地电脑（温哥华）**：Python worker 轮询 VPS 拿任务，跑实际抢约逻辑
- 通信：worker → VPS 出站 HTTPS，本地无需公网 IP

## 端口与 URL
- 前端：`https://gogoxoxo.duckdns.org:9443/booking/`
- API：`https://gogoxoxo.duckdns.org:9443/api/`
- worker 心跳：5s 轮询 `/api/worker/claim`

## 目录
- `backend/`  FastAPI 后端
- `frontend/` Vue 3 前端
- `worker/`   本地抢约 worker
- `deploy/`   VPS 一键部署脚本
- `docs/`     架构 / API / 部署文档

## 快速开始
详见 [docs/deploy.md](docs/deploy.md) 和 [docs/architecture.md](docs/architecture.md)
