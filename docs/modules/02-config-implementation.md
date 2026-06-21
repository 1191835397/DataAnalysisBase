# config 模块实施记录

| 属性 | 值 |
|------|-----|
| 模块 | `config` |
| 状态 | `planned` |
| Phase | `A` |
| 负责人 | `TBD` |
| 最近更新 | `2026-06-22` |
| 关联设计 | [02-config.md](./02-config.md) |

## 1. 当前目标

建立统一的配置加载与校验层，把 `config/*.yaml` 和环境变量转换为类型安全的配置对象。

## 2. 本次范围

- `settings.py`
- `providers.yaml`、`sync_schedule.yaml`、`surveillance_rules.yaml`、`watchlist.yaml` 的类型定义
- YAML 读取与 Pydantic 校验

不包含：

- Phase F 配置热加载
- 前端运行时配置注入

## 3. 前置依赖

- `domain`
- `pydantic v2`
- `pyyaml` 或等价 YAML 解析库
- `config/` 运行目录

## 4. 实现拆解

1. 确认配置文件 schema
2. 建立 `Settings` 和分模块配置对象
3. 实现 `load_*` 系列函数
4. 补非法配置测试

## 5. 当前进度

### 已完成

- 配置参考文档与样例已存在

### 进行中

- 无

### 未开始

- Python 配置加载器
- 配置模板复制到运行目录

## 6. 关键决策

| 决策 | 原因 | 影响 |
|------|------|------|
| 配置统一走 Pydantic 校验 | 启动即发现非法配置 | 减少运行期隐式错误 |
| 密钥只从环境变量读取 | 避免泄漏进仓库 | 部署时需显式配置环境 |

## 7. 与原设计偏差

当前无实现，暂无偏差。

## 8. 代码位置

- `backend/src/dataanalysisbase/config_loader/`
- `backend/tests/config_loader/`
- `config/`

## 9. 风险与阻塞

- 配置字段如果与文档命名不一致，会影响多个模块同时对接

## 10. 下一步动作

1. 复制 `docs/examples/*.yaml` 到运行期模板
2. 定义配置模型
3. 实现加载器并补校验测试
