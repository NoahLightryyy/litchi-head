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

> **区分"日常提交"和"推送前"**。日常逐次改动跑相关测试即可，全量留给推送前和 CI。

### 🔨 日常修改后（每次 git commit 前）

- [ ] `ruff check .` — 零错误
- [ ] `pyright src/` — 零错误、零警告
- [ ] 新增代码有类型注解
- [ ] `pytest <本次改动的相关测试文件>` — 全部通过
- [ ] 新增功能有对应测试
- [ ] `git diff --check` — 无空白字符错误

### 📤 推送前 / 最终整合（每次 git push 前）

- [ ] （上面日常的 6 项）
- [ ] `pytest -v --tb=short` — **全量**测试全部通过
- [ ] 覆盖率 ≥ 80%
- [ ] 代码审查已完成

---

## 避免的陷阱

```bash
# ❌ 跳过 lint
ruff check .            # 哪怕只改了一行也要跑

# ❌ 跳过类型检查
pyright src/            # Pyright basic mode 零错误是硬性要求

# ✅ 日常开发：跑相关测试
pytest tests/test_data/test_data_providers.py   # 改了 data 模块
pytest tests/test_debate/                       # 改了 debate 模块

# ✅ 最终整合 / 大清理：全量测试
pytest -v --tb=short                            # 全量，CI 前必跑
```

> **测试范围原则**：日常开发只跑本次改动相关的测试文件，节省时间。全量测试（`make test` / `pytest -v --tb=short`）留给最终整合、架构级变更、以及 CI 自己去跑。

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
