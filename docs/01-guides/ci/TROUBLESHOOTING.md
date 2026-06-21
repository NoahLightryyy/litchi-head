# CI 常见失败根因与修复

> **读给**：全部开发者（AI + 人类）
> **目的**：经验知识库，每次 CI 修完就更新，越积越厚。
>
> 按「症状 → 根因 → 修复」格式，搜症状定位。

---

## Pyright

### Pyright 在 Python 3.13 上超时/取消

| 字段 | 值 |
|:-----|:---:|
| **症状** | CI: 3.13 job 中 Pyright step 被 cancelled，后续步骤全 skipped |
| **根因** | Python 3.13 是超前兼容版本。Pyright 在 3.13 上解析类型时可能遇到新语法导致超时（CI 单步 timeout 约 60s） |
| **修复** | 1. 先确保 3.12 全绿<br>2. 3.13 的 Pyright 允许超时不阻塞（见 STANDARDS.md §4）<br>3. 如果 3.13 也有新错误，需要检查是否有 Python 3.13 特有语法问题 |
| **验证** | `pyright src/` 在 Python 3.12 环境下通过即视为 CI 通过 |
| **登记** | 2026-06-21 — 已知，不阻塞合并 |

### Pyright 报类型错误

| 字段 | 值 |
|:-----|:---:|
| **症状** | `pyright src/` 报类型不匹配 |
| **常见根因** | 1. 函数签名改了但调用方没更新<br>2. `pandas` DataFrame `iterrows()` 返回类型未显式转换<br>3. Pydantic model 字段类型不匹配 |
| **修复模板** | 见下方「pandas iterrows 类型」 |
| **pandas 修复** | `StockInfo(code=str(row["code"]), name=str(row["name"]))` — 所有从 DataFrame 取的值必须 `str()`/`int()`/`float()` 显式转换 |

---

## Pytest

### 测试失败

| 字段 | 值 |
|:-----|:---:|
| **症状** | `pytest -v --tb=short` 报 FAILED |
| **排查** | 查看具体哪个测试失败 |
| **可能根因** | 1. 实现代码改了但测试没同步<br>2. 外部数据源变化（akshare 返回值格式变更）<br>3. Mock 不完整导致实际调用了网络<br>4. 新加功能没写测试 |
| **修复** | 见 WORKFLOW.md §3 |

### Pytest exit code 4（用法错误）

| 字段 | 值 |
|:-----|:---:|
| **症状** | CI 中 pytest 运行仅 4 秒就退出，exit code 4（usage error），无具体测试 FAILED 输出 |
| **根因** | ⚠️ **尚不明确** — 本地 Win 3.14 环境 945 tests 全绿通过，无法复现 |
| **已知** | 1. 首次出现于 commit `14312ee6`（文档大重组）<br>2. 最近 5 次 CI 运行（SHA: 85713a5→8025fb54）均为此模式<br>3. 仅 3.12 矩阵出现此问题，3.13 是 Pyright 超时被 cancelled |
| **排查难点** | GitHub API 无管理员权限无法获取日志，`gh` CLI 未安装，本地不能复现 |
| **排查方案** | A. 推送新 CI 运行实时观察<br>B. 手动在 GitHub Actions 页面查看日志<br>C. 安装 gh CLI 认证后获取日志 |
| **登记** | 2026-06-21 — 关联 CI-001 |

### 集成测试跳过

| 字段 | 值 |
|:-----|:---:|
| **症状** | `pytest` 输出中显示 `skipped` 但非 `passed` |
| **根因** | 代理环境下东方财富 API 不可达，`urllib.request.urlopen(..., timeout=3)` 检测失败时自动跳过 |
| **处理** | 本地/CI 环境正常跑时不跳过，CI 上检测到 API 可达即可。这是预期行为 |
| **注意** | CI 环境（ubuntu-latest）应可达东方财富 API。如果 CI 也跳过，说明 GitHub Actions IP 被限 |

### adata 未安装导致 ADataSource 构造失败

| 字段 | 值 |
|:-----|:---:|
| **症状** | `TestADataSourceErrorHandling` 中 7 个测试全部报 `ImportError: adata 未安装，请执行: pip install adata` |
| **根因** | `adata` 是实盘数据源（同花顺+东方财富+新浪+腾讯+百度），已在本地开发环境安装，但 `pyproject.toml` 的 `dependencies` 中未声明 → CI 环境下 `pip install -e ".[dev]"` 不安装，`ADataSource.__init__` 抛 ImportError |
| **修复** | `pyproject.toml` 的 `[project] dependencies` 添加 `"adata>=2.9.0"` |
| **验证** | CI 重新运行，`TestADataSourceErrorHandling` 7 tests 全部通过 |
| **登记** | 2026-06-21 — commit 6fd83f4 |

---


### Ruff 报格式/风格错误

| 字段 | 值 |
|:-----|:---:|
| **症状** | `ruff check .` 报 E*** / F*** / W*** |
| **修复** | `ruff check . --fix` 自动修复 |
| **预防** | PostWrite hook 已配置自动 `ruff check --fix`，不应出现此问题。如果出现说明 hook 失效 |

---

## Coverage

### 覆盖率低于 80%

| 字段 | 值 |
|:-----|:---:|
| **症状** | `FAIL Required test coverage of 80% not reached` |
| **修复** | 新增测试覆盖未覆盖的代码路径 |
| **查看** | `pytest --cov=src --cov-report=term-missing` 列出缺失行 |

---

## pip-audit

### 依赖漏洞

| 字段 | 值 |
|:-----|:---:|
| **症状** | pip-audit 发现已知 CVE |
| **处理** | 仅 🟡 警告，不阻塞。升级受影响包即可 |
| **注意** | 升级前确认不破坏兼容性 |

---

> **最后更新**: 2026-06-21 | CI 治理体系创建，记录了首次连续失败分析的已知问题
