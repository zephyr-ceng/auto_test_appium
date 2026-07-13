# auto_test_appium

粉笔行测学习报告页面。当前版本支持：

- 静态报告页面：`res_json/report.html`
- Vercel Python API：`/api/report`、`/api/health`、`/api/admin/cookie`
- ECharts 图表、练习历史筛选、错题知识点下拉树

## 本地预览

静态页面可直接用本地 HTTP 服务查看；如果没有 `/api/report`，页面会回退读取 `res_json/live_*.json`。

```powershell
cd res_json
py -m http.server 8765 --bind 127.0.0.1
```

打开：

```text
http://127.0.0.1:8765/report.html
```

## Vercel 部署

在 Vercel 项目环境变量中配置：

```text
FENBI_COOKIE=<完整粉笔 Cookie>
REPORT_CACHE_TTL_SECONDS=600
```

部署后访问：

- `/report.html`：报告页面
- `/admin.html`：Cookie 更新页面
- `/api/health`：服务健康检查
- `/api/report`：统一报告数据

注意：管理员页面写入的是 Serverless 运行时临时文件系统，实例重建后可能丢失；生产环境仍建议同步更新 `FENBI_COOKIE` 环境变量。
