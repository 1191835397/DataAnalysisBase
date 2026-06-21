# observability 模块使用说明

| 属性 | 值 |
|------|-----|
| 模块 | `observability` |
| 最近更新 | `2026-06-22` |
| 关联设计 | [07-observability.md](./07-observability.md) |

## 1. 模块用途

为同步链路、系统状态和前端顶栏提供统一的可观测与状态判断能力。

## 2. 运行方式

```python
from dataanalysisbase.observability.status import compute_data_status
```

## 3. 配置项

| 配置 | 含义 | 默认值 | 风险 |
|------|------|--------|------|
| stale 阈值 | 超时多久算旧数据 | 45 分钟 | 过短会频繁告警，过长会误导用户 |

## 4. 输入输出

### 输入

- 最近同步运行记录
- 当前时间
- 指标快照

### 输出

- `DataStatus`
- 系统状态 DTO

## 5. 常见问题排查

| 现象 | 可能原因 | 排查方法 |
|------|----------|----------|
| 顶栏状态不对 | 口径不一致或时间比较错误 | 检查 `compute_data_status()` |
| 页面一直 stale | 最新快照未提交成功 | 检查 `market_snapshot_runs` |

## 6. 扩展方式

- 新指标先定义记录接口，再补状态接口输出
- 尽量保持观测对象可序列化、可展示

## 7. 变更注意事项

- 改 `data_status` 规则会影响所有页面展示
