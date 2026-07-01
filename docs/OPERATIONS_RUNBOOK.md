# 当前待办与运行手册

> 最近更新：2026-07-01  
> 目标：把当前开发上下文、启动部署流程、验证命令和 Git 同步流程集中到一处，便于交接和继续开发。

## 当前状态

- 主分支：`main`
- 本地运行方式：FastAPI 后端 + Vite 前端 + DuckDB 本地文件
- 后端端口：`127.0.0.1:8000`
- 前端端口：`127.0.0.1:5173`
- 前端代理：`/api` -> `http://localhost:8000`
- 默认 DuckDB：`data/duckdb/analytics.duckdb`
- 当前可用页面：市场总览、行业排行、行业覆盖概览、行业热力图、行业成分股、股票、个股详情面板、告警
- 当前可用同步能力：API 触发后台市场同步、取消、持久化任务、历史分页、最近失败统计、任务详情、结构化运行日志、运行 artifact、重试入口、本地行业映射文件回填最新快照
- 当前可用告警能力：系统告警、涨停、跌停、放量、异常涨跌幅、告警持久化、read / handled / ignored 生命周期、按 `dedupe.window_minutes` / `cooldown_minutes` 冷却去重、同股票告警分组、等级/类型/状态筛选、点击定位个股详情

## 当前待办

优先级从高到低：

1. 完整行业映射数据源：行业映射同步已按优先级自动合并 Tushare（有 token 时）/ AKShare / efinance / BaoStock，AKShare 会补充北交所股票列表行业，BaoStock 可补主板/深市映射；近期真实同步覆盖率已约 99.96%，仍需处理极少数 `UNKNOWN` / 退市标的补齐策略。
2. 数据正确性：交易日历 freshness 已按 `sync_schedule.yaml` 交易时段口径处理，并支持 `holidays` / `makeup_trading_days` 手动维护真实节假日与调休交易日，2026 年交易日历已通过 AKShare 新浪交易日历同步到 2026-07-01；delta 类价格告警已在首快照 / 无上一价格时跳过，股票级告警已按 `is_suspended` 显式停牌字段和无有效价格或零成交量/零成交额标的做停牌式保守过滤，ST / 科创板 / 创业板 / 北交所涨跌停阈值已按代码和名称分档，AKShare 市场同步会从沪/深/北交易所批量股票列表补齐 `listing_date`，快照存在 `listing_date` 时上市初期 5 个自然日内跳过涨跌停判定，AKShare 市场同步会按快照日期读取分红派息提醒并合并报告期历史分红送配记录，命中当日除权除息日时标记 `ex_dividend=true`，快照存在 `ex_dividend=true` 时跳过 delta 类价格告警；下一步优先接入独立停牌公告/清单数据源，交易日历和历史除权除息仍需按真实样本持续核验。
3. 生产化部署：增加 Docker / launchd / systemd 或等价进程守护方案。

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
- `config/sync_schedule.yaml` 的 `holidays` / `makeup_trading_days` 用 `YYYY-MM-DD` 维护，用于运行状态 freshness 判断真实休市日和调休交易日。
- `sync trade-calendar` 默认 dry-run；传 `--execute` 后会调用 AKShare 新浪交易日历并写回 `config/sync_schedule.yaml`。

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

行业映射：

```bash
cd backend
.venv/bin/python -m dataanalysisbase.delivery.cli sync industry-mapping --execute --json
```

交易日历：

```bash
cd backend
.venv/bin/python -m dataanalysisbase.delivery.cli sync trade-calendar --json
.venv/bin/python -m dataanalysisbase.delivery.cli sync trade-calendar --year 2026 --execute --json
```

备用 provider 可显式指定：

```bash
cd backend
.venv/bin/python -m dataanalysisbase.delivery.cli sync industry-mapping --provider tushare --execute --json
.venv/bin/python -m dataanalysisbase.delivery.cli sync industry-mapping --provider baostock --execute --json
```

说明：

- 默认不指定 `--provider` 时，会按配置优先级自动合并可用候选：Tushare（已配置 token 时）/ AKShare / efinance / BaoStock；前序来源优先，后序来源只补缺。指定 `--provider` 时只使用该单一来源刷新映射文件。
- 当前 AKShare 行业映射真实同步可能返回 0 条，失败时不会写空文件，并会继续尝试下一候选。
- AKShare 还会读取北交所股票列表里的 `所属行业` 字段，用于补充 `920xxx.BJ` 代码体系。
- Tushare 需要 token 且账号需有 `stock_basic` 权限；BaoStock 真实可用性取决于本机网络能否连接 BaoStock 服务；efinance 实时行情可能不含行业字段。
- 如果已有 `data/industry_mapping.csv`，可回填最新快照并刷新行业聚合：
- 行业页会展示行业映射覆盖率、UNKNOWN 占比、行业热力图和行业排行；UNKNOWN 占比高时热力图不能代表全市场行业分布。
- 可用只读体检命令查看当前覆盖率：

```bash
cd backend
.venv/bin/python -m dataanalysisbase.delivery.cli industry coverage --json
```

- 如需人工补齐静态映射，可导出当前缺口模板：

```bash
cd backend
.venv/bin/python -m dataanalysisbase.delivery.cli industry coverage --missing-output ../data/industry_mapping_missing.csv --json
```

```bash
cd backend
.venv/bin/python -m dataanalysisbase.delivery.cli sync industry-backfill --execute --json
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
GET  /api/v1/sync/market/history
GET  /api/v1/sync/market/{job_id}
POST /api/v1/sync/market/{job_id}/cancel
GET  /api/v1/alerts/market
GET  /api/v1/alerts/market/groups
PATCH /api/v1/alerts/market/{alert_id}
GET  /api/v1/market/overview
GET  /api/v1/stocks
GET  /api/v1/stocks/{security_id}
GET  /api/v1/industries
GET  /api/v1/industries/{industry_code}/stocks
```
