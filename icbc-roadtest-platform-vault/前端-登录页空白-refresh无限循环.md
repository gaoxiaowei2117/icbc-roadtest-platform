---
title: 前端登录页空白 — refresh token 无限刷新循环
date: 2026-06-30
tags:
  - icbc-platform
  - bug-fix
  - 前端
  - 认证
pr: 3
severity: 高
aliases:
  - 页面空白
  - refresh 死循环
---

# 前端登录页空白 — refresh token 无限刷新循环

> [!bug] 现象
> 手机端（及任何**带过期 token 的老设备**）打开站点，只显示语言选择 + 页脚，主体内容空白。全新访客正常。

## 根因

`frontend/src/stores/auth.ts` 的 axios 响应拦截器在收到 401 时会尝试刷新 token，但**没有排除 auth 端点本身**。当 refresh token 也过期时：

1. `POST /api/auth/refresh` 自己返回 401
2. 拦截器又对这个 refresh 请求触发刷新
3. 每次 `axios.post()` 都是全新 config，`_retry` 标记永远为空 → **无限递归刷新**（控制台 401 持续增长，复现时见到 37→82 次仍在涨）
4. `logout()`（在 catch 里）永远跑不到 → localStorage 里的失效 token 清不掉
5. `fetchMe()` 永远 pending → 路由守卫 `await auth.fetchMe()` 挂起 → 永不跳转登录页
6. 停在内部 `/` 路由（只有 redirect、没有组件）→ `<RouterView>` 渲染空 → 只剩 App.vue 外壳 + 页脚

```js
// 出问题的拦截器（简化）
if (err.response?.status === 401 && refreshToken.value && !err.config._retry) {
  err.config._retry = true
  await axios.post('/api/auth/refresh', ...)   // ← 这个请求自己 401 时又会进拦截器
}
```

## 修复

刷新拦截器**跳过 `/api/auth/` 端点自身**：

```js
const url = err.config?.url || ''
const isAuthEndpoint = url.includes('/api/auth/')
if (err.response?.status === 401 && refreshToken.value && !err.config._retry && !isAuthEndpoint) {
  ...
}
```

这样 refresh 401 时直接 reject → 外层 catch 跑 `logout()` 清 token → `fetchMe()` reject → 路由守卫捕获 → 正常跳转登录页。

## 验证

- 浏览器 390×844 注入过期 token 复现了空白效果；修复后正常跳到 `/booking/login`，过期 token 被清除。
- 全新访客（无 token）始终正常 —— 这解释了为什么只有"老用户/开发者自己的手机"中招。

> [!warning] 排查关键
> 现象是"页面空白"，但**外壳和页脚是渲染出来的**，说明 Vue 已挂载、只有 `<RouterView>` 空 —— 这把问题从"构建/资源加载失败"缩小到"路由没匹配 / 守卫挂起"。控制台里 401 **次数持续增长**是死循环的决定性证据。

## 关联

- 同 PR 顺带修了 [[nginx-SPA-缓存策略]]（否则修复传不到老用户）。
- 排查与部署细节见 [[部署流程-mycloud]]。
