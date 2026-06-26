# providers 模块验证记录

| 属性 | 值 |
|------|-----|
| 模块 | `providers` |
| 验证状态 | `passed` |
| 最近更新 | `2026-06-25` |
| 关联实现 | [04-providers-implementation.md](./04-providers-implementation.md) |

## 1. 验收目标

- 可以拉取一份全市场现货快照并封装为 `RawDataset`
- 单源错误能被隔离并结构化返回
- Provider 健康状态可查询

## 2. 测试范围

- 单元测试：字段映射、raw_hash、路由逻辑
- 集成测试：mock `akshare` 返回 DataFrame 转 `RawDataset`
- 手动验证：执行一次市场快照拉取

## 3. 验证清单

| 项 | 方法 | 结果 | 备注 |
|----|------|------|------|
| `AkshareAdapter.fetch_market_snapshot()` 成功 | 单元测试 | `passed` | Fake DataFrame-like 输入，不联网 |
| DataFrame 正确映射为 `MarketSnapshotBatch` / `MarketRow` | 单元测试 | `passed` | 覆盖代码、名称、价格、涨跌幅、量比、估值、行业 |
| 单源异常被包装为 `ProviderError` | 单元测试 | `passed` | 覆盖 fetcher 异常 |
| `ProviderRegistry` 路由正确 | 单元测试 | `passed` | 覆盖优先级、禁用 provider、未知 provider |
| `dab sync market` 默认 dry-run | 单元测试 | `passed` | 不调用 provider，不写 DuckDB |
| provider 本地健康检查 | 单元测试 | `passed` | 覆盖依赖存在、token 缺失、禁用 provider、未知 provider |
| `/api/v1/system/status` provider health | API 测试 | `passed` | 返回 `providers` 列表 |
| provider 联网健康检查 | 单元测试 + CLI/API 测试 | `passed` | 显式 `--online` / `online=true` 才探测上游端点，不拉取行情数据 |
| 真实 `dab sync market --execute` | 手动验证 | `passed` | 2026-06-26 10:56:34 +08:00，`expected=5367`、`actual=5367`、`missing=0` |
| 最近 market run 状态 | CLI/API 测试 + 手动验证 | `passed` | `dab status --json` 返回 `last_market_run` 和失败原因 |
| provider retry wrapper | 单元测试 | `passed` | 只重试 `retryable=True` 的 `ProviderError`，使用指数退避 |
| provider rate limit wrapper | 单元测试 | `passed` | 按 `requests_per_minute` 控制单进程最小间隔 |
| AKShare 备用现货接口 | 单元测试 | `passed` | `stock_zh_a_spot_em` 失败后 fallback 到 `stock_zh_a_spot`，不联网 |
| AKShare 行业字段补全 | 单元测试 | `passed` | mock 行业板块和成分股接口；行业接口失败时不阻断快照 |
| 行业备用映射入口 | 单元测试 | `passed` | `industry_mapping_fetcher` 可补行业；板块接口结果优先；映射失败不阻断快照 |
| 本地行业映射文件 | 单元测试 | `passed` | 支持 CSV / JSON；`ProviderRegistry` 可按 `industry_mapping_path` 注入读取器 |
| 行业映射诊断 | 单元测试 | `passed` | `dab doctor` 可报告映射文件缺失 warning、解析成功记录数 |
| 真实 AKShare 行业接口 | 手动验证 | `blocked` | `stock_board_industry_name_em` 当前返回 `RemoteDisconnected` |

## 4. 边界场景

- 空数据集
- 字段缺失
- 超时或网络异常
- 非法 `DatasetType`

## 5. 已知问题

- 免费源仍可能因上游策略、接口变更或网络权限失败，需要保留失败 run 与 status 诊断
- 行业补全已具备降级实现，但真实行业接口当前不可用，真实同步仍可能继续产生 `UNKNOWN` 行业
- 本地行业映射文件入口已接入 registry，但真实 `data/industry_mapping.csv` 尚未生成或维护

## 6. 剩余风险

- AKShare/Eastmoney 免费接口稳定性不可保证，后续仍需观察失败率并评估 Tushare / 其他源补充
- 行业分类仍需要落地真实映射文件或自动生成流程，否则行业页数据质量依赖单个 AKShare 行业接口

## 7. 验收结论

当前达到最小 adapter、registry、手动同步入口、本地 provider health、显式联网健康检查、指数退避 retry / 限流 wrapper、AKShare 备用现货接口、失败 run 持久化与真实成功快照验证标准。行业字段补全、本地备用映射入口和 registry 注入已通过 mock 测试，但真实行业接口当前阻塞，需后续补充真实映射文件或自动生成流程。
