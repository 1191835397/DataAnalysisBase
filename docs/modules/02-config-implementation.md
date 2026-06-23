# config 模块实施记录

| 属性 | 值 |
|------|-----|
| 模块 | `config` |
| 状态 | `implemented` |
| Phase | `A` |
| 负责人 | `TBD` |
| 最近更新 | `2026-06-24` |
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
- 已初始化运行期 `config/` 目录
- 已落地 `providers.yaml`、`sync_schedule.yaml`、`surveillance_rules.yaml`
- 已落地 `watchlist.yaml`、`fusion_policy.yaml`、`reconcile_thresholds.yaml`
- 已新增 `.env.example`
- 已实现 `Settings`、Providers、SyncSchedule、SurveillanceRules、Watchlist、FusionPolicy、ReconcileThresholds 配置模型
- 已实现 `load_*` 系列加载器
- 已补 `backend/tests/config_loader/test_loader.py`

### 进行中

- 等待 Python 3.11 与依赖环境后运行 pytest

### 未开始

- Phase F 配置热加载

## 6. 关键决策

| 决策 | 原因 | 影响 |
|------|------|------|
| 配置统一走 Pydantic 校验 | 启动即发现非法配置 | 减少运行期隐式错误 |
| 密钥只从环境变量读取 | 避免泄漏进仓库 | 部署时需显式配置环境 |

## 7. 与原设计偏差

当前无偏差。实现额外覆盖了 `fusion_policy.yaml` 与 `reconcile_thresholds.yaml`，方便后续 Phase D 复用同一加载器。

## 8. 代码位置

- `backend/src/dataanalysisbase/config_loader/`
- `backend/tests/config_loader/`
- `config/`
- `.env.example`

## 9. 风险与阻塞

- 当前机器缺少 Python 3.11 和项目依赖，完整 pytest 尚未执行
- 配置字段如果与文档命名不一致，会影响多个模块同时对接

## 10. 下一步动作

1. 安装或切换到 Python 3.11
2. 安装后端开发依赖
3. 运行 `pytest backend/tests/config_loader`
