# 🔬 CI 健康急救

> Ruff、Pyright、测试三者不全绿不提交。
> **这条是纪律，不是建议。**

---

## 症状速查

| 症状 | 诊断 | 修复 |
|:-----|:-----|:------|
| `ruff check .` 报错 | 代码风格/导入/未使用变量 | `ruff check --fix .` 自动修，剩的手动 |
| `pyright src/` 报错 | 类型不匹配/属性不存在 | 看具体 error line 修 |
| `pytest --tb=short -q` FAIL | 测试破坏 | `--tb=long` 看完整错误定位 |
| CI main 上常绿，本地不绿 | 文件没 add | `git stash` 再 `git pull` 再检查 |

---

## 一键检查

```bash
# 全量三合一
ruff check . && echo "RUFF OK" &&
pyright src/ && echo "PYRIGHT OK" &&
python -m pytest --tb=short -q &&
echo "CI ALL GREEN"
```

---

## Ruff 常见修复

### 自动修复（先跑这个）

```bash
ruff check --fix .
# 能自动修 30-50% 的问题：import 排序、未用导入、空 f-string
```

### 常见手动修复

| 规则码 | 含义 | 修复方法 |
|:------|:-----|:---------|
| `F841` | 未使用变量 | 删掉赋值，或者前面加 `_`（如 `_ = func()`） |
| `E501` | 行超 100 字符 | 拆多行、拆变量、或 `# noqa: E501`（仅限测试文件名超长场景） |
| `F541` | 空 f-string `f""` | 改成 `""` |
| `E402` | import 不在文件顶 | 如果是惰性导入（避免 torch crash），加 `# noqa: E402` |
| `F401` | import 未使用 | 删掉，或者 `# noqa: F401`（仅限类型检查用的 import） |

### 命名规范 N 类

```bash
# ruff 会检查 N801/N802/N803/N806 等命名规范
# 常见：变量名用 snake_case，类名用 PascalCase，常量用 UPPER_CASE
```

---

## Pyright 常见修复

### 运行

```bash
pyright src/        # 只检 src，不含 tests
pyright src/ tests/ # 检全部
```

### 常见类型错误

| 错误 | 原因 | 修复 |
|:-----|:-----|:-----|
| `reportCallIssue` | 参数名对不上 | 检查 API 实际参数名（用 `help(func)` 看签名） |
| `reportAttributeAccessIssue` | 属性不存在 | 用 `getattr(obj, "attr", None)` 安全访问 |
| `reportOptionalMemberAccess` | 可能为 None | 加 `if x is not None:` 或 `assert x is not None` |
| `reportGeneralTypeIssues` | 类型不兼容 | 加 `cast()` 或调整类型注解 |

### 绕行方案

```python
# 场景：adata API 版本不同，参数名可能变
# 方案：用 getattr + 安全包装
industry = getattr(self._adata.stock.info, "all_industry", None)
if industry is None:
    return []
df = industry()

# 场景：pandas iterrows 推断为 Series|ndarray
# 方案：显式转换
code = str(row.get("code", ""))
price = float(row.get("price", 0.0))
```

---

## 测试常见修复

| 症状 | 原因 | 修复 |
|:-----|:-----|:------|
| `ModuleNotFoundError` | conftest 找不到 | 检查 `tests/conftest.py` 或模块级 `conftest.py` |
| `fixture not found` | fixture 没 import | 确认 conftest 定义了 fixture 或用 `pytest_plugins` |
| 集成测试 `skip` | 网络不通 | 检查 `urllib.request.urlopen` 连通性检测 |
| 异步测试超时 | await 没写 | 加 `await` 或 `pytest.mark.asyncio` |

---

## CI 流程纪律（已写入 CLAUDE.md）

```
每轮 Batch 收尾前自动跑:
  ruff check . + pyright src/ → 有红先修 → 修不了登记债务 → 再提交
```

**不在合并时留红。** CI 不绿 → 说明有未完成的技术债务。
