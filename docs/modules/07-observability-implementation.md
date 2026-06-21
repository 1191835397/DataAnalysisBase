# observability 模块实施记录

| 属性 | 值 |
|------|-----|
| 模块 | `observability` |
| 状态 | `planned` |
| Phase | `A/B` |
| 负责人 | `TBD` |
| 最近更新 | `2026-06-22` |
| 关联设计 | [07-observability.md](./07-observability.md) |

## 1. 当前目标

为 Phase A 提供最基本的可观测能力：同步结果记录、`data_status` 计算、系统状态汇总。

## 2. 本次范围

- `compute_data_status()`
- `Metrics.record_sync()`
- `/system/status` 所需的数据汇总对象

不包含：

- LLM 成本统计
- Phase F 复杂指标与热加载观测

## 3. 前置依赖

- `storage`
- `domain`
- `config`

## 4. 实现拆解

1. 定义指标对象与状态计算函数
2. 接入 ingest 链路埋点
3. 组装系统状态 DTO
4. 补边界状态测试

## 5. 当前进度

### 已完成

- 设计文档已完成

### 进行中

- 无

### 未开始

- 指标模型
- 状态计算
- API 集成

## 6. 关键决策

| 决策 | 原因 | 影响 |
|------|------|------|
| 所有页面统一依赖 `data_status` | 避免前后端各自判断旧数据 | 状态口径必须单一 |
| 观测优先做同步与数据质量 | Phase A 最需要的是知道数据是否可信 | 先不追求复杂指标体系 |

## 7. 与原设计偏差

当前无实现，暂无偏差。

## 8. 代码位置

- `backend/src/dataanalysisbase/observability/`
- `backend/tests/observability/`

## 9. 风险与阻塞

- stale/partial/failed 的口径若不统一，会直接影响 UI 可信度

## 10. 下一步动作

1. 实现 `compute_data_status()`
2. 接入 `MarketBulkSync`
3. 提供 `/system/status` 所需数据结构
