# CI 维护手册

> **读给**：[🔄 CI 治理部](../../06-departments/11-ci-governance/ROLE.md)
> **目的**：CI 配置维护、检查项增删、hook 管理等操作指引。

---

## 1. GitHub Actions 工作流

### 配置文件位置

```
.github/workflows/ci.yml
```

### 当前检查项

见 [STANDARDS.md](STANDARDS.md#1-ci-检查项定义)。

### 手动触发

```bash
# 通过 gh CLI
gh workflow run CI --ref main

# 浏览器
# 打开 https://github.com/NoahLightryyy/litchi-head/actions
# 选择 CI workflow → Run workflow
```

### 查看最近运行

```bash
curl -s "https://api.github.com/repos/NoahLightryyy/litchi-head/actions/runs?per_page=5"
```

---

## 2. 添加新检查项

### 步骤

1. 在 `.github/workflows/ci.yml` 的 `steps` 下新增 step
2. 更新 `STANDARDS.md` 的检查项表格
3. 在 `CHECKS.md` 的本地检查清单中增加对应项
4. 如果有本地等效命令，加入 `Makefile`
5. 提交并验证 CI 通过

### 模板

```yaml
- name: <中文检查名>
  run: <检查命令>
```

---

## 3. Pre-push Hook 管理

### 安装

```bash
# 创建 pre-push hook
cat > .git/hooks/pre-push << 'EOF'
#!/bin/bash
echo "=== CI 本地预检 ==="
make check || exit 1
EOF
chmod +x .git/hooks/pre-push
```

> ⚠️ `.git/hooks/` 不被版本控制。如需团队共享，应将 hook 脚本版本化：
> 将脚本放在 `scripts/pre-push.sh`，然后在 README 中指引开发者运行
> `git config core.hooksPath scripts/hooks` 或手动复制。

### 跳过 hook

```bash
# 紧急情况（如修 CI 本身）
git push --no-verify

# 使用后必须立即说明原因
```

---

## 4. Makefile 管理

### 当前 CI 相关命令

```makefile
lint:   ruff check .           # 代码风格
type:   pyright src/           # 类型检查
test:   pytest -v --tb=short   # 测试
check:  lint type test         # 一键三连
```

### 修改规则

- `make check` 必须包含 `make lint` + `make type` + `make test`
- 新增检查项 → 同步更新 `make check`
- 新增检查项 → 同步更新 `STANDARDS.md`

---

## 5. CI 状态 Badge

当前 README.md 中 CI badge：

```markdown
[![CI](https://github.com/NoahLightryyy/litchi-head/actions/workflows/ci.yml/badge.svg)](https://github.com/NoahLightryyy/litchi-head/actions)
```

如果 badge 显示 `failing`，说明 CI 当前是红的。

---

## 6. 问题排查

| 问题 | 可能原因 | 修复 |
|:-----|:---------|:-----|
| CI 不触发 | workflow 文件未在 main 分支 | 确认 `.github/workflows/ci.yml` 存在 |
| step 无故被 cancelled | CI 总运行时间超过限制 | 减少不必要的依赖安装 |
| 安装依赖失败 | pip index 超时 | 添加 `pip --timeout=60` 或使用国内镜像 |
| 测试结果不稳定 | 网络依赖测试 flaky | 标记为 `@pytest.mark.flaky` 或使用 vcr 录制 |

---

## 7. CI 优化建议

| 优化项 | 预期收益 | 难度 |
|:-------|:--------|:----:|
| 增加缓存（pip 缓存已配置，可考虑 pre-commit 缓存） | 减少 ~30s 安装时间 | 低 |
| 分离 lint 和 test 为独立 job（并行） | 减少 ~50% wall-clock | 中 |
| 测试分片（按目录） | 大规模时减少 ~60% | 高 |
| 增加 pre-commit hook（版本化） | 本地拦截率提升 | 低 |

---

> **最后更新**: 2026-06-21
