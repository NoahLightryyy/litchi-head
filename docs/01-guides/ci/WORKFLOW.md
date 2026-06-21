# CI 处理工作流

> **读给**：全部开发者
> **归属**：[🔄 质量保障部](../../06-departments/11-quality-assurance/ROLE.md)
> **流程**：发现 → 定位 → 修复 → 验证 → 复盘

---

## 0. 触发条件

以下任一情况触发本工作流：

- `git push` 后 GitHub Actions 变红
- 本地 `make check` 报错
- 会话启动时 `resume-session` 检测到 CI 状态异常
- Batch Loop 健康自检发现错误

---

## 1. 发现阶段 — 检测到 CI 失败

### 自动检测

| 时机 | 检测方式 | 响应 |
|:-----|:---------|:-----|
| 推送后 | GitHub Actions 自动运行 | 变红即触发 |
| 会话启动 | `resume-session` 检查 CI 状态 | 输出 CI 看板 |
| Batch 收尾 | `make check` | 报错即阻塞提交 |
| 定时 | CI 状态看板 | 质量保障部定期审视 |

### 严重程度分级

| 级别 | 定义 | 响应时间 |
|:----:|:-----|:--------:|
| P0 🔴 | 所有版本失败（3.12 + 3.13 全红） | **立即** |
| P1 🟡 | 单版本失败（如仅 3.13 红） | **当前批次内** |
| P2 🟢 | 非阻塞项失败（pip-audit 警告） | **本次迭代内** |

---

## 2. 定位阶段 — 找到根因

### 快速排查决策树

```
CI 红了
├── Ruff 报错？ → 运行 ruff check . --fix → 自动修
├── Pyright 报错？
│   ├── 3.12 红 → 检查类型注解
│   └── 3.13 红（超时） → TROUBLESHOOTING 查看已知问题
├── Pytest 报错？
│   ├── 测试代码本身有 bug → 修测试
│   └── 实现代码变更导致 → 修实现或更新测试
└── 覆盖率低于 80%？
    └── 补充缺少覆盖的测试
```

### 报错获取

```bash
# 方式一：本地重现
make check

# 方式二：查看 GitHub Actions 日志
# 浏览器打开 https://github.com/NoahLightryyy/litchi-head/actions
# 点击失败 run → 展开失败 step

# 方式三：API 方式
curl -s "https://api.github.com/repos/NoahLightryyy/litchi-head/actions/runs/RUN_ID/jobs"
```

---

## 3. 修复阶段 — 执行修复

### 自动修复规则

| 错误类型 | 是否能自动修 | 方式 |
|:---------|:----------:|:-----|
| Ruff 格式/风格 | ✅ 可自动 | `ruff check . --fix` |
| 简单 Pyright 类型 | ⚠️ 部分可 | 需要判断 |
| Pytest 失败 | ❌ 不可 | 需人工/AI 分析 |
| 覆盖率不足 | ⚠️ 部分可 | 补充测试 |

### 修复纪律

1. **最小改动原则** — 只改导致 CI 失败的部分，不改额外代码
2. **文档同步** — 如果发现新根因，更新 `TROUBLESHOOTING.md`
3. **登记债务** — 如果是长期问题（如架构导致），登记到 `ISSUES.md` 或对应部门 DEBT.md
4. **双版本验证** — 修完后本地 `make check` 确认通过

---

## 4. 验证阶段 — 确认修复

```bash
# 1. 本地全量检查
make check

# 2. 提交并推送
git add -A
git commit -m "fix: <CI 错误描述>"

# 3. 推送后等 CI 跑完
git push
# 检查 Actions 页面确认变绿
```

**严格禁止**：未等待 CI 结果就推送下一个提交。

---

## 5. 复盘阶段 — 防止再犯

每次 CI 修复完成后：

- [ ] TROUBLESHOOTING.md 是否有这个根因？没有就加
- [ ] 现有检查能否在本地拦截这个错误？不能就优化 hook
- [ ] 是否是文档/流程导致的？更新 STANDARDS.md
- [ ] 需要登记债务？更新 ISSUES.md

---

## 6. 异常处理

| 场景 | 处理 |
|:-----|:-----|
| CI 修不好 | 登记为 CI 债务，建分支并跳过 CI 推 |
| 紧急 bug 需要绕过 CI | **禁止**。先修 CI 再修 bug |
| CI 配置本身有问题 | 联系质量保障部更新 `.github/workflows/ci.yml` |
| 长时间（>1h）修不好 | 暂停当前工作，专注修 CI |

---

> **最后更新**: 2026-06-21
