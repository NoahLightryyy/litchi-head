# resume-session — 会话快速恢复

> **目的**：新会话 30 秒内恢复上下文，输出摘要，**停在决策点等你指方向**。
> 封装 AGENTS.md Batch Loop 模式的前两步（恢复上下文 → 给你看一眼）。
>
> **⚠️ 核心纪律**：本 Skill 输出摘要后就停，**不准自己决定下一步干什么**。

## 触发条件

用户说以下任一即触发：
- "继续"、"接着做"、"上次做到哪了"
- "恢复会话" / "resume" / "开始工作"
- 任何不明确任务的新消息（隐含"我要继续工作"）

## 执行步骤

### 第 1 层：快速同步（必读，~3-5K token）

```
1. 读取 docs/01-guides/HANDOVER.md
   → §1 项目身份卡 + 🏢 各部门一览 + 🎯 当前跨部门优先级

2. 读取 docs/04-changelog/logs/README.md
   → 用 grep '^\|.*\d{4}-\d{2}-\d{2}' 提取日志索引表格的最新条目
   → 不要直接 tail — 文件末尾是 footer 链接，不是索引条目

3. 读取最新工作日志正文（前一步确定的路径）
   → 了解前次会话具体做了什么
```

### 第 2 层：精度验证（必须执行，确认为止）

> **核心原则**：文档可能过时。信任代码 > 信任文档。
> 以下每一项都交叉验证，发现不一致立即标记。

```
☐ 测试数验证
  运行: pytest --collect-only -q 2>&1 | tail -1
  对比: 交接文档 🏢 各部门一览 写的测试数
  不一致 → 标记 ⚠️ "文档显示 N tests，实际 M tests，交接文档需要更新"

☐ 关键文件存在性
  交接文档 🏢 各部门一览 或工作日志中列出的核心文件路径（如 src/debate/orchestrator.py）
  逐一 verify 文件存在
  不存在 → 标记 ⚠️ "引用文件 X 不存在，可能已移动/删除"

☐ Git 状态
  git status --short
  有未提交变更 → 标记 ⚠️ "工作区有未提交修改，请确认是否需要先处理"

☐ 前一会话是否完整关闭
  检查：工作日志末尾是否有「上下文耗尽，续接」标记
  有 → 说明前次会话中断，需要额外读取上下文
  无 → 正常关闭，交接完整

☐ CI 状态
  检查 GitHub Actions 最新运行状态
  运行（自包含 Python，无 curl/文件依赖）：
  py -3 -c "
import json, urllib.request
try:
    URL = 'https://api.github.com/repos/NoahLightryyy/litchi-head/actions/runs?per_page=5'
    req = urllib.request.Request(URL, headers={'User-Agent': 'litchi-head/1.0'})
    with urllib.request.urlopen(req, timeout=10) as resp:
        data = json.loads(resp.read().decode('utf-8'))
    results = [r['conclusion'] for r in data['workflow_runs'] if r.get('conclusion')]
    success, failure = results.count('success'), results.count('failure') + results.count('cancelled')
    print(f'Recent {len(results)} runs: {success} success, {failure} failed')
    if failure > 0:
        for r in data['workflow_runs'][:5]:
            title = r.get('display_title', '?')[:50]
            print(f'  {title:50s} → {r.get(\"conclusion\", \"?\")}')
except Exception as e:
    print(f'NETWORK_ERROR: Unable to check CI status: {e}')
"
  输出 "NETWORK_ERROR: ..." → 标记 ⚠️ "CI 状态检查失败（网络不可达），需手动确认"
  输出中有 failure > 0 → 标记 ⚠️ "CI 非绿色（最近 N 次中 M 次失败），建议先处理 CI 再继续"
  且 如果连续失败 ≥ 3 次 → 标记 🔴 "CI 连续失败严重，需优先处理"
```

### 第 3 层：按需加载（用到才读）

```
- 技术债务日志 — 要修债务时（先看 ROUTER.md 找部门，再读对应 DEBT.md）
- docs/00-overview/ROADMAP.md — 查全局进度时
- docs/00-overview/OVERVIEW.md — 新开发者看项目概览
- 部门角色 — 要开工时（docs/06-departments/{id}/ROLE.md）
- ADR — 涉及技术选型时（docs/05-decisions/README.md）
```

## 输出格式

```markdown
## 📋 当前进度
- 状态: [从 HANDOVER 🏢 各部门一览 + 🎯 优先级]
- 上次完成: [从工作日志提取]
- 测试: N tests collected

## 精度检查结果
| 检查项 | 结果 |
|--------|------|
| 测试数一致 | ✅ / ⚠️ 差 N |
| 关键文件存在 | ✅ / ⚠️ X 不存在 |
| Git 干净 | ✅ / ⚠️ N 个未提交 |
| 前次正常关闭 | ✅ / ⚠️ 上下文耗尽 |
| CI 状态 | 🟢 绿 / ⚠️ 最近 N 次失败 M 次 / 🔴 连续失败 ≥3 / ⚠️ 网络不可达 |

## 🚦 等你指方向
> ⚠️ 本 Skill 到此为止。等你给一句话说干什么。
```

## ⚠️ 核心纪律

1. **输出摘要后立即停** — 不准继续往下读/改/修任何东西
2. **等你给方向** — "修债务" / "继续做功能" / "验证 UI" / "别的" 都行
3. **方向明确后才拆 todo** — 拆完给你看一眼确认了再开干
4. **所有引用路径必须用新目录结构** — `docs/01-guides/workflow/` / `docs/06-departments/` 等

## 精度异常处理

| 异常 | 处理 |
|------|------|
| 测试数不匹配 | 输出警告 + 建议先更新 HANDOVER 再继续 |
| 核心文件缺失 | 暂停，让用户确认文件是否被移动 |
| 工作区不干净 | 列出变更，询问是否先处理 |
| 前次上下文耗尽 | 额外读取上一会话工作日志，标记"中断续接" |
| CI 非绿色 | 标记到输出摘要，建议先修 CI 再推进 —— 参见 [CI 治理](../../../docs/01-guides/ci/README.md) |
| CI 连红 ≥3 | **暂停**，优先处理 CI —— 按 [CI 处理工作流](../../../docs/01-guides/ci/WORKFLOW.md) 执行 |
| CI 网络检查失败 | 输出 ⚠️ "CI 状态检查失败（网络不可达），需手动确认" —— 常见于 Windows DNS 缓存，参见 [triage/git-bash-compat.md](../../../docs/01-guides/triage/git-bash-compat.md) |
