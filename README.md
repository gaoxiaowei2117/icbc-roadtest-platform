# ICBC Road Test Platform

多用户 ICBC 路考自动预约平台。

## 架构
- **VPS（广州腾讯云）**：FastAPI + PostgreSQL + Nginx（9443），负责注册/登录、任务管理
- **本地电脑（温哥华）**：Python worker 轮询 VPS 拿任务，跑实际抢约逻辑；推荐用 Docker 跑一个或多个 worker 实例
- 通信：worker → VPS 出站 HTTPS，本地无需公网 IP

## 端口与 URL
- 前端：`https://gogoxoxo.duckdns.org:9443/booking/`
- API：`https://gogoxoxo.duckdns.org:9443/api/`
- worker 心跳：5s 轮询 `/api/worker/claim`
- worker 容器：不需要暴露端口，只需要能出站访问 API

## 任务运行机制
- 用户在页面创建任务后，任务先进入 `pending`，被 worker 领取后变为 `running`。
- 没有合适考位时，worker 随机等待 12-20 秒再查询；页面上的“查询轮次”会持续增加。
- 每个 worker 执行周期最长 600 秒。周期结束仍无考位时，任务回到 `pending` 并由 worker 再次领取，持续运行直到成功、用户取消或出现不可重试错误。
- `attempt_count` 是任务被 worker 领取的次数，不是查询考位的轮次；实际查询次数看 `progress_rounds`。
- 后端只会在任务连续 15 分钟没有进度心跳时认为 worker 已失联，并自动重排任务。

## 目录
- `backend/`  FastAPI 后端
- `frontend/` Vue 3 前端
- `worker/`   本地抢约 worker
- `deploy/`   VPS 一键部署脚本
- `docs/`     架构 / API / 部署文档

## 快速开始
- 用户注册、配置和任务状态说明：[用户使用指南](docs/user-guide.md)
- 首次部署、日常更新和排障：[部署与运维指南](docs/deploy.md)
- 系统组件和数据流：[架构说明](docs/architecture.md)
- 接口定义：[API 文档](docs/api.md)
