# 当前待办与运行手册

> 最近更新：2026-06-29  
> 目标：把当前开发上下文、启动部署流程、验证命令和 Git 同步流程集中到一处，便于交接和继续开发。

## 当前状态

- 主分支：`main`
- 本地运行方式：FastAPI 后端 + Vite 前端 + DuckDB 本地文件
- 后端端口：`127.0.0.1:8000`
- 前端端口：`127.0.0.1:5173`
- 前端代理：`/api` -> `http://localhost:8000`
- 默认 DuckDB：`data/duckdb/analytics.duckdb`
- 当前可用页面：市场总览、行业、股票、告警
- 当前可用同步能力：API 触发后台市场同步、取消、持久化任务、历史列表、任务详情、重试入口
- 当前可用告警能力：系统告警、涨停、跌停、放量、异常涨跌幅、同股票告警分组、等级/类型筛选、点击定位股票

## 当前待办

优先级从高到低：

1. 告警生命周期：新增 read / handled / ignored 状态，支持前端标记处理。
2. 告警持久化：将当前派生告警落表，保留历史、处理状态、首次/最近触发时间。
3. 告警冷却窗口：按 `surveillance_rules.yaml` 的 `dedupe.window_minutes` 和规则 `cooldown_minutes` 去重。
4. 行业热力图：基于 `industry_snapshots` 做行业涨跌、成交额、告警密度视图。
5. 个股详情页：从告警或股票列表进入，展示当日快照、历史告警、行业归属和基础指标。
6. 同步任务历史增强：后端分页、最近 N 次失败统计、运行日志或 artifact 链接。
7. 数据正确性：处理停牌、新股首快照、除权除息、交易日历对 freshness 的影响。
8. 生产化部署：增加 Docker / launchd / systemd 或等价进程守护方案。

## 首次环境准备

后端：

```bash
cd backend
python3.12 -m venv .venv
.venv/bin/python -m pip install -e ".[dev,providers]"
```

前端：

```bash
cd frontend
npm install
```

运行配置，在仓库根目录：

```bash
cp .env.example .env
```

`.env` 常用项：

```bash
DAB_CONFIG_DIR=./config
DAB_DUCKDB_PATH=./data/duckdb/analytics.duckdb
DAB_TUSHARE_TOKEN=
DAB_DEEPSEEK_API_KEY=
```

说明：

- AKShare 不需要 token，是当前全市场快照主 provider。
- Tushare / DeepSeek token 为空时对应能力降级，不应阻塞基础市场页。
- `data/` 被 `.gitignore` 忽略，不提交本地 DuckDB 数据。

## 本地启动流程

推荐开两个终端。

终端 A，在仓库根目录启动后端：

```bash
DYLD_LIBRARY_PATH=/opt/homebrew/opt/expat/lib backend/.venv/bin/uvicorn dataanalysisbase.api.main:app --host 127.0.0.1 --port 8000
```

如果本机不需要 `DYLD_LIBRARY_PATH`，且当前 shell 已能找到后端依赖，可使用 Makefile：

```bash
make dev-api
```

终端 B，启动前端：

```bash
make dev-web
```

访问：

```text
http://127.0.0.1:5173/
```

快速检查：

```bash
curl -sS http://127.0.0.1:8000/api/v1/system/status
curl -sS 'http://127.0.0.1:8000/api/v1/alerts/market/groups?limit=10'
curl -sS 'http://127.0.0.1:5173/api/v1/alerts/market/groups?limit=10'
```

## 手动同步数据

预览全市场同步：

```bash
cd backend
.venv/bin/python -m dataanalysisbase.delivery.cli plan sync-market --json
```

执行全市场同步：

```bash
cd backend
.venv/bin/python -m dataanalysisbase.delivery.cli sync market --execute --json
```

也可以从页面点击顶部“同步”按钮触发后台任务。页面触发的任务会持久化到 `api_sync_jobs`，服务重启后可恢复最新任务状态；重启前仍在 `running` 的任务会标记为失败并提示被 API 重启中断。

## 质量验证

后端全量验证：

```bash
cd backend
.venv/bin/python -m pytest
.venv/bin/ruff check .
.venv/bin/mypy src
```

前端验证：

```bash
cd frontend
npm run build
```

常用一次性验证清单：

```bash
cd backend && .venv/bin/python -m pytest && .venv/bin/ruff check . && .venv/bin/mypy src
cd ../frontend && npm run build
```

## 部署说明

当前仓库尚未提供生产化 Docker / systemd / launchd 配置。现阶段部署方式是“本地长期运行”：

1. 在目标机器完成首次环境准备。
2. 准备 `.env` 和 `config/`。
3. 后端以前台或进程守护方式从仓库根目录运行 `backend/.venv/bin/uvicorn dataanalysisbase.api.main:app --host 127.0.0.1 --port 8000`。
4. 前端开发环境运行 `npm run dev`；若需要静态产物，运行 `npm run build` 后使用静态服务器托管 `frontend/dist/`。
5. 前端静态部署时要保证 `/api` 转发到后端 `8000`。

上线前必须执行质量验证，并确认：

- `data/duckdb/analytics.duckdb` 路径可写。
- 后端能读取 `config/`。
- 前端能访问 `/api/v1/system/status`。
- 告警接口 `/api/v1/alerts/market/groups` 返回 200。

## Git 同步与推送流程

同步远端：

```bash
git status --short --branch
git pull
```

提交前检查：

```bash
git diff --stat
git diff --cached --stat
```

只暂存相关文件，避免提交本地私有文件：

```bash
git add <files>
git commit -m "docs: add operations runbook"
```

推送：

```bash
git push origin main
```

如果普通 SSH 不通，可使用 GitHub SSH 443：

```bash
GIT_SSH_COMMAND='ssh -p 443 -o StrictHostKeyChecking=accept-new -o UserKnownHostsFile=/tmp/codex_github_known_hosts' \
  git push ssh://git@ssh.github.com/1191835397/DataAnalysisBase.git main
```

推送后确认：

```bash
git fetch origin main
git status --short --branch
git rev-parse --short HEAD
git rev-parse --short origin/main
```

## 不要提交的内容

- `.env`
- `data/`
- `*.duckdb`
- `frontend/dist/`
- `frontend/tsconfig.tsbuildinfo`
- 本地知识库或私人笔记，例如当前工作区里的 `.obsidian/`

## 当前关键接口

```text
GET  /api/v1/system/status
POST /api/v1/sync/market
GET  /api/v1/sync/market/latest
GET  /api/v1/sync/market/jobs
GET  /api/v1/sync/market/{job_id}
POST /api/v1/sync/market/{job_id}/cancel
GET  /api/v1/alerts/market
GET  /api/v1/alerts/market/groups
GET  /api/v1/market/overview
GET  /api/v1/stocks
GET  /api/v1/industries
GET  /api/v1/industries/{industry_code}/stocks
```
