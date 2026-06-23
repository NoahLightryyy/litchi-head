# 07 类型注解与 Pyright

## 一句话

> **类型注解就是在代码里标明"这个变量是什么类型"**。它不是写给 Python 解释器看的（Python 不检查类型），是写给**人**和**工具**看的。

---

## 没有类型注解的时候

```python
def analyze(stock_data, config):
    result = process(stock_data)
    return result
```

代码写的时候没问题。但三天后回来看：
- `stock_data` 是 dict 还是 DataFrame？
- `config` 里有哪些字段可取？
- `result` 是字符串还是对象？
- 只能去看调用处的传参才能猜，或者加 print 调试

---

## 加了类型注解之后

```python
from pydantic import BaseModel
import pandas as pd

class Config(BaseModel):
    source: str
    max_retries: int

def analyze(stock_data: pd.DataFrame, config: Config) -> list[float]:
    result = process(stock_data)
    return result
```

现在一看就知道：
- `stock_data` 是 Pandas DataFrame ✅
- `config` 是 Pydantic Model，有 `source` 和 `max_retries` 字段 ✅
- 返回 `list[float]` ✅

---

## 类型注解只是注释？不对——Pyright 帮你检查

类型注解 + **Pyright** = 在代码跑起来之前发现 bug。

```python
def calc_ma(closes: list[float], period: int) -> list[float]:
    ...

result = calc_ma("000001", 5)  # ❌ 传入字符串，但期望是 list[float]
```

Pyright 会报错：
```
Argument of type "str" cannot be assigned to parameter "closes"
```

**你在编辑器里就已经看到这个红线了，不用等到运行才炸。**

---

## 项目里的实战案例

### 1. 函数参数和返回值

```python
def get_kline(code: str, count: int = 100) -> pd.DataFrame:
    """获取K线数据"""
    # code → 必须传字符串
    # count → 必须传整数，不传默认 100
    # 返回 → DataFrame
```

### 2. Pydantic Model 本身就是类型

```python
class StockQuote(BaseModel):
    code: str
    price: float

def get_quote(code: str) -> StockQuote:
    """返回值类型明确 —— StockQuote 实例"""
    ...

# 调用时，IDE 自动提示 .code 和 .price
quote = get_quote("000001")
quote.price  # ✅ IDE 自动补全
```

### 3. Union / Optional

```python
from typing import Optional

def calc_ma(closes: list[float], period: int) -> list[Optional[float]]:
    """返回列表，前面 N 天可能为空"""
    ...
# Optional[float] = "要么是 float，要么是 None"
```

### 4. 自定义类型别名

```python
StockCode = str  # 类型别名，表示"这是个股票代码"
def search(code: StockCode) -> StockQuote:
    ...
```

---

## Pyright 的工作方式

| 对比 | Pyright | mypy |
|:-----|:--------|:------|
| 速度 | ✅ 极快（微软写的，TypeScript 那套移植过来） | ❌ 慢 |
| 安装 | ✅ VSCode Pylance 自带 | ❌ 要单独装 |
| 严格度 | 支持 basic + strict 模式 | 支持渐进式 |
| 配置 | `pyproject.toml` 或 `pyrightconfig.json` | `mypy.ini` |

项目用的 **Pyright basic mode**，配置在 `pyproject.toml` 里：

```toml
[tool.pyright]
typeCheckingMode = "basic"  # basic 模式，不是 strict（要求没那么变态）
include = ["src"]           # 只检查 src/
```

---

## 不写类型注解的后果

项目 CLAUDE.md 明确规定：

> **类型注解必须完整 — Pyright basic mode 零错误通过**

如果有文件类型注解不完整，`python scripts/check.py` 会失败，CI 也会挂。

---

## 自己试试（3 分钟）

1. 运行 `make type`，看看 Pyright 报哪些错
2. 打开任意一个 `.py` 文件，把鼠标悬停在一个函数参数上——IDE 会展示类型信息
3. 试着去掉一个函数的返回类型注解：
   ```python
   def calc_ma(closes, period):   # 去掉 list[float] 和 -> list[float]
   ```
   然后跑 `make type`，看 Pyright 报什么

---

**上一篇：[纯 Python 技术指标计算](06-technical-indicators.md)**

**下一篇：[Pydantic Settings 配置管理](08-pydantic-settings.md)** — 环境变量 + 配置文件统一管理
