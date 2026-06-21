# 模块详细设计索引

> 关联：[../MODULE_DESIGN.md](../MODULE_DESIGN.md)（模块总览与边界）· [../ARCHITECTURE.md](../ARCHITECTURE.md)

本目录把 [MODULE_DESIGN.md](../MODULE_DESIGN.md) 的每个模块拆成**可直接编码的详细设计**：完整类结构、方法签名、状态机/时序、表 DDL、错误处理、测试用例清单。

进入实现阶段后，模块还需要补齐“交付文档包”，规则见 [../MODULE_DELIVERY_STANDARD.md](../MODULE_DELIVERY_STANDARD.md)，模板见 [../MODULE_DELIVERY_TEMPLATE.md](../MODULE_DELIVERY_TEMPLATE.md)。

## 拆分进度（按 Phase 批次）

| 批次 | 模块 | 文档 | 状态 |
|------|------|------|------|
| Phase A | domain | [01-domain.md](./01-domain.md) | ✅ |
| Phase A | config | [02-config.md](./02-config.md) | ✅ |
| Phase A | storage | [03-storage.md](./03-storage.md) | ✅ |
| Phase A | providers | [04-providers.md](./04-providers.md) | ✅ |
| Phase A | ingest | [05-ingest.md](./05-ingest.md) | ✅ |
| Phase B | surveillance | [06-surveillance.md](./06-surveillance.md) | ✅ |
| Phase B/A | observability | [07-observability.md](./07-observability.md) | ✅ |
| Phase A+ | api | [08-api.md](./08-api.md) | ✅ |
| Phase A+ | frontend | [09-frontend.md](./09-frontend.md) | ✅ |
| Phase C/E | analytics | [10-analytics.md](./10-analytics.md) | ✅ |
| Phase D | fusion | [11-fusion.md](./11-fusion.md) | ✅ |
| Phase D/F | intelligence | [12-intelligence.md](./12-intelligence.md) | ✅ |
| Phase F | portfolio | [13-portfolio.md](./13-portfolio.md) | ✅ |
| Phase A/E | delivery | [14-delivery.md](./14-delivery.md) | ✅ |

## 模块交付文档包

进入编码阶段的模块，除设计文档外，还应同步维护：

- `*-implementation.md`
- `*-verification.md`
- `*-operations.md`

Phase A 首批已初始化如下：

| 模块 | 设计 | 实施记录 | 验证记录 | 使用说明 |
|------|------|----------|----------|----------|
| domain | [01-domain.md](./01-domain.md) | [01-domain-implementation.md](./01-domain-implementation.md) | [01-domain-verification.md](./01-domain-verification.md) | [01-domain-operations.md](./01-domain-operations.md) |
| config | [02-config.md](./02-config.md) | [02-config-implementation.md](./02-config-implementation.md) | [02-config-verification.md](./02-config-verification.md) | [02-config-operations.md](./02-config-operations.md) |
| storage | [03-storage.md](./03-storage.md) | [03-storage-implementation.md](./03-storage-implementation.md) | [03-storage-verification.md](./03-storage-verification.md) | [03-storage-operations.md](./03-storage-operations.md) |
| providers | [04-providers.md](./04-providers.md) | [04-providers-implementation.md](./04-providers-implementation.md) | [04-providers-verification.md](./04-providers-verification.md) | [04-providers-operations.md](./04-providers-operations.md) |
| ingest | [05-ingest.md](./05-ingest.md) | [05-ingest-implementation.md](./05-ingest-implementation.md) | [05-ingest-verification.md](./05-ingest-verification.md) | [05-ingest-operations.md](./05-ingest-operations.md) |
| observability | [07-observability.md](./07-observability.md) | [07-observability-implementation.md](./07-observability-implementation.md) | [07-observability-verification.md](./07-observability-verification.md) | [07-observability-operations.md](./07-observability-operations.md) |
| api | [08-api.md](./08-api.md) | [08-api-implementation.md](./08-api-implementation.md) | [08-api-verification.md](./08-api-verification.md) | [08-api-operations.md](./08-api-operations.md) |
| frontend | [09-frontend.md](./09-frontend.md) | [09-frontend-implementation.md](./09-frontend-implementation.md) | [09-frontend-verification.md](./09-frontend-verification.md) | [09-frontend-operations.md](./09-frontend-operations.md) |

## 每篇文档的统一结构

```text
1. 模块定位与边界    做什么 / 不做什么
2. 目录与文件        包内结构
3. 数据结构与类      核心 dataclass/Pydantic/类（带字段与方法签名）
4. 核心流程          时序图 / 状态机 / 算法
5. 对外接口契约      其他模块怎么调用
6. 配置与表          读取配置、读写 DuckDB 表 DDL
7. 错误处理与降级    异常分类与兜底
8. 测试用例清单      单测/集成测试要点
9. 开放问题          实现期需确认的点
```

## 阅读建议

先读 [MODULE_DESIGN.md](../MODULE_DESIGN.md) 建立全局模块边界，再按 Phase A 主线依次读 `01`→`05`，即为第一批编码顺序。全部 14 个模块详细设计已完成（`01`→`14`），可按 Phase 顺序进入实现阶段。
