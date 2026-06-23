# storage 模块实施记录

| 属性 | 值 |
|------|-----|
| 模块 | `storage` |
| 状态 | `implemented` |
| Phase | `A` |
| 负责人 | `TBD` |
| 最近更新 | `2026-06-24` |
| 关联设计 | [03-storage.md](./03-storage.md) |

## 1. 当前目标

建立 DuckDB 存储层、schema、repository 和聚合表刷新机制，作为 Phase A 的核心基础设施。

## 2. 本次范围

- `DuckDBStore`
- `schema.sql`
- `SnapshotRepo`
- `AggregateRepo`
- `market_snapshots`、`market_snapshot_runs`、`latest_market_snapshot`、`market_overview_snapshots`、`industry_snapshots`

不包含：

- Chroma 向量库
- Phase E 归档器
- Focus/Fusion 的 canonical 全量表

## 3. 前置依赖

- `domain`
- DuckDB
- 本地数据库路径约定

## 4. 实现拆解

1. 设计并落地首批 DDL
2. 实现连接管理与事务包装
3. 实现快照写入与幂等 upsert
4. 实现聚合表刷新
5. 补 repository 集成测试

## 5. 当前进度

### 已完成

- 存储详细设计已完成
- 已落地 `schema.sql`
- 已实现 `DuckDBStore`
- 已实现 `SnapshotRepo`
- 已实现 `AggregateRepo`
- 已补 `backend/tests/storage/test_repositories.py`

### 进行中

- 等待 Python 3.11、DuckDB 与 Pydantic 依赖后运行集成测试

### 未开始

- migrations runner
- 只读连接防御测试
- Phase E archiver

## 6. 关键决策

| 决策 | 原因 | 影响 |
|------|------|------|
| SQL 只允许在 `storage` 层 | 保持访问边界清晰 | 上层只能通过 repo 调用 |
| API 使用只读连接 | 避免 DuckDB 写锁冲突 | 需区分读写进程 |

## 7. 与原设计偏差

当前无偏差。首版聚合刷新使用物化表方式，符合设计中“首期物化表”的建议。

## 8. 代码位置

- `backend/src/dataanalysisbase/storage/`
- `backend/tests/storage/`

## 9. 风险与阻塞

- 当前机器缺少 Python 3.11 和项目依赖，完整 pytest 尚未执行
- DuckDB upsert 方案要兼顾幂等与性能
- 聚合表口径一旦定下，后续 API 和前端都会依赖

## 10. 下一步动作

1. 安装或切换到 Python 3.11
2. 安装后端开发依赖
3. 运行 `pytest backend/tests/storage`
