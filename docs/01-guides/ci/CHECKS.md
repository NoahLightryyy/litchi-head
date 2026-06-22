# 推送前本地检查清单

> **读给**：全部开发者
> **位置**：每轮 `git push` 前执行
> **命令**：`make check`

---

## 快速检查

```bash
# 分级运行：
make lint              # 代码风格（~5s）
make type              # 类型检查（~25s）
pytest -m "not slow"   # 快测试子集（~30s）
make check             # 全量 = lint + type + 全量测试（~12min）

# 慢测试单独运行
pytest -m slow         # 23 个慢测试（~11min）
```

---

## 提交前检查清单

> **区分"日常提交"和"推送前"**。日常逐次改动跑相关测试即可，全量留给推送前和 CI。

### 🔨 日常修改后（每次 git commit 前）

- [ ] `ruff check .` — 零错误
- [ ] `pyright src/` — 零错误、零警告
- [ ] 新增代码有类型注解
- [ ] `pytest <本次改动的相关测试文件>` — 全部通过
- [ ] 新增功能有对应测试
- [ ] `git diff --check` — 无空白字符错误

### 📤 推送前（每次 git push 前）

> Pre-push hook 自动执行 `ruff check .` + `pyright src/` + `pytest -m "not slow" -x`（~70s）。
> **23 个 @pytest.mark.slow 慢测试（~600s）交由 GitHub Actions CI 执行。**

- [ ] `ruff check .` — 零错误（hook 自动）
- [ ] `pyright src/` — 零错误、零警告（hook 自动）
- [ ] `pytest -m "not slow" -x --tb=short` — 快测试子集通过（hook 自动）
- [ ] `git diff --check` — 无空白字符错误
- [ ] 代码审查已完成

> **如需推送前验证全量测试**（架构变更、大重构）：手动 `make check`。

---

## 避免的陷阱

## 三层测试策略

```
pre-push hook → ruff + pyright + 快测试子集（~70s）    ← 每次推送自动
GitHub CI     → ruff + pyright + 全量测试（含慢测试）   ← PR 合并前完整验证
手动 make check → ruff + pyright + 全量测试             ← 大重构前自选
```

```bash
# ✅ 日常开发：跑相关测试
pytest tests/test_data/test_data_providers.py   # 改了 data 模块
pytest tests/test_debate/                       # 改了 debate 模块

# ✅ 推送前：hook 自动跑快子集
pytest -m "not slow" -x --tb=short              # ~30s

# ✅ 最终整合 / 大清理：全量测试
pytest -v --tb=short                            # 全量，约 12min
```

---

## CI 债务门禁

如果检查无法通过且不能立即修复：

```bash
# 1. 登记 CI 债务
# 编辑 docs/01-guides/ci/ISSUES.md

# 2. 如果可以建分支推送（绕过 main 保护）
git checkout -b fix/ci-xxx
git push -u origin fix/ci-xxx

# 3. 在分支上修复后再合并
```

---

> **最后更新**: 2026-06-22 | 三层测试策略（快/慢标记）
