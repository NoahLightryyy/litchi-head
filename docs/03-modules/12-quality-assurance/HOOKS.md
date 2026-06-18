# Hookify 规则 & Claude Code Hooks 参考

> **工程护栏** — 所有规则和钩子的完整索引，用于日常开发和故障排查。

---

## 一、Hookify 规则索引

| ID | 名称 | 类型 | 文件 | 说明 |
|:---|:-----|:----:|:-----|:-----|
| R001 | `except-pass-blocker` | ⛔ block | `.claude/hookify.except-pass.local.md` | `except.*: pass` → 直接阻止 |
| R002 | `bare-except-warning` | ⚠️ warn | `.claude/hookify.bare-except.local.md` | `except:` 不带异常类型 |
| R003 | `get-no-default` | ⚠️ warn | `.claude/hookify.get-no-default.local.md` | `.get()` 无默认值 |
| R004 | `pydantic-field-constraints` | 💡 remind | `.claude/hookify.pydantic-constraints.local.md` | BaseModel 字段缺少 Field() |
| R005 | `debug-code-blocker` | ⛔ block | `.claude/hookify.debug-code.local.md` | print/console.log/debugger |
| R006 | `hardcoded-secret` | ⚠️ warn | `.claude/hookify.hardcoded-secret.local.md` | API key/password 硬编码 |
| R007 | `test-after-code-change` | 💡 remind | `.claude/hookify.test-after-edit.local.md` | 修改代码后提醒测试 |

### 规则文件路径

所有规则文件位于项目根目录 `.claude/` 下，命名格式为 `hookify.<动词>-<对象>.local.md`。

### 快速启用/禁用

```bash
# 列出所有规则
/hookify-list

# 交互式开关
/hookify-configure
```

### 规则调试

```bash
# 测试一个模式是否匹配
python3 -c "import re; print(re.search(r'你的_模式', '测试_文本'))"
```

---

## 二、Claude Code Hooks 配置

### PostToolUse 钩子

作用于 `Write` 或 `Edit` Python 文件后。

**配置位置**：`.claude/settings.json` + `settings.local.json`

```json
{
  "hooks": {
    "PostToolUse": {
      "python-lint": {
        "matcher": {
          "file_pattern": "\\.py$"
        },
        "exec": [
          "ruff", "check", "--select", "E,W,F", "--fix", "{file}"
        ]
      },
      "test-reminder": {
        "matcher": {
          "file_pattern": "\\.py$",
          "content_pattern": "(def |class )"
        },
        "exec": [
          "echo", "[hook] 代码已修改，记得跑测试: python -m pytest tests/ -x --tb=short"
        ]
      }
    }
  }
}
```

### PreToolUse 钩子

作用于 `Bash` 执行前。用于防止危险命令。

```json
{
  "hooks": {
    "PreToolUse": {
      "protect-prod": {
        "matcher": {
          "command_pattern": "(rm -rf /|> /dev/sda|dd if=)"
        },
        "action": "block"
      }
    }
  }
}
```

### Stop 钩子

会话结束时执行。

```json
{
  "hooks": {
    "Stop": {
      "debt-check": {
        "exec": [
          "echo", "[hook] 会话结束前检查：更新了债务日志吗？文档同步了吗？"
        ]
      }
    }
  }
}
```

### 钩子类型对照表

| 钩子类型 | 触发时机 | 参数 | 返回值 |
|:---------|:---------|:-----|:-------|
| `PreToolUse` | 工具执行前 | `command`, `file_path`, `new_text`, `user_prompt` | 允许/拒绝/修改 |
| `PostToolUse` | 工具执行后 | `command`, `exit_code`, `stdout`, `stderr` | 可追加输出 |
| `Stop` | 会话结束时 | 无 | 显示消息 |

---

## 三、故障排查

### 规则不触发

1. 确认规则文件在 `.claude/hookify.*.local.md`
2. 确认文件 `enabled: true`
3. 确认 `event` 字段正确（file/bash/stop/prompt）
4. 测试正则：`python3 -c "import re; print(re.search(r'模式', '测试文本'))"`
5. 检查是否被 `.gitignore` 忽略

### Hook 配置不生效

1. 检查 `~/.claude/settings.json` 或项目 `.claude/settings.json`
2. 检查 JSON 格式（可以用 `python -m json.tool` 验证）
3. 重启 Claude Code 会话
4. 查看 Claude Code 输出日志

### 误报处理

1. 对于 Block 规则：在同一行添加 `# noqa: <规则名>` 注释绕过
2. 对于 Warn 规则：阅读提示后继续，规则只展示不阻止
3. 提交 issue 到项目文档，标记为规则误报

---

## 四、CI 门禁配置

> 见 [CI 配置文件](../../../.github/workflows/ci.yml)

```yaml
# 待添加（Phase R 目标）
- name: Coverage gate
  run: |
    coverage run --source=src -m pytest
    coverage report --fail-under=80

- name: Security scan
  run: |
    pip install bandit safety
    bandit -r src/ -c pyproject.toml
    safety check
```

---

**参见**：[SPEC.md](SPEC.md) | [学习卡片：Hookify 规则](../../learning/09-hookify-rules.md) | [Claude Code Hooks 官方文档](https://docs.anthropic.com/en/docs/claude-code/settings#hooks)
