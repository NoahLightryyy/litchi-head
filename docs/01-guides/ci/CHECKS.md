# 推送前本地检查清单

> **读给**：全部开发者
> **位置**：每轮 `git push` 前执行
> **命令**：`python scripts/check.py`

---

## 快速检查

```bash
# 日常开发 —— 按变更范围智能选择测试
python scripts/check.py          # ruff -> pyright -> 模块测试（~40s）

# 跨模块/大重构 —— 全量子集（不含慢测试）
python scripts/check.py --full   # ruff -> pyright -> 全量子集（~3min）

# 慢测试（23 个，~600s）交由 GitHub Actions CI 执行

# Linux/macOS 同样可用
make check                       # 同 --full（委托给 check.py）
```

---

## 提交前检查清单

> **区分"日常提交"和"推送前"**。日常逐次改动跑相关测试即可，全量子集留给推送前和 CI。

### 🔨 日常修改后（每次 git commit 前）

- [ ] `ruff check .` — 零错误
- [ ] `pyright src/` — 零错误、零警告
- [ ] 新增代码有类型注解
- [ ] `python scripts/check.py` — 智能检测变更范围，跑对应测试
- [ ] 新增功能有对应测试
- [ ] `git diff --check` — 无空白字符错误
- [ ] `git diff --name-only --diff-filter=A` — 如有新增文件，搜索旧方案/旧命令/旧路径是否还有残留引用

### 📤 推送前（每次 git push 前）

> Pre-push hook 自动执行 `ruff check .` + `pyright src/` + `pytest -m "not slow" -x`（~70s）。
> **23 个 @pytest.mark.slow 慢测试（~600s）交由 GitHub Actions CI 执行。**

- [ ] `ruff check .` — 零错误（hook 自动）
- [ ] `pyright src/` — 零错误、零警告（hook 自动）
- [ ] `pytest -m "not slow" -x --tb=short` — 快测试子集通过（hook 自动）
- [ ] `git diff --check` — 无空白字符错误
- [ ] 代码审查已完成
- [ ] 引用清理：本次新增的文件是否有旧方案残留未清理？搜索确认

> **如需推送前验证全量测试**（架构变更、大重构）：`python scripts/check.py --full`。

---

## 避免的陷阱

## 三层测试策略

```
pre-push hook   → ruff + pyright + 快测试子集（~70s）    ← 每次推送自动
check.py        → ruff + pyright + 按变更选测试（~40s）   ← 日常开发推荐
check.py --full → ruff + pyright + 全量子集（~3min）      ← 跨模块/推送前
GitHub CI       → ruff + pyright + 全量测试（含慢测试）    ← PR 合并前完整验证
```

```bash
# ✅ 日常开发：自动选模块
python scripts/check.py                    # 改了 src/utils 只跑 test_utils

# ✅ 强制全量子集
python scripts/check.py --full

# ✅ 跟 main 分支比较变更
python scripts/check.py --diff main
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

> **最后更新**: 2026-06-23 | 新增 scripts/check.py 智能变更检测
