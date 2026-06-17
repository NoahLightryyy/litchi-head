# 05 Provider 抽象模式（数据源）

## 一句话

> **Provider 模式 = 同一个接口，背后可以换不同的数据源。** 今天用 akshare，明天切 Tushare Pro，后天换本地 CSV——但代码不用改。

---

## 为什么需要它？

### 问题场景

你的系统需要股票数据，但数据来源很多：

| 数据源 | 优点 | 缺点 |
|:-------|:-----|:-----|
| **akshare** | 免费，不用注册 | 偶尔不稳定（92% 成功率） |
| **Tushare Pro** | 稳定（99.7%） | 要注册 token |
| **本地 CSV** | 完全可控 | 数据可能过期 |
| **zzshare** | 某种定制源 | 可能有独特数据 |

如果代码直接写成：

```python
import akshare as ak

def get_kline(code: str):
    df = ak.stock_zh_a_hist(symbol=code)   # 写死 akshare
    return df
```

将来想换成 Tushare Pro 怎么办？**所有用到行情数据的地方都要改。** 如果是 20 个文件里有 50 处调用——噩梦。

---

## Provider 模式的解法

画一层**抽象层**：

```
         ┌────────────────────┐
         │  DataProvider (接口) │
         │  + get_kline(code)  │
         │  + get_quote(code)  │
         └─────────┬──────────┘
                   │
        ┌──────────┼──────────┐
        │          │          │
   ┌────┴────┐ ┌──┴───┐ ┌───┴────┐
   │ akshare  │ │Tushare│ │ zzshare│
   │ Provider │ │Provider│ │Provider│
   └─────────┘ └──────┘ └────────┘
```

业务代码只跟 `DataProvider` 接口说话，不关心背后是哪个 Provider。

---

## 项目里的真实代码

打开 `src/data/collector.py`，核心设计：

```python
from abc import ABC, abstractmethod

# 1. 抽象接口
class DataProvider(ABC):
    """所有数据源必须实现这些方法"""
    
    @abstractmethod
    def get_kline(self, code: str) -> pd.DataFrame:
        pass
    
    @abstractmethod
    def get_quote(self, code: str) -> dict:
        pass

# 2. 具体实现 —— akshare 版
class AkshareProvider(DataProvider):
    def get_kline(self, code: str) -> pd.DataFrame:
        import akshare as ak
        return ak.stock_zh_a_hist(symbol=code)
    
    def get_quote(self, code: str) -> dict:
        # ... 用 akshare 实现

# 3. 具体实现 —— zzshare 版（备用）
class ZzshareProvider(DataProvider):
    def get_kline(self, code: str) -> pd.DataFrame:
        # ... 用 zzshare 实现

# 4. 调度器 —— 自动选择
class DataCollector:
    def __init__(self, source: str = "akshare"):
        if source == "akshare":
            self._provider = AkshareProvider()
        elif source == "zzshare":
            self._provider = ZzshareProvider()
    
    def get_kline(self, code: str):
        # 5. 自动 fallback —— 一个不行换另一个
        try:
            return self._provider.get_kline(code)
        except Exception:
            # akshare 炸了？自动换 zzshare
            self._provider = ZzshareProvider()
            return self._provider.get_kline(code)
        # 6. 还不够？最后还有静态数据兜底
```

### 关键设计点

**1. 接口统一**
`get_kline` 不管哪个 Provider 返回的数据格式都是一样的（Pandas DataFrame）。业务代码不用改。

**2. 运行时切换**
```python
# 默认用 akshare
collector = DataCollector(source="akshare")

# 一行切换
collector = DataCollector(source="tushare")  # 如果将来实现
```

**3. 自动 fallback**
akshare 挂了？不用你去手动切换，代码自动试下一个源。

**4. 生产配置**
在 `backend/config.py` 里配一次，整个项目生效：
```python
class Settings(BaseModel):
    data_source: str = "akshare"   # 生产环境改成 "tushare"
```

---

## 为什么不用 if-else？

```python
# 如果你不用 Provider 模式：
def get_kline(code: str, source: str):
    if source == "akshare":
        return ak.stock_zh_a_hist(symbol=code)
    elif source == "tushare":
        return ts.pro_bar(ts_code=code)
    elif source == "csv":
        return pd.read_csv(f"{code}.csv")
    # 加一个新源 → 改这个函数 → 可能影响其他调用

# 用 Provider 模式：
def get_kline(code: str):
    return self._provider.get_kline(code)
    # 加一个新源 → 新建一个 Provider 类 → 不影响任何现有代码
```

**开闭原则**：对扩展开放（加新的 Provider 类），对修改关闭（不改已有代码）。

---

## 你面试被问到可以说

> "我用 Provider 模式做数据源抽象，这样 akshare 挂了自动 fallback 到备用源，切换数据源也不用改业务代码。这个模式的核心就是针对接口编程，不针对实现编程。"

---

## 自己试试（5 分钟）

1. 打开 `src/data/collector.py`
2. 找到 `DataProvider` 接口类，看看定义了哪些方法
3. 找到 `AkshareProvider`，看它怎么实现 `get_kline`
4. 思考一个问题：**如果我想加一个 TushareProProvider，需要改哪些文件？**

---

**上一篇：[FastAPI 桥接层架构](04-fastapi-bridge.md)**

**下一篇：[纯 Python 技术指标计算](06-technical-indicators.md)** — 不依赖 numpy 算 MA/RSI/MACD
