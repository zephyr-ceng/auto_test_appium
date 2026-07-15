# 粉笔学习报告服务

这是一个标准 B/S 架构的本地学习报告服务。后端使用 FastAPI 负责接口、数据缓存、上游请求和安全校验；前端集中管理 HTML、CSS 和 JavaScript，通过同源 `/api/*` 接口获取报告数据。

## 项目结构

```text
.
├── backend/
│   ├── main.py                 # FastAPI 应用装配入口
│   ├── config.py               # 后端配置与路径配置
│   ├── api/
│   │   ├── routes/             # 页面路由与 API 路由
│   │   ├── security.py         # 请求来源校验
│   │   ├── rate_limit.py       # 手动刷新限流
│   │   └── schemas.py          # 请求模型
│   └── services/
│       ├── fenbi_client.py     # 粉笔接口、缓存、报告归一化
│       └── ai_analysis.py      # AI 分析 SSE 服务
├── frontend/
│   ├── pages/                  # HTML 页面
│   └── assets/
│       ├── css/                # 页面样式
│       └── js/                 # 页面脚本
├── data/                       # 本地运行数据与缓存
├── doc/                        # 原始参考文档
└── main.py                     # 兼容入口，导出 backend.main:app
```

## 本地启动

项目推荐使用 Python 3.12 和 `uv` 管理环境。

```powershell
uv python install 3.12
uv venv .venv --python 3.12
uv pip install --python .venv\Scripts\python.exe -r requirements.txt
```

可选：启动前设置粉笔 Cookie，也可以启动后在 `/admin.html` 页面配置。

```powershell
$env:FENBI_COOKIE = "<完整粉笔 Cookie>"
```

推荐使用后端包入口启动：

```powershell
uv run uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload
```

兼容旧入口仍然可用：

```powershell
uv run uvicorn main:app --host 127.0.0.1 --port 8000 --reload
```

打开页面或接口：

- `http://127.0.0.1:8000/report.html`
- `http://127.0.0.1:8000/admin.html`
- `http://127.0.0.1:8000/api/health`
- `http://127.0.0.1:8000/api/report`

如果使用其他端口，需要同步设置 `ALLOWED_ORIGINS`：

```powershell
$env:ALLOWED_ORIGINS = "http://127.0.0.1:8011,http://localhost:8011"
uv run uvicorn backend.main:app --host 127.0.0.1 --port 8011 --reload
```

## 前后端边界

- `frontend/pages` 只存放页面结构。
- `frontend/assets/css` 只存放样式。
- `frontend/assets/js` 只存放前端交互和接口调用。
- `backend/api/routes` 只处理 HTTP 路由。
- `backend/services` 集中处理业务逻辑、上游请求、缓存和数据归一化。
- 后端通过 `/static` 挂载 `frontend/assets`，页面通过 `/static/css/...` 和 `/static/js/...` 引用资源。

## Cookie

可以通过环境变量提供 Cookie：

```powershell
$env:FENBI_COOKIE = "<完整粉笔 Cookie>"
```

也可以在 `/admin.html` 页面提交。服务端会先调用粉笔接口验证 Cookie，通过后写入 `data/fenbi_cookie.txt`。不要提交运行时 Cookie 或缓存文件。

## 缓存与刷新

- `/api/report` 使用缓存优先策略，会立即返回最近一次可用报告。
- 运行时缓存默认有效期为 4 小时，可通过 `REPORT_CACHE_TTL_SECONDS` 调整。
- 服务启动后会在后台按缓存周期加随机延迟静默刷新。
- 手动刷新接口为 `POST /api/report/refresh`，默认每个客户端每小时最多 3 次。
- 如果上游请求失败，服务端会优先返回最后一次成功缓存，并标记 `meta.stale=true`。
- 如果没有 Cookie 或运行时缓存，服务端会回退读取 `data/live_*.json`。

## 安全控制

- CORS 默认只允许 `http://127.0.0.1:8000` 和 `http://localhost:8000`。
- 敏感 API 会校验 `Origin` 或 `Referer`。
- 上游粉笔接口请求串行执行，并在接口之间加入随机延迟。

## AI 分析

`/api/analysis/stream` 提供 SSE 分析接口。配置 `AI_API_KEY` 后会调用兼容 OpenAI `/chat/completions` 的流式 API；未配置时返回本地确定性摘要，便于测试。
