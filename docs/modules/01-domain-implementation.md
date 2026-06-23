# domain 模块实施记录

| 属性 | 值 |
|------|-----|
| 模块 | `domain` |
| 状态 | `implemented` |
| Phase | `A` |
| 负责人 | `TBD` |
| 最近更新 | `2026-06-23` |
| 关联设计 | [01-domain.md](./01-domain.md) |

## 1. 当前目标

完成全系统共享 DTO、枚举、`SecurityId` 解析和值对象定义，作为后续所有模块的类型基础。

## 2. 本次范围

- 定义 `Market`、`DatasetType`、`RunStatus`、`DataStatus` 等枚举
- 定义 `SecurityId`、`RawDataset`、`MarketRow`、`SyncResult`、`FusionResult`
- 提供 `parse` 与 `to_source_code` 契约

不包含：

- 名称到证券 ID 的数据库解析
- 任意 IO、配置读取、指标计算

## 3. 前置依赖

- Python `3.11+`
- `pydantic v2`
- 无上游业务模块依赖

## 4. 实现拆解

1. 建立 `enums.py`、`symbols.py`、`models.py`、`contracts.py`
2. 完成 `SecurityId.parse()` 与 `to_source_code()`
3. 为 DTO 补类型、可空性与校验规则
4. 补单元测试

## 5. 当前进度

### 已完成

- 详细设计文档已完成
- 已初始化 `backend/src/dataanalysisbase/domain/`
- 已实现枚举、`SecurityId`、source code 格式化、核心 DTO
- 已补 `backend/tests/domain/test_symbols.py`

### 进行中

- 等待 Python 3.11 环境后运行测试

### 未开始

- Pydantic DTO 运行期测试

## 6. 关键决策

| 决策 | 原因 | 影响 |
|------|------|------|
| `domain` 保持零 IO | 避免底层模块带副作用 | 所有上层都可安全导入 |
| 跨模块统一 DTO | 降低隐式字段漂移 | 后续 API、storage、providers 契约更稳定 |

## 7. 与原设计偏差

当前无实现，暂无偏差。

## 8. 代码位置

- `backend/src/dataanalysisbase/domain/`
- `backend/src/dataanalysisbase/common/errors.py`
- `backend/tests/domain/test_symbols.py`

## 9. 风险与阻塞

- 当前机器默认 `python3` 是 3.9，未安装 Python 3.11，暂不能运行基于 `StrEnum` 的测试
- 北交所号段推断规则需在实现时用真实样本校验
- 基金/ETF/指数的 ID 归类边界后续可能需要扩展

## 10. 下一步动作

1. 安装或切换到 Python 3.11
2. 安装后端开发依赖
3. 运行 `pytest backend/tests/domain`
