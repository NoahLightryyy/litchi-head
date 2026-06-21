# 🧪 类型检查急救

> Pyright basic mode 零错误通过是硬性要求（CLAUDE.md 技术红线第 3 条）。

---

## 症状速查

| 症状 | 常见原因 | 修复 |
|:-----|:---------|:------|
| `Cannot access attribute "xxx"` | 属性不存在或类型推断为 `Any` | 加 `cast()` 或检查类型定义 |
| `No parameter named "xxx"` | 函数参数名不匹配 | `help(func)` 看实际签名 |
| `Object of type "None"` | 返回值可能为 None | 加 `assert x is not None` 或 `if x:` |
| `Argument of type "X" cannot be assigned` | 参数类型不匹配 | 显式转换 `str()` / `float()` |

---

## pandas iterrows 模式（最高频）

Pyright 会把 `row["col"]` 推断为 `Series | ndarray | Any`，导致任何赋值都报类型不匹配。

```python
# ❌ 错误：Pyright 报 type mismatch
StockInfo(code=row["code"], name=row["name"])
# → Argument of type "Series | ndarray | Unknown" cannot be assigned

# ✅ 正确：显式转换
StockInfo(
    code=str(row.get("code", "")),
    name=str(row.get("name", "")),
    price=float(row.get("最新价", 0.0)),
    volume=int(row.get("成交量", 0)),
)
```

**黄金法则**：
- 字符串字段 → `str(row.get("col", ""))`
- 数字字段 → `float(row.get("col", 0.0))` 或 `int(row.get("col", 0))`
- 可能 None 的字段 → 用 `safe_str()` / `safe_float()` / `safe_int()`（定义在 `providers/base.py`）

---

## import 位置（E402）

Pyright 也遵循 PEP 8 的 import 位置规则。顶层 import 之外的 import 会报 `E402`。

### 惰性导入（有意为之）

```python
# 如果惰性导入是为了避免 Windows torch crash
# 所有惰性 import 后加 # noqa: E402
from src.debate.reflection import generate_reflection  # noqa: E402
```

### sys.path 修改后导入（脚本场景）

```python
# scripts/xxx.py
import sys
from pathlib import Path
_root = str(Path(__file__).resolve().parent.parent)
sys.path.insert(0, _root)

# 这些 import 依赖 sys.path 修改，必须加 noqa
from src.debate.models import DebateInput  # noqa: E402
```

---

## 测试文件名超长（E501）

测试方法和 fixture 名称组合后常超 100 字符。

```python
# 方法一：括号换行
async def test_run_sets_confidence_without_knowledge(  # noqa: E501
    self, agent_with_skill, ctx, make_analysis,
):

# 方法二：仅在万不得已时用 noqa 跳过
# 不推荐无脑 noqa，优先用方法一
```

---

## Pydantic 模型字段验证

```python
# 字段约束帮助 Pyright 类型推断
class StockQuote(BaseModel):
    code: str = ""
    price: float = Field(default=0.0, ge=0.0)
    volume: int = Field(default=0, ge=0)

# model_validator 校验多字段关系
@model_validator(mode="after")
def check_ohlc(self) -> Self:
    """确保 OHLC 价格合理"""
    if self.high < self.low:
        raise ValueError("high must be >= low")
    return self
```

---

## 通用 Pyright 调试技巧

```bash
# 看具体错误类型
pyright src/your/file.py

# 只检查某个文件
pyright src/debate/orchestrator.py

# 输出 JSON 格式错误（方便解析）
pyright --outputjson src/
```

### 常见绕行方案

| 场景 | 方案 |
|:-----|:------|
| 三方库没类型注解 | `# type: ignore[import]` |
| 匿名函数类型复杂 | `from typing import cast; cast(Callable, x)` |
| 可选链太长 | `assert` 提前缩小类型范围 |
| 配置类动态属性 | 加 `__getattr__` 注解 → `def __getattr__(self, name: str) -> Any: ...` |
