# 推送前本地检查清单

> **读给**：全部开发者
> **位置**：每轮 `git push` 前执行
> **命令**：`make check`

---

## 快速检查

```bash
# 一键全量
make check

# 或分步：
ruff check .           # 代码风格
pyright src/           # 类型检查（src/ 模块）
pytest -v --tb=short   # 测试
pytest --cov=src --cov-fail-under=80  # 覆盖率
```

---

## 提交前检查清单

在 `git commit` 和 `git push` 之前：

- [ ] `ruff check .` — 零错误
- [ ] `pyright src/` — 零错误、零警告
- [ ] 新增代码有类型注解
- [ ] `pytest -v --tb=short` — 全部通过
- [ ] 新增功能有对应测试
- [ ] 覆盖率 ≥ 80%
- [ ] `git diff --check` — 无空白字符错误

---

## 避免的陷阱

```bash
# ❌ 只跑部分测试
pytest tests/test_a.py        # 其他模块可能坏了

# ❌ 跳过 lint
# 你以为代码没问题？Ruff 会找到

# ❌ 跳过类型检查
# Pyright basic mode 零错误是硬性要求

# ✅ 正确做法
make check   # 一条命令，全部覆盖
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

> **最后更新**: 2026-06-21
