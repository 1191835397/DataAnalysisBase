# ingest 模块使用说明

| 属性 | 值 |
|------|-----|
| 模块 | `ingest` |
| 最近更新 | `2026-06-22` |
| 关联设计 | [05-ingest.md](./05-ingest.md) |

## 1. 模块用途

编排数据采集任务，把 provider 数据转成结构化快照并写入存储层。

## 2. 运行方式

```bash
# 示例：手动触发一次市场快照
python -m dataanalysisbase.ingest.market_bulk_sync
```

## 3. 配置项

| 配置 | 含义 | 默认值 | 风险 |
|------|------|--------|------|
| 快照周期 | 全市场任务运行频率 | 30 分钟 | 周期过短会加大源压力 |
| 交易时段 | 限定任务运行窗口 | 无 | 配错会错过或误跑任务 |
| 完整率阈值 | 判定 partial/failed | 待定 | 影响 UI 状态 |

## 4. 输入输出

### 输入

- provider 返回的 `RawDataset`
- 调度时间
- 交易日历

### 输出

- `market_snapshots`
- `market_snapshot_runs`
- 聚合表刷新结果

## 5. 常见问题排查

| 现象 | 可能原因 | 排查方法 |
|------|----------|----------|
| 没有生成快照 | 非交易日或调度未命中 | 检查交易日历与调度配置 |
| 状态一直失败 | provider 拉取失败或写库失败 | 从运行状态表和日志定位 |
| 数据不完整 | 上游缺失或阈值设置过严 | 检查 expected/actual 与原始拉取结果 |

## 6. 扩展方式

- 新增任务类型时复用 `RunTracker`
- 保持链路清晰：fetch -> normalize -> write -> aggregate -> commit

## 7. 变更注意事项

- 修改状态流会影响 observability 和 API 的 `data_status`
- 修改任务时段前要同步检查 `sync_schedule.yaml`
