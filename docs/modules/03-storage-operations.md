# storage 模块使用说明

| 属性 | 值 |
|------|-----|
| 模块 | `storage` |
| 最近更新 | `2026-06-22` |
| 关联设计 | [03-storage.md](./03-storage.md) |

## 1. 模块用途

作为系统唯一的结构化存储访问层，负责 DuckDB 建表、读写和聚合表维护。

## 2. 运行方式

```python
from dataanalysisbase.storage.duckdb_store import DuckDBStore
from dataanalysisbase.storage.repositories.snapshot_repo import SnapshotRepo
```

## 3. 配置项

| 配置 | 含义 | 默认值 | 风险 |
|------|------|--------|------|
| DuckDB 路径 | 主库文件位置 | 待定 | 路径错误会导致无法启动 |
| 只读模式 | API 读库连接 | `False` | 误用会导致写失败 |

## 4. 输入输出

### 输入

- `MarketRow`
- 查询参数 DTO

### 输出

- DuckDB 表数据
- 分页结果、聚合结果、运行状态

## 5. 常见问题排查

| 现象 | 可能原因 | 排查方法 |
|------|----------|----------|
| 写入失败 | schema 未初始化或连接模式错误 | 检查建表流程和连接参数 |
| 数据重复 | 幂等键未生效 | 检查 upsert 主键与测试 |
| API 读不到最新数据 | 聚合表未刷新 | 检查 `AggregateRepo.refresh_*` 调用链 |

## 6. 扩展方式

- 新增表先补 DDL，再补 repository，再补验证记录
- 上层不得直接写 SQL

## 7. 变更注意事项

- 表结构变更会影响 ingest、api、frontend 查询口径
- 修改主键或状态字段前必须补回归测试
