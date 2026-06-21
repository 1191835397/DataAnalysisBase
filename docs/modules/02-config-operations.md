# config 模块使用说明

| 属性 | 值 |
|------|-----|
| 模块 | `config` |
| 最近更新 | `2026-06-22` |
| 关联设计 | [02-config.md](./02-config.md) |

## 1. 模块用途

负责读取运行期 YAML 与环境变量，并向后端模块暴露类型化配置对象。

## 2. 运行方式

```python
from dataanalysisbase.config_loader.loader import load_settings, load_providers

settings = load_settings()
providers = load_providers()
```

## 3. 配置项

| 配置 | 含义 | 默认值 | 风险 |
|------|------|--------|------|
| `config/providers.yaml` | Provider 启停与优先级 | 无 | 配错会影响采集链路 |
| `config/sync_schedule.yaml` | 调度周期 | 无 | 会影响快照频率 |
| `config/surveillance_rules.yaml` | 监管规则与去重 | 无 | 误配会导致噪音告警 |
| 环境变量 | API Key / Token | 无 | 缺失会导致对应功能不可用 |

## 4. 输入输出

### 输入

- YAML 文件
- `.env` 或系统环境变量

### 输出

- `Settings`
- `ProvidersConfig`
- `SyncSchedule`
- `SurveillanceRules`

## 5. 常见问题排查

| 现象 | 可能原因 | 排查方法 |
|------|----------|----------|
| 启动失败 | 配置缺字段或字段类型错误 | 检查异常信息对应的配置路径 |
| Provider 未启用 | `enabled` 或优先级配置错误 | 检查 `providers.yaml` |
| 密钥读取不到 | 环境变量未导出 | 检查进程环境和 `.env` |

## 6. 扩展方式

- 新增配置文件先定义 Pydantic 模型，再实现 `load_*`
- 避免在业务模块里直接读 YAML

## 7. 变更注意事项

- 改配置字段名时要同步更新文档、样例文件和消费方
