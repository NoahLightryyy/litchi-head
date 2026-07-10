# Codex Batch Loop 自动化协议

> **用途**：让 ChatGPT / Codex 在新窗口或定时自动化中，按固定流程恢复上下文、选择最高优先级、推进一个原子功能、验证并落文档。

## 触发口令

在新聊天窗口中发送：

```text
启动 litchi-head loop
```

等价短句：

```text
继续 loop
```

只做收尾、不推进新功能：

```text
收尾 loop
```

## Loop 单轮流程

每轮只推进一个可交付的原子任务，不一次开多个坑。

```text
1. 恢复上下文
   - 读 AGENTS.md
   - 读 docs/01-guides/HANDOVER.md
   - 读 docs/04-changelog/logs/README.md 和最新日志
   - 读 docs/01-guides/debt/ROUTER.md
   - git status --short

2. 判断最高优先级
   默认顺序：
   RC-001 结果回调引擎
   → FD-002a 伪产业链修复
   → 交易复盘极简版
   → R4 置信度量化
   → YahooFinanceSource + 美股前端 Tab

3. 拆一个原子任务
   - 明确本轮验收标准
   - 判断轻量模式还是完整模式
   - 如涉及字段/风险/数据源/用户可见文案，先停下来问用户

4. 实现
   - 先扫相关债务
   - 定 Pydantic 契约和函数签名
   - 写/改相关测试
   - 写代码

5. 验证
   - 默认只跑相关测试
   - 跨模块基础设施、契约、conftest、主编排、大 Batch 才跑全量
   - 至少跑 ruff + pyright；优先用 python scripts/check.py

6. 落文档
   - 工作日志必写
   - 债务有新增/关闭才改 DEBT/ROUTER
   - 状态真变化才改 HANDOVER/ROADMAP/README，避免文档 churn
   - 新架构意图写 ADR 或 docs/99-archive/

7. 停下来汇报
   - 完成了什么
   - 验证结果
   - 仍有哪些风险
   - 下一轮建议
```

## 功能完成即收尾保存

Loop 模式下，“做完一个功能”不等于只把代码写完。每个原子功能完成后必须立刻执行一次功能级收尾：

```text
1. 跑验证
   - ruff / pyright
   - 本功能相关测试
   - 需要前端可视化时，再启动页面并用浏览器/Computer Use 验证

2. 写入工作日志
   - 本功能做了什么
   - 改了哪些文件
   - 验证结果
   - 剩余风险和下一步

3. 同步债务
   - 新发现的债务必须登记
   - 修掉的债务必须关闭或更新状态

4. 同步相关文档
   - 状态真变化才更新 HANDOVER / ROADMAP / README
   - 架构/战略变化写 ADR 或 docs/99-archive/

5. 保存当前工作状态
   - 保留清晰 git status
   - 用户要求提交、会话结束、上下文耗尽时执行 git commit
   - 未提交时必须在日志中写清楚哪些文件是本轮产物
```

原则：**每个功能都是一个可恢复检查点**。新窗口接手时，必须能从工作日志和 git status 看懂做到哪、验证到哪、下一步是什么。

## 上下文耗尽续接

当 Codex 判断上下文接近耗尽时，不继续开新功能，立即执行完整收尾：

```text
1. 停止推进新代码
2. 更新当天工作日志，标注“上下文耗尽，需续接”
3. 记录当前任务进度、已改文件、验证结果、未完成事项
4. 更新债务/看板/交接文档（如状态变化）
5. 如当前功能已形成稳定检查点，按项目规则提交
6. 输出新窗口续接口令
```

新窗口续接口令：

```text
启动 litchi-head loop
```

或更明确：

```text
继续 litchi-head loop。先读 AGENTS.md、HANDOVER、最新日志和 git status，从上次上下文耗尽的位置继续。
```

## Computer Use 的边界

`computer-use` 可以用于 Windows GUI 验证，但**不能**用来自动操作 Codex 桌面 App、Codex CLI 或 Codex 扩展来打开新聊天窗口。

原因：Computer Use 的安全规则禁止自动化 Codex 自身 UI。上下文续接应通过以下方式完成：

- 用户打开新窗口后发送 `启动 litchi-head loop`
- 使用 Codex App 自动化创建定时/心跳任务
- 使用线程/自动化工具进行续接，而不是让 Computer Use 点击 Codex UI

`computer-use` 的正确用途：

- 打开浏览器验证本地前端
- 检查页面是否真实渲染
- 验证图表、Tab、错误态、空态、离线态
- 在 UI 交互类功能完成后做桌面级验收

不用于：

- 创建或操作 Codex 聊天窗口
- 跑测试、Git、PowerShell、Python 命令
- 代替 Codex 的代码修改流程

## 自动化层级

### 1. 口令式自动化

适合手动开新窗口继续。用户只发“启动 litchi-head loop”，Codex 自动恢复和推进一轮。

### 2. Codex App 自动化

适合定时、心跳、提醒、周期检查。需要用户指定节奏，例如：

```text
每天上午 9 点启动 litchi-head loop，推进一个原子任务
```

或：

```text
每 2 小时检查 litchi-head loop 是否有未完成收尾
```

这类需求应使用 Codex 自动化工具创建 `cron` 或 `heartbeat`，不要用手写脚本假装后台常驻。

### 3. Computer Use 桌面自动化

`computer-use` 只用于 Windows GUI 场景，不用于代码主循环。

适用场景：
- 启动本地前后端后，打开浏览器做真实页面验证
- 检查桌面应用窗口、浏览器页面、可视化图表是否真的显示
- 必要时点击页面、切换 Tab、观察错误态/空态/离线态

不适用场景：
- 读写项目文件
- 跑测试
- 执行 Git / PowerShell / Python 命令
- 替代 Codex 的代码修改流程

## 测试策略

默认不跑全量。

| 情况 | 测试范围 |
|------|----------|
| 单模块功能 | 相关测试文件 |
| 后端路由 | 对应 `tests/test_backend/` 文件 |
| 数据 Provider | `tests/test_data/` 相关文件 |
| 辩论/回调/风控 | 对应模块测试 |
| 前端组件/API hook | `pnpm build`，必要时加页面验证 |
| 跨模块基础设施 | `python scripts/check.py --full` 或 `make check` |
| Pydantic 契约变更 | 相关上下游测试 + 必要时全量 |
| pytest fixture/conftest | 全量或至少所有受影响测试目录 |
| 用户明确要求 | 按用户要求 |

## 必须停下来问用户的情况

- 功能做什么/不做什么
- 字段设计和数据模型取舍
- 跟钱、风险、仓位、止损相关的默认值
- 数据源变更或新增
- AI 输出格式、置信度定义、错误文案
- 是否创建新长期文档或学习卡片
- 要不要创建 Codex App 定时自动化

## 当前默认下一步

截至 2026-07-10，下一轮 loop 默认从：

```text
RC-001 结果回调引擎
```

开始，除非用户指定其他方向。
