# providers 模块使用说明

| 属性 | 值 |
|------|-----|
| 模块 | `providers` |
| 最近更新 | `2026-06-22` |
| 关联设计 | [04-providers.md](./04-providers.md) |

## 1. 模块用途

把外部数据源封装成统一 `RawDataset`，供 ingest 和后续 fusion 使用。

## 2. 运行方式

```python
from dataanalysisbase.providers.registry import ProviderRegistry

registry = ProviderRegistry(...)
dataset = registry.fetch_market_spot()
```

## 3. 配置项

| 配置 | 含义 | 默认值 | 风险 |
|------|------|--------|------|
| provider 启停 | 控制数据源是否参与调度 | 无 | 配错会导致无数据 |
| 优先级 | 多源冲突时排序 | 无 | 会影响后续融合策略 |
| 限流 | 控制访问速率 | 无 | 过高可能被封禁 |

## 4. 输入输出

### 输入

- `DatasetType`
- `security_id`
- provider 配置

### 输出

- `RawDataset`
- `ProviderHealth`

## 5. 常见问题排查

| 现象 | 可能原因 | 排查方法 |
|------|----------|----------|
| 拉取失败 | 源接口变更或网络异常 | 先看 `ProviderError` 明细 |
| 字段不全 | 上游返回列变化 | 检查映射层与原始样本 |
| 多源没生效 | 配置未启用或不支持该类型 | 检查 `supports()` 与配置 |

## 6. 扩展方式

- 新增数据源先实现 Adapter，再注册到 `ProviderRegistry`
- 保持上层只依赖协议，不依赖具体库

## 7. 变更注意事项

- 改 `RawDataset` 输出结构会影响 ingest 与 fusion
- 调整字段映射前要同步更新测试样本
