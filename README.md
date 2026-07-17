# 报告服务

这是一个本地学习报告服务。后端使用 FastAPI 提供页面路由、报告接口、粉笔上游请求、缓存、安全校验和 AI 分析；前端使用同源的 HTML、CSS 和 JavaScript，通过 `/api/*` 接口读取数据并展示报告。

项目当前以本地运行为主，同时采用接近 Vercel 的环境变量配置方式：敏感信息放在本机 `.env.local` 或部署平台环境变量中，不提交到仓库。

## 项目结构

```text
.
├── backend/
│   ├── main.py                 # FastAPI 应用装配入口
│   ├── config.py               # 路径、缓存、Cookie、AI 服务商配置
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
├── data/                       # 本地兜底数据与运行缓存
├── main.py                     # 兼容入口，导出 backend.main:app
├── requirements.txt            # pip 依赖
└── pyproject.toml              # uv / Python 项目配置
```

## 本地环境

推荐使用 Python 3.12 和项目内 `.venv`。

```powershell
uv python install 3.12
uv venv .venv --python 3.12
uv pip install --python .venv\Scripts\python.exe -r requirements.txt
```

如果不用 `uv`，也可以直接使用已有虚拟环境：

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

## 环境变量

推荐在项目根目录创建 `.env.local` 存放本机配置。该文件只用于本地，不应提交。

```dotenv
# AI 中转站，默认 provider 为 relay
AI_DEFAULT_PROVIDER=relay
AI_RELAY_BASE_URL=https://relay.nf.video/v1
AI_RELAY_MODEL=gpt-5.5
AI_RELAY_WIRE_API=responses
AI_RELAY_REASONING_EFFORT=high
AI_RELAY_DISABLE_RESPONSE_STORAGE=true
AI_RELAY_API_KEY=<your-key>

# 可选：粉笔 Cookie。也可以启动后在 /admin.html 配置。
FENBI_COOKIE=<your-cookie>

# 本地默认端口为 8000；如果改端口，需要同步调整来源白名单。
ALLOWED_ORIGINS=http://127.0.0.1:8000,http://localhost:8000
```

PowerShell 手动加载 `.env.local`：

```powershell
Get-Content .env.local | ForEach-Object {
  if ($_ -match '^\s*#' -or $_ -notmatch '=') { return }
  $name, $value = $_ -split '=', 2
  [Environment]::SetEnvironmentVariable($name.Trim(), $value.Trim(), 'Process')
}
```

也可以直接在当前 PowerShell 会话里设置单个变量：

```powershell
$env:AI_RELAY_API_KEY = "<your-key>"
$env:FENBI_COOKIE = "<your-cookie>"
```

## 启动

推荐使用后端包入口启动：

```powershell
.\.venv\Scripts\uvicorn.exe backend.main:app --host 127.0.0.1 --port 8000 --reload
```

兼容旧入口仍可使用：

```powershell
.\.venv\Scripts\uvicorn.exe main:app --host 127.0.0.1 --port 8000 --reload
```

常用页面和接口：

- `http://127.0.0.1:8000/report.html`
- `http://127.0.0.1:8000/admin.html`
- `http://127.0.0.1:8000/api/health`
- `http://127.0.0.1:8000/api/report`
- `http://127.0.0.1:8000/api/analysis/providers`

如果使用其他端口，需要同步设置 `ALLOWED_ORIGINS`：

```powershell
$env:ALLOWED_ORIGINS = "http://127.0.0.1:8011,http://localhost:8011"
.\.venv\Scripts\uvicorn.exe backend.main:app --host 127.0.0.1 --port 8011 --reload
```

## Cookie 与运行数据

粉笔 Cookie 有两种配置方式：

- 本地或部署环境变量：`FENBI_COOKIE=<your-cookie>`。
- 本地页面提交：打开 `/admin.html`，服务端验证后写入 `data/fenbi_cookie.txt`。

运行时会生成或更新这些本地文件，均不应提交：

- `.env.local`
- `data/fenbi_cookie.txt`
- `data/report_cache.json`
- `data/rate_limit.json`
- `data/status.json`

`data/live_*.json` 是可提交的本地兜底数据 fixture。当没有 Cookie、没有运行缓存或上游请求失败时，服务可以回退读取这些文件，方便本地调试和离线查看页面。

## 缓存与刷新

- `/api/report` 使用缓存优先策略，会立即返回最近一次可用报告。
- 运行时缓存默认有效期为 4 小时，可通过 `REPORT_CACHE_TTL_SECONDS` 调整。
- 服务启动后会在后台按缓存周期加随机延迟静默刷新。
- 手动刷新接口为 `POST /api/report/refresh`，默认每个客户端每小时最多 3 次。
- 如果上游请求失败，服务端优先返回最后一次成功缓存，并标记 `meta.stale=true`。
- 如果没有 Cookie 或运行时缓存，服务端回退读取 `data/live_*.json`。

## AI 分析

`/api/analysis/stream` 提供 SSE 分析接口。默认 AI provider 是 `relay`，使用中转站的 OpenAI Responses API：

- 请求地址默认是 `https://relay.nf.video/v1/responses`。
- 默认模型是 `gpt-5.5`。
- 默认 `reasoning.effort=high`。
- 默认 `store=false`，避免保存响应。
- SSE 返回 `text/event-stream; charset=utf-8`，用于避免中文流式响应乱码。

配置 `AI_RELAY_API_KEY` 后，报告页的 AI 分析会调用 `relay` 并流式返回结果。未配置 Key 时，服务会返回本地确定性摘要，便于测试页面。

其他 provider 仍可使用 OpenAI 兼容的 `/chat/completions` 流式接口：

- `OPENAI_API_KEY` / `OPENAI_BASE_URL` / `OPENAI_MODEL`
- `DEEPSEEK_API_KEY` / `DEEPSEEK_BASE_URL` / `DEEPSEEK_MODEL`
- `DASHSCOPE_API_KEY` / `QWEN_BASE_URL` / `QWEN_MODEL`

前端会从 `/api/analysis/providers` 读取可用服务商，并在 `/admin.html` 保存当前浏览器选择。API Key 始终由后端环境变量提供。

## 安全与隔离

- CORS 默认只允许 `http://127.0.0.1:8000` 和 `http://localhost:8000`。
- 敏感 API 会校验 `Origin` 或 `Referer`。
- 上游粉笔接口请求串行执行，并在接口之间加入随机延迟。
- 不要提交 `.env.local`、Cookie、AI Key、粉笔账号数据或运行缓存。
- 如果需要提供示例配置，使用 `.env.example` 并只写占位值。

## Vercel 风格说明

当前项目主要是本地运行和本地模拟 Vercel 风格环境变量，并不等同于已经完成 Vercel 部署。

如果未来真正部署到 Vercel，需要注意：

- Serverless 文件系统不能用于持久保存 Cookie、缓存、状态或限流数据。
- 生产环境建议只通过环境变量提供 `FENBI_COOKIE`、`AI_RELAY_API_KEY` 等敏感配置。
- `/admin.html` 写入 Cookie 文件的方式只适合本地持久化；部署环境需要改成外部存储或只读环境变量策略。
- 需要补充 Vercel 入口、路由配置和持久化方案后，再声明可直接部署。

## 验证

后端语法检查：

```powershell
.\.venv\Scripts\python.exe -m compileall backend
```

检查 AI provider 配置：

```powershell
Invoke-RestMethod http://127.0.0.1:8000/api/analysis/providers
```

检查服务健康状态：

```powershell
Invoke-RestMethod http://127.0.0.1:8000/api/health
```

提交前确认没有 secret 或运行数据进入暂存区：

```powershell
git status --short
git diff -- README.md
```
