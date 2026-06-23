# 模块 12：质量保障体系（Quality Assurance System）

> 🔒 **实盘级代码防护** — 三类自动化检查 + 两类流程门禁，让漏洞从源头被拦截而非事后追溯。
> **核心原则：检查点到为止，不阻塞开发节奏。**

## 模块定义

在 Claude Code 自动化开发环境中，通过 Hookify 规则、Post-tool hooks、CI 门禁三层，在代码编写→提交→合入全链路拦截常见漏洞。

**职责边界**：
- ✅ 实时拦截沉默吞异常（`except: pass`）
- ✅ 实时拦截缺少异常类型的 `except:`
- ✅ 实时拦截 `.get()` 无默认值
- ✅ 实时提醒添加 Pydantic `Field(ge=/le=)` 约束
- ✅ 实时拦截调试代码（print/console.log/debugger）
- ✅ 实时拦截硬编码密钥
- ✅ 代码修改后自动触发 ruff 检查
- ✅ 代码修改后提醒同步文档/测试
- ✅ 会话结束检查待办事项
- ✅ CI 覆盖率和安全扫描门禁
- ❌ 不替代人工 Code Review
- ❌ 不替代 TDD 流程
- ❌ 不阻塞紧急热修复（提供压制机制）

## 架构：三道防线

```
写入/编辑代码              提交                   合入
───────┬────────    ────────┬──────    ─────────┬────
       │                     │                   │
       ▼                     ▼                   ▼
┌──────────────┐   ┌──────────────┐   ┌──────────────────┐
│  Layer 1:     │   │  Layer 2:     │   │  Layer 3:         │
│  Hookify 规则  │   │  Post-tool     │   │  CI 门禁           │
│  (实时拦截)     │   │  hooks        │   │  (合入屏障)         │
│               │   │  (自动检查)     │   │                   │
│  • block:     │   │  • ruff check  │   │  • Ruff 通过       │
│    except:pass│   │  • type check  │   │  • Pyright 通过     │
│  • warn:      │   │  • test run    │   │  • 测试通过         │
│    bare except│   │  • debt scan   │   │  • 覆盖率 ≥80%     │
│  • remind:    │   │  • doc remind  │   │  • 安全扫描通过      │
│    field const│   │               │   │                   │
└──────┬───────┘   └──────┬───────┘   └────────┬─────────┘
       │                   │                     │
       ▼                   ▼                     ▼
  开发时反馈           提交前屏障              合入门禁
```

### Layer 1：Hookify 规则（实时）

在每次 `Write`/`Edit` 工具调用时实时检测，立即反馈。

| 规则 | 类型 | 拦截模式 |
|:-----|:----:|:---------|
| `except-pass-blocker` | ⛔ block | `except.*:.*pass` — 沉默吞异常 |
| `bare-except-warning` | ⚠️ warn | `except:` 不带异常类型 |
| `get-no-default` | ⚠️ warn | `.get(` 缺少默认值参数（Python上下文） |
| `pydantic-field-constraints` | 💡 remind | 检测 `BaseModel` 新字段缺少 `Field()` 约束 |
| `debug-code-blocker` | ⛔ block | `print(`, `debugger`, `console.log(` |
| `hardcoded-secret` | ⚠️ warn | `api_key`, `password`, `secret` 等硬编码 |
| `test-after-code-change` | 💡 remind | 修改 `.py` 文件后提醒写/跑测试 |

### Layer 2：Post-tool Hooks（自动）

在 `Write`/`Edit` 后自动执行检查。

```yaml
hooks:
  PostToolUse:
    - matcher: file_write_edit  # 修改 Python 文件后
      actions:
        - bash: ruff check --select E,W,F <changed_files>
    - matcher: session_stop      # 会话结束
      actions:
        - bash: python scripts/check.py --full
```

### Layer 3：CI 门禁（屏障）

在 `main` 分支合入前执行。

| 检查 | 当前 | 目标 |
|:-----|:----:|:----:|
| Ruff lint ✅ | 已配 | — |
| Pyright type ✅ | 已配 | — |
| Pytest ✅ | 已配 | — |
| Coverage 门禁 ❌ | 未配 | ≥80% |
| 安全扫描 ❌ | 未配 | bandit + safety |
| 文档同步 ❌ | 未配 | git diff 检测 docs/ 不同步 |

## Hookify 规则明细

### R001 — except-pass-blocker

```yaml
name: except-pass-blocker
event: file
action: block  # 写代码时直接阻止
pattern: "except(\\s+\\w+)?\\s*:\\s*\\n\\s*pass\\s*$"
```

**触发场景**：写 `try: ... except: pass` 或 `except Exception: pass`。
**压制方法**：在 pass 前加注释 `# noqa: silence` 说明为什么可以沉默。

### R002 — bare-except-warning

```yaml
name: bare-except-warning
event: file
action: warn
pattern: "except\\s*:"
```

**触发场景**：写 `except:` 不带异常类型。
**为什么**：`except:` 会捕获 `SystemExit`、`KeyboardInterrupt` 等，永远不应该出现在生产代码。

### R003 — get-no-default

```yaml
name: get-no-default
event: file
action: warn
pattern: "\\.get\\(\\s*['\"]\\w+['\"]\\s*\\)"
```

**触发场景**：`dict.get("key")` 不带默认值，返回 None 未处理。
**例外**：`Field(default_factory=...)` 模式不受影响。

### R004 — pydantic-field-constraints

```yaml
name: pydantic-field-constraints
event: file
action: warn
pattern: "(?s)class\\s+\\w+\\(BaseModel\\)[\\s\\S]*?:(\\s*\\w+\\s*:)"
```

**触发场景**：新增 `BaseModel` 子类，字段上缺少 `Field(ge=/le=)` 约束。
**提示内容**：输出约束速查表。

### R005 — debug-code-blocker

```yaml
name: debug-code-blocker
event: file
action: block
pattern: "\\bprint\\(|\\blogger\\.info\\(|console\\.log\\(|debugger\\b"
```

**触发场景**：提交生产代码时插入 `print()`/`console.log()`/`debugger`。
**压制方法**：添加注释 `# debug` 在同一行。

### R006 — hardcoded-secret

```yaml
name: hardcoded-secret
event: file
action: warn
pattern: "(?i)(api_key|api_secret|password|token|secret)\\s*[=:]\\s*['\"][^'\"]{8,}['\"]"
```

**触发场景**：代码中硬编码 API 密钥/密码/Token。
**例外**：测试文件中的 mock 值。

### R007 — test-after-code-change

```yaml
name: test-after-code-change
event: file
action: warn
pattern: "\\.py$"
```

**触发场景**：修改了 `.py` 源文件。
**提示内容**：提醒是否需要更新测试或文档。

### R008 — logger-exception-blocker

```yaml
name: logger-exception-blocker
event: file
action: block  # 写 except 块时检查是否包含日志调用
pattern: "except\\s+(\\w+\\s+)*as\\s+\\w+\\s*:[^}]*?(?=\\n(?!\\s*logger\\.(exception|warning|error|info)\\())"
```

**触发场景**：写 `except ... as e:` 但块内没有 `logger.exception()` / `logger.warning()`。
**压制方法**：在 except 块内添加日志调用或注释 `# R008: suppress`。

### R009 — type-ignore-comment

```yaml
name: type-ignore-comment
event: file
action: warn
pattern: "# type: ignore(?!\\[)"
```

**触发场景**：新增 `# type: ignore` 不带具体错误代码（如 `# type: ignore[arg-type]`）。
**为什么**：宽泛的 `type: ignore` 会掩盖所有类型错误，指定错误代码可以精确压制预期的问题。

## Post-tool Hooks 配置

见 [HOOKS.md](HOOKS.md) 完整参考。

## CI 门禁目标

### 短期（本轮实现）
- [x] Ruff lint ✅
- [x] Pyright type check ✅
- [x] Pytest ✅

### 中期（Phase R 内）
- [ ] Coverage 门禁：`coverage run --source=src -m pytest && coverage report --fail-under=80`
- [ ] 安全扫描：`bandit -r src/ -c pyproject.toml`
- [ ] 依赖漏洞：`safety check`

### 长期
- [ ] 文档同步检测：对比 git diff 中的 `src/` 和 `docs/` 变更范围
- [ ] 自动 Code Review agent
- [ ] 性能回归检测

## 维护指南

### 新增一条 Hookify 规则

1. 在 `.claude/hookify.*.local.md` 中添加规则
2. 在本文档「Hookify 规则明细」中添加条目
3. 更新 [HOOKS.md](HOOKS.md) 索引
4. 通知团队（写在工作日志中）

### 规则分级原则

| 级别 | 标签 | 含义 | 使用场景 |
|:-----|:----:|:-----|:---------|
| ⛔ Block | `action: block` | 阻止写入 | 数据丢失/安全漏洞风险 |
| ⚠️ Warn | `action: warn` | 显示警告 | 违反最佳实践，可压制 |
| 💡 Remind | `action: warn` | 输出提示 | 可能遗忘的流程（测试/文档） |

### 压制机制

当某条规则确实不适用于当前场景时：
- **Block 规则**：在同一行添加注释 `# noqa: <规则名>` 可以绕过
- **Warn 规则**：确认后继续，规则只提示不阻止

## 与其他模块的关系

| 模块 | 关系 |
|:-----|:-----|
| 所有 `src/` 模块 | 被检查对象 |
| `docs/` 全目录 | 五同步检查对象（含引用清理） |
| `.github/workflows/ci.yml` | Layer 3 载体 |
| `pyproject.toml` | 工具配置托管 |
| `.claude/settings.json` | hooks 配置托管 |

---

**相关文档**：
- [Hookify 规则参考](HOOKS.md)
- [学习卡片：Hookify 规则与 Claude Code Hooks](../../learning/09-hookify-rules.md)
- [Workflow 指南](../../01-guides/WORKFLOW.md)
- [CI 配置](../../../.github/workflows/ci.yml)
