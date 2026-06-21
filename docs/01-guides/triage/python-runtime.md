# 🐍 Python 运行时急救

> Windows 下 Python 开发的特有问题，特别是 torch/transformers 兼容性。

---

## 症状速查

| 症状 | 诊断 | 修复 |
|:-----|:-----|:------|
| `Windows torch access violation` | transformers 链导入 torch 时 crash | 惰性导入 `torch` 相关模块 |
| `UserWarning: pydantic v1 not compatible with 3.14` | langchain 依赖 pydantic v1 | 等上游升级，暂时忽略 |
| `UserWarning: pkg_resources deprecated` | setuptools 版本问题 | 忽略，仅报警 |
| `ImportError: No module named 'adata'` | 可选依赖未安装 | `pip install adata` |

---

## Transformer/Torch Access Violation

### 现象

```python
from src.debate.orchestrator import DebateOrchestrator
# → Windows fatal exception: access violation
```

### 原因

`transformers` 库链导入 `torch`，而 `torch` 在 Windows 上有线程安全问题。
具体链：`orchestrator.py` → `reflection.py` → `llm_service` → transformers → torch。

### 修复

把 torch 相关模块做**惰性导入**——在文件末尾、函数内部或条件导入：

```python
# src/debate/orchestrator.py

logger = logging.getLogger(__name__)

# ---- 以下是顶层非 torch 导入 ----
from src.agents.base import AgentContext

# ---- torch 相关放后面，用 noqa E402 标记 ----
from langgraph.graph import END, StateGraph  # noqa: E402 — 惰性导入
from src.agents.master_agent import MasterAgent  # noqa: E402
from src.debate.reflection import generate_reflection  # noqa: E402
from src.utils.llm import llm_service  # noqa: E402
```

### 检测方法

```python
# 在 __init__.py 里惰性导入
# __init__.py
from src.debate.orchestrator import DebateOrchestrator  # noqa: F401

# 改成
def get_orchestrator():
    from src.debate.orchestrator import DebateOrchestrator
    return DebateOrchestrator()
```

---

## Python 3.14 + Pydantic v1 警告

```bash
UserWarning: Core Pydantic V1 functionality isn't compatible with Python 3.14
```

**原因**：`langchain_core` 内部用了 pydantic v1，而 Python 3.14 移除了 pydantic v1 依赖的某些 API。

**影响**：无。代码正常运行，测试全部通过。

**长期**：等 langchain 升级到完全兼容 pydantic v2。

---

## pip-audit CVE 警告

CI 中 `pip-audit` 可能会报 CVE 漏洞，但目前设为了**仅警告不阻塞**：

```yaml
- name: Dependency audit
  run: |
    pip-audit || echo "⚠️ pip-audit 发现已知 CVE（仅警告，不阻塞构建）"
```

**什么时候修**：当 CVE 影响运行时安全性（如 RCE、SSRF 等 critical 级别）时再修。

---

## Windows 特有编码问题

Git Bash 下某些 Windows 命令输出乱码：

```bash
# 在 Git Bash 里跑 ipconfig /flushdns
# → 输出乱码（GBK 编码问题）
# 解决方法：用 cmd.exe /c 包裹
cmd.exe /c ipconfig /flushdns
```

```bash
# 或者临时设置编码
export LANG=zh_CN.GBK
ipconfig /flushdns
```
