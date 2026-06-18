# 编码规范与工程原则

| 属性 | 值 |
|------|-----|
| 版本 | v0.1.0 |
| 状态 | 约束（编码期强制） |
| 目标 | 统一全项目的代码风格与工程范式，作为逐模块实现时的硬约束清单 |

> 关联：[MODULE_DESIGN.md](./MODULE_DESIGN.md) §9（架构级编码约定）· [ARCHITECTURE.md](./ARCHITECTURE.md) · [AGENT_INTELLIGENCE.md](./AGENT_INTELLIGENCE.md) §1.1（LLM 铁律）

本文件分两部分：**A. 代码风格**（怎么写得统一）与 **B. 工程设计原则**（怎么写得正确、可测、可维护）。两者在每个模块编码前都应对照。

---

## A. 代码风格

### A.1 语言与工具链

| 项 | 选型 | 说明 |
|----|------|------|
| Python | 3.11+ | 用 `match`、`X \| None`、`tomllib` 等现代特性 |
| 包管理 | `pyproject.toml`（PEP 621） | 单一依赖与配置入口 |
| Lint + Format | **Ruff** | 同时做 lint 与 format，替代 black/isort/flake8 |
| 类型检查 | **mypy**（strict） | CI 门禁，新增代码不得引入 `Any` 泄露 |
| 数据模型/校验 | **Pydantic v2** | 配置、DTO、外部边界数据校验 |
| 测试 | **pytest** + pytest-asyncio | 见 §B.8 |
| 前端 | TypeScript strict + ESLint + Prettier | 见 `modules/09-frontend.md` |

`pyproject.toml` 关键约定（实现时落地）：

```toml
[tool.ruff]
line-length = 100
target-version = "py311"
[tool.ruff.lint]
select = ["E", "F", "I", "N", "UP", "B", "SIM", "RUF"]   # 含 import 排序(I)、命名(N)、bugbear(B)
[tool.mypy]
python_version = "3.11"
strict = true
warn_unused_ignores = true
```

### A.2 命名

| 对象 | 规范 | 示例 |
|------|------|------|
| 包/模块 | 小写下划线 | `snapshot_repo.py` |
| 类 | PascalCase | `SurveillanceEngine` |
| 函数/变量 | snake_case | `compute_data_status` |
| 常量 | UPPER_SNAKE | `DEFAULT_PAGE_SIZE` |
| 私有 | 前导下划线 | `_build_query` |
| 类型别名 | PascalCase | `SecurityId`, `RunId` |
| 布尔 | is_/has_/should_ 前缀 | `is_trading_day`, `has_unresolved_l3` |

业务术语统一用领域词汇（与文档一致）：`security_id`、`snapshot_time`、`canonical_*`、`reconciliation_issues`、`data_status`，禁止自造同义词（如 `stock_code`/`ts`/`quality`）。

### A.3 格式

- 行宽 100；缩进 4 空格；文件以 LF 结尾、UTF-8。
- import 分三组（标准库 / 第三方 / 本项目），由 Ruff `I` 自动排序。
- 一律使用绝对导入：`from dataanalysisbase.domain import SecurityId`。
- 不留被注释掉的死代码；不用 `print` 调试（用 logging，见 §B.3）。

### A.4 类型注解（强制）

- 所有公开函数/方法必须有完整参数与返回类型注解。
- 优先 `X | None` 而非 `Optional[X]`；集合用内置泛型 `list[...]`/`dict[...]`。
- 跨模块传递的数据**必须是带类型的 DTO**（`@dataclass(frozen=True)` 或 Pydantic），**禁止裸传 `DataFrame`/`dict`**（呼应 MODULE_DESIGN §9「契约先行」）。
- DataFrame 只在模块内部（如 providers/analytics 计算）使用，出模块边界前转 DTO。

### A.5 docstring 与注释

- 公开类/函数用 docstring 说明**意图与契约**（做什么、关键参数含义、异常、副作用），不复述实现。
- 注释解释「为什么」，不解释「做了什么」。禁止逐行翻译式注释。
- docstring 与注释用中文（与现有设计文档一致）；标识符用英文。

```python
def compute_data_status(latest_run: SnapshotRun | None, now: datetime) -> DataStatus:
    """根据最近一次快照运行判定数据状态。

    超过 stale 阈值返回 stale；最近运行失败返回 failed；无运行返回 offline。
    用于 API envelope 的 meta.data_status，避免前端误读旧数据。
    """
```

---

## B. 工程设计原则

### B.1 模块边界（继承 MODULE_DESIGN §9，强制）

- 依赖单向向下，禁止环依赖（依赖图见 MODULE_DESIGN §2）。
- 只有 `storage` 写 SQL；其他模块通过 repository 方法访问数据。
- 只有 `providers` 可 `import akshare/tushare`。
- `surveillance` 不调用 LLM；LLM 叙事在 `intelligence`。
- `intelligence`/`analytics`/`api` 只读 `canonical_*`/`*_snapshots`/聚合表，不直连数据源。

### B.2 纯函数 vs 副作用边界

- 计算逻辑（指标、对账分级、估值、异常分）写成**无 IO 的纯函数**，便于单测与复用。
- IO（DB、网络、文件、LLM）集中在 repository / adapter / service 编排层。
- domain 层零 IO、零业务逻辑（仅模型与契约）。

### B.3 日志

- 用标准 `logging`，模块级 `logger = logging.getLogger(__name__)`。
- 结构化关键字段：`security_id`、`snapshot_time`、`run_id`、`source`、`severity`。
- 级别约定：DEBUG 开发细节 / INFO 任务里程碑（同步开始结束、告警数）/ WARNING 可恢复降级（stale、单源失败）/ ERROR 需关注失败。
- **禁止记录密钥**（API key、webhook URL、SMTP 密码）。

### B.4 错误处理与异常层级

- 定义统一根异常，分层派生；每个模块抛**自己语义的异常**，不向上泄露第三方异常。

```python
class DABError(Exception): ...                 # 项目根异常
class ConfigError(DABError): ...
class ProviderError(DABError): ...             # 含 source、是否可重试
class StorageError(DABError): ...
class FusionBlockedError(DABError): ...         # L3 阻断
class LLMError(DABError): ...
```

- fail-fast：配置非法、schema 缺失等启动期问题立即报错，不带病运行。
- 可恢复降级（stale 数据、单源失败、LLM 不可用）必须**显式表达**给上层（返回状态/置信度），不静默吞掉。
- 不写空 `except:`；捕获要么处理要么裹成本模块异常重抛。

### B.5 配置与密钥

- 阈值/规则/调度/通道一律走 `config`（YAML + Pydantic 校验），禁止硬编码魔法数。
- 密钥只从环境变量读（`DEEPSEEK_API_KEY`、`WECHAT_WEBHOOK`…），提供 `.env.example`，`.env` 不入库。
- 配置对象不可变（frozen），全局只在启动加载一次。

### B.6 时间、时区与交易日历

- 全系统用**带时区**的 datetime，统一 `Asia/Shanghai`；存储与 API 用 ISO 8601。
- 交易日/除权除息判断走 `ingest.trading_calendar`，禁止各模块各自判断。
- 价格趋势类计算统一用**前复权**序列（避免除权日误报，见 MARKET_SURVEILLANCE §5.2.1）。

### B.7 数据正确性与幂等

- 所有写入按幂等键 upsert（如快照 `(snapshot_time, security_id, source)`），重复同步不产生重复行。
- DuckDB **单写者**：写进程（ingest/surveillance）串行；API 用只读连接（见 `modules/03-storage.md`、`08-api.md`）。
- 外部边界数据（provider 返回、LLM 输出、用户输入）一律先 Pydantic 校验再入流程。
- **LLM 不产数字**：LLM 输出的数值必须 ⊆ Tool 返回值（幻觉检测）；存在未解决 L3 时禁止确定性结论（AGENT_INTELLIGENCE §1.1）。

### B.8 测试规范

- 框架 pytest；目录 `tests/` 镜像源码结构；文件 `test_*.py`；用例命名 `test_<场景>_<预期>`。
- 分层：
  - **单元**：纯函数（指标、对账分级、估值、data_status 判定）——必须覆盖边界（空、缺口、停牌、除权、首快照）。
  - **集成**：mock provider/LLM，用临时 DuckDB 验证「同步→落库→聚合」「双源→canonical+issues」全链。
  - **契约回归**：固定输入 snapshot 对比融合/研报结构。
- 外部依赖（akshare/tushare/DeepSeek/网络）一律 mock，CI 不联网。
- 覆盖率目标：核心计算与 storage ≥ 85%；交付层（api/cli）≥ 60%。
- 测试只通过公开接口，不测私有实现细节。

### B.9 异步与并发

- IO 密集（多源并行拉取、LLM 调用、WebSocket）用 `async`；CPU 计算（指标）保持同步纯函数。
- 不在 async 函数里做阻塞调用（DuckDB 同步调用放线程池或集中在写进程）。
- providers 并行拉取做错误隔离：单源异常不影响其他源（见 `modules/04-providers.md`）。

### B.10 可观测内建

- 同步任务、规则求值、LLM 调用都埋点到 `observability`（耗时、成功率、告警量、token 成本）。
- 对外响应统一带 `data_status`（fresh/stale/partial/failed/offline），不让前端裸读可能过期的数据。

---

## C. Git 与协作

- 提交信息遵循 Conventional Commits：`feat|fix|docs|refactor|test|chore(scope): 描述`。
- 一次提交聚焦一件事；提交前本地通过 Ruff + mypy + pytest。
- 建议 `pre-commit` 钩子：ruff format、ruff lint、mypy（增量）。
- 分支：`main` 保持可运行；功能走 `feat/<模块>-<简述>`。

---

## D. 实现期检查清单（每个模块完成时自检）

- [ ] 仅依赖依赖图允许的上游，无环依赖
- [ ] 跨模块只传 DTO，无裸 DataFrame/dict
- [ ] 公开接口类型注解 + docstring 完整
- [ ] 计算为纯函数，IO 集中在边界
- [ ] 异常裹成本模块语义异常；降级显式
- [ ] 写入幂等；配置外置；无硬编码阈值/密钥
- [ ] 单元 + 集成测试覆盖边界场景，外部依赖已 mock
- [ ] Ruff / mypy / pytest 全绿
- [ ] 关键路径埋点到 observability

---

*本文件为编码期强制约束；与各模块详细设计（`docs/modules/`）配合使用。算法与表结构以专题文档为准，风格与范式以本文件为准。*
