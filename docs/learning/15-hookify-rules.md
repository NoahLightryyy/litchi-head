# 09 Hookify 规则与 Claude Code Hooks

## 一句话

> **Hookify 规则是 Claude Code 内置的"代码护栏"** — 在你写代码的瞬间检测模式并拦截/警告，让漏洞在产生的那一刻就被发现，而不是等到 Code Review 或上线后。

---

## 为什么需要它？

### 问题场景

想象一下这个流程：

```
写代码 → 提交 → CI 跑 5 分钟 → 合入 → 上线
```

最常见的漏洞发生在第一步。而且有个残酷的事实：

1. **你的注意力在"实现功能"上**，不在"检查错误"上
2. **Code Review 靠自觉** — 项目忙的时候直接合入
3. **CI 属于远程发现** — 写完等 5 分钟才知道有问题
4. **沉默错误最危险** — `except: pass` 写了，测试全绿，但线上静默失败了

你写过这样的代码吗？

```python
try:
    result = await call_external_api()
    return result
except:  # 没写 Exception 类型！
    pass   # 出错了？无所谓
```

这段代码会静默吞掉 `KeyboardInterrupt`（Ctrl+C）、`SystemExit`，让进程无法正常终止。

### 它的解法

Hookify 规则在 **你写完代码的那一刻**、**Write/Edit 工具返回之前** 检测到问题：

```
你写入文件 → Hookify 检查 → 匹配规则 → ⛔ 阻止/⚠️ 警告 → 你修复 → 写入成功
                                                                    ↓
                                                             （如果误报，加 # noqa）
```

三段式防护：

1. **⛔ Block** — 直接阻止写入（比如 `except.*: pass`，数据安全风险）
2. **⚠️ Warn** — 显示警告，你可以选择继续（比如缺少默认值的 `.get()`）
3. **💡 Remind** — 善意提醒（比如改完代码提醒写测试）

---

## 项目里的真实代码

打开 `.claude/hookify.except-pass.local.md`：

```markdown
---
name: except-pass-blocker
enabled: true
event: file
action: block
pattern: "except(\\s+\\w+)?\\s*:\\s*\\n\\s*pass\\s*$"
---

⛔ **沉默吞异常检测**

你写了一段 `except ...: pass`，异常信息被完全吞掉了。
这意味着程序出错时没有任何人知道。

**怎么修**：
1. 加 `logger.exception(...)` 记录异常
2. 或者 `raise` 重新抛出
3. 确定要沉默？在 `pass` 前加 `# noqa: silence` 说明原因
```

当你在编辑器中写入：

```python
try:
    process(data)
except KeyError:
    pass
```

Hookify 会立即阻挡，并显示上面的提示。

---

再看一个实用性极强的 R003 `.get()` 无默认值检测：

打开 `.claude/hookify.get-no-default.local.md`：

```markdown
---
name: get-no-default
enabled: true
event: file
action: warn
pattern: "\\.get\\(\\s*['\"]\\w+['\"]\\s*\\)"
---

⚠️ **.get() 没有提供默认值**

`dict.get("key")` 在 key 不存在时返回 None。
如果后续代码假设一定有值，就会在奇怪的地方炸。

**建议**: `dict.get("key", 0)` 或 `dict.get("key", [])` 或 `dict.get("key", "")`
```

---

## 和 CI 门禁有什么不同？

| 对比 | Hookify 规则 | CI 门禁 |
|:-----|:------------|:--------|
| 发现时间 | **写入瞬间**（<1秒） | 提交后（5-10分钟） |
| 反馈位置 | 编辑器内 | 远程 CI 日志 |
| 网络依赖 | ❌ 不需要 | ✅ 需要 |
| 可压制 | ✅ `# noqa` 注释 | ❌ 必须改 |
| 适合检测 | 局部模式（语法/模式） | 全局属性（覆盖率/安全） |
| 误报影响 | 低（开发时压制） | 高（阻塞合入） |

**正确姿势**：Hookify 拦截简单明确的模式错误（80% 的常见问题），CI 拦截需要全局分析的复杂问题（20%）。

---

## 你会怎么用

1. **日常开发**：Hookify 规则自动生效，你几乎感觉不到它们的存在
2. **收到警告**：看一眼提示，改掉就好
3. **误报**：加 `# noqa: 规则名` 跳过
4. **想加新规则**：发现一种频繁出现的错误模式 → 写一条规则 → 从此不会再犯

---

## 面试会怎么问

> **Q: 如何在不依赖 Code Review 的情况下保证代码质量？**
>
> A: 在开发工具链中嵌入自动化检查。最有效的是三层防御：
> 1. **写入时拦截**（Hookify/IDE 插件）— 即时反馈，零成本修复
> 2. **提交前检查**（pre-commit hooks）— 本地运行，快速迭代
> 3. **合入门禁**（CI）— 最终屏障，跑不过不能合入
>
> 关键是把"检查"嵌入到流程中，而不是依赖人的自觉性。

---

## 自己试试（5 分钟）

1. 打开项目 `.claude/` 目录，看看有哪些 `hookify.*.local.md` 文件
2. 打开一个，理解它的 `pattern` 正则做了什么
3. 故意在某个 `.py` 文件里写 `try:\n    pass\nexcept:\n    pass`，看看会发生什么
4. （思考题）你能想到项目里还有哪些**反复出现的错误模式**可以写一条规则？

---

**上一篇：[08 类型提示与 Pyright](08-type-hints-pyright.md)**
**下一篇：—**
