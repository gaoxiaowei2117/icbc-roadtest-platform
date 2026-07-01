---
title: nginx SPA 缓存策略 — index.html 不缓存 + hash 资源长缓存
date: 2026-06-30
tags:
  - icbc-platform
  - bug-fix
  - 部署
  - nginx
pr: 3
severity: 中
aliases:
  - SPA 缓存
  - Cache-Control
---

# nginx SPA 缓存策略

> [!bug] 隐患
> `index.html` 没有任何 `Cache-Control` 头，浏览器靠**启发式缓存**。发布用 `rsync --delete` 删除了旧 hash bundle，缓存了旧 `index.html` 的老用户会去加载**已不存在的旧 JS** → 404 / 页面空白；或继续跑缓存的旧代码。等于修复传不到老用户（比如自己的手机）。

## 原则

- **`index.html` 永不缓存**（每次校验）→ 发版后老用户立即拿到新引用的 hash 资源。
- **带 hash 的静态资源长期缓存**（`immutable`）→ 文件名变化即失效，安全地缓存一年。

## 配置

`deploy/nginx-icbc.conf` 的 `location /booking/` 内：

```nginx
location /booking/ {
    alias /var/www/icbc-platform/;
    try_files $uri $uri/ /booking/index.html;

    # 带 hash 的静态资源可长期缓存（文件名变化即失效）
    location /booking/assets/ {
        alias /var/www/icbc-platform/assets/;
        add_header Cache-Control "public, max-age=31536000, immutable";
    }

    # index.html 永不缓存，保证发版后老用户立即拿到新引用的 hash 资源
    location = /booking/index.html {
        alias /var/www/icbc-platform/index.html;
        add_header Cache-Control "no-cache";
    }
}
```

## 验证（线上 curl）

```
index.html → cache-control: no-cache
assets/index-*.js → cache-control: public, max-age=31536000, immutable
```

> [!note] 过渡期提醒
> `no-cache` 只对**将来**生效。这次切换之前已缓存旧 `index.html` 的浏览器，可能仍需一次硬刷新/清站点数据；之后就由 revalidation 自动接管。

## 关联

- 与 [[前端-登录页空白-refresh无限循环]] 同属 PR #3。修了代码却被缓存挡住的话，根因照样复现。
- 部署激活步骤（`nginx -t` + `reload`）见 [[部署流程-mycloud]]。
