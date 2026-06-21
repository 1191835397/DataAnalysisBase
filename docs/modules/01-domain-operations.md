# domain 模块使用说明

| 属性 | 值 |
|------|-----|
| 模块 | `domain` |
| 最近更新 | `2026-06-22` |
| 关联设计 | [01-domain.md](./01-domain.md) |

## 1. 模块用途

为全系统提供统一的领域语言，包括证券 ID、共享枚举和跨模块 DTO。

## 2. 运行方式

```python
from dataanalysisbase.domain.symbols import SecurityId

sid = SecurityId.parse("600519")
print(str(sid))  # 600519.SH
```

## 3. 配置项

无运行期配置项。

## 4. 输入输出

### 输入

- 证券代码字符串
- providers / ingest / storage 间传递的结构化字段

### 输出

- 规范化 `SecurityId`
- 共享 DTO 实例

## 5. 常见问题排查

| 现象 | 可能原因 | 排查方法 |
|------|----------|----------|
| 名称无法解析 | `domain` 不负责名称查库 | 到上层 alias / securities 表做解析 |
| 代码市场后缀错误 | 输入格式不符合规则 | 检查 `parse()` 分支与测试样例 |

## 6. 扩展方式

- 新增市场时先扩枚举，再扩 `SecurityId.parse()`
- 新增跨模块契约时优先放入 `contracts.py`

## 7. 变更注意事项

- 改动 DTO 字段会影响 providers、storage、api 等多个模块
- 改动枚举值前必须检查配置文件和前端常量是否同步
