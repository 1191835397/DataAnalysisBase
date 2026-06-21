# ingest 模块实施记录

| 属性 | 值 |
|------|-----|
| 模块 | `ingest` |
| 状态 | `planned` |
| Phase | `A` |
| 负责人 | `TBD` |
| 最近更新 | `2026-06-22` |
| 关联设计 | [05-ingest.md](./05-ingest.md) |

## 1. 当前目标

跑通 Phase A 的全市场快照主链路：拉取 -> 标准化 -> 落库 -> 聚合刷新 -> 任务状态记录。

## 2. 本次范围

- `MarketBulkSync`
- `RunTracker`
- `TradingCalendar`
- `Scheduler` 的 Phase A 最小注册

不包含：

- Focus 5 分钟深度同步
- Fusion 触发
- 复杂失败重试编排

## 3. 前置依赖

- `providers`
- `storage`
- `config`
- `observability`

## 4. 实现拆解

1. 实现 `MarketBulkSync.run()`
2. 实现运行状态 begin/commit
3. 刷新聚合表
4. 接入交易日历守卫
5. 补全链路集成测试

## 5. 当前进度

### 已完成

- 详细设计已完成

### 进行中

- 无

### 未开始

- Sync 编排代码
- Scheduler
- 集成测试

## 6. 关键决策

| 决策 | 原因 | 影响 |
|------|------|------|
| 同步链路串行提交 | 降低状态混乱与重复写入风险 | 吞吐较低但更稳 |
| 快照运行单独记录状态表 | 便于 UI 呈现 fresh/stale/partial/failed | API 可直接暴露数据质量 |

## 7. 与原设计偏差

当前无实现，暂无偏差。

## 8. 代码位置

- `backend/src/dataanalysisbase/ingest/`
- `backend/tests/ingest/`

## 9. 风险与阻塞

- 交易日历与真实交易时段口径必须统一
- 快照 partial/failure 判定阈值需在实现中明确

## 10. 下一步动作

1. 实现 `MarketBulkSync`
2. 接上 `SnapshotRepo` 与 `AggregateRepo`
3. 补一次完整链路测试
