# 19 Windows 开发环境调试指南 — Git Bash 5 大兼容坑

## 一句话

> Python 项目在 Windows/Git Bash 环境下开发，工具链（curl → python3 → /tmp/ → 编码）之间有 5 个常见不兼容模式。自包含 Python 命令比多步 Shell 管道稳 10 倍。

---

## 为什么需要它？

### 问题场景

你在 Claude Code 里跑一条看起来很简单的命令：

```bash
curl -s "https://api.github.com/..." -o /tmp/data.json
python3 -c "import json; json.load(open('/tmp/data.json'))"
```

结果五花八门：
- `curl` exit 49 — 无输出
- `python3` exit 49 — 无输出
- `FileNotFoundError: /tmp/data.json` — 明明刚 curl 成功
- `UnicodeDecodeError: 'gbk' can't decode byte` — 内容乱码
- `ipconfig /flushdns` 全是 `����` 乱码

每步排查 2-5 分钟，一条 5 秒的命令变成 15 分钟的痛苦。

### 根因：5 个独立问题叠加

所有问题都是 **Git Bash（POSIX 模拟层）× Windows（原生层）**之间的翻译错误：

| # | 问题 | 原因 |
|:-:|:-----|:------|
| 1 | DNS 缓存过时 | Windows DNS 缓存未刷新 → curl exit 49 |
| 2 | 命令乱码 | Git Bash 用 UTF-8，Windows 原生命令输出 GBK |
| 3 | python3 存根 | Windows Store `python3.exe` 总是 exit 49 |
| 4 | /tmp/ 不存在 | Git Bash 的 `/tmp/` 在 Claude Code 子进程里可能不可用 |
| 5 | GBK 解码 | Windows Python `open()` 默认 GBK，API JSON 是 UTF-8 |

### 解法：自包含 Python 命令

用单条 `py -3 -c` 替代 `curl → file → python3 → file` 链条：

```bash
# ❌ 脆弱的 4 步链
curl -s "URL" -o /tmp/data.json
python3 -c "..."           # 踩 #3 / #4 / #5

# ✅ 自包含 Python（1 步，没有外部依赖）
py -3 -c "
import json, urllib.request
req = urllib.request.Request('URL', headers={'User-Agent': '...'})
with urllib.request.urlopen(req, timeout=10) as r:
    data = json.loads(r.read().decode('utf-8'))
# ... 直接用 data ...
"
```

优势：
- **零外部命令** — 不需要 curl（避 #1）
- **零中间文件** — 不需要写 /tmp/（避 #4）
- **显式 UTF-8** — `r.read().decode('utf-8')`（避 #5）
- **用 `py -3`** — 不是 `python3`（避 #3）
- **统一 try/except** — 网络错误优雅处理，不再 exit 49 让人摸不着头脑

---

## 项目里的真实代码

打开 `.claude/skills/resume-session/skill.md`（第 58-75 行）：

```python
# 之前的 resume-session CI 检查（脆弱版）
curl -s "https://api.github.com/repos/NoahLightryyy/litchi-head/actions/runs?per_page=5" -o /tmp/ci_runs.json && python3 -c "
import json
with open('/tmp/ci_runs.json') as f:   # ← 踩 #4 /tmp/ + #5 GBK
    data = json.load(f)
"

# 之后的 resume-session CI 检查（稳健版）
py -3 -c "
import json, urllib.request
try:
    URL = 'https://api.github.com/repos/NoahLightryyy/litchi-head/actions/runs?per_page=5'
    req = urllib.request.Request(URL, headers={'User-Agent': 'litchi-head/1.0'})
    with urllib.request.urlopen(req, timeout=10) as resp:
        data = json.loads(resp.read().decode('utf-8'))
    # ...安全处理 data...
except Exception as e:
    print(f'NETWORK_ERROR: {e}')  # 优雅处理，不 exit 49
"
```

**解读**：之前这条命令踩了 3 个兼容坑（curl exit 49 →排查 2min，/tmp/ 找不到→排查 2min，GBK 解码→排查 2min）。改成自包含 Python 后，**0 个命令级错误点** + 网络不可达的报错信息直接可读。

---

## 5 条通用原则（记这 5 条就够了）

当命令需要从 Git Bash 调用 Python + 网络 + 文件时：

1. **首选纯 Python** — `urllib.request` 替代 `curl`，消除对 curl 的依赖
2. **用 `py -3` 而非 `python3`** — 避免 Windows Store 存根
3. **显式 `encoding='utf-8'`** — 所有文件操作都加，别依赖默认编码
4. **用 `$TEMP` 而非 `/tmp/`** — Windows 原生临时目录永远存在
5. **包 Windows 原生命令** — `cmd.exe /c ipconfig` 而非直接 `ipconfig`

---

## 和纯 Linux 开发有什么不同

| 对比 | Linux / macOS | Windows + Git Bash |
|:-----|:--------------|:--------------------|
| `/tmp/` | ✅ 永久存在 | ❌ 子进程可能不可用 |
| `python3` | ✅ 真实解释器 | ❌ Windows Store 存根可能拦截 |
| 默认编码 | ✅ UTF-8 | ❌ GBK（中文 Windows） |
| DNS 缓存 | 系统自动 | 需手动 `ipconfig /flushdns` |

---

## 面试会怎么问

> **Q: 你在 Windows 上做 Python 开发遇到过什么坑？**
> 
> A: 主要在工具链兼容性上——Git Bash 是 POSIX 模拟层，而 Windows 原生命令（ipconfig）、文件路径（/tmp/）、Python 解释器路径（Windows Store 存根）和默认编码（GBK vs UTF-8）四个层面都有坑。核心解决思路是：用自包含 Python 命令替代跨工具链的 Shell 管道链，一步到位，别用中间文件。

---

## 自己试试（5 分钟）

1. 打开 `.claude/skills/resume-session/skill.md` 看第 58-75 行的 CI 检查命令
2. 对比之前（注释掉的旧版本）和现在（自包含 Python 版本）的区别
3. 思考题：如果你需要在 GitHub API 返回数据后做更多处理（比如只取失败的任务），是在 Python 里加循环好，还是用 `jq` 过滤好？（答案：全放 Python 里，避免增加工具链依赖）

---

**上一篇：[FastAPI 路由测试 — TestClient + MockCollector](18-fastapi-testclient-mockcollector.md)**

---

> **更新**：2026-06-22 | TD-039 开发过程中踩坑后固化的 Windows 开发环境通用指南，与 `docs/01-guides/triage/git-bash-compat.md` 配合使用。
