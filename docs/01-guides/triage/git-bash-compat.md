# 🌐 Git Bash on Windows 工具链兼容性

> Git Bash 是 POSIX 模拟层，与 Windows 原生工具链有 5 个常见不兼容模式。
> 任何跨工具链命令（curl → Python → cmd）都可能踩这些坑。

---

## 速查表

| # | 问题 | 诊断信号 | 修复 |
|:-:|:-----|:---------|:-----|
| 1 | **DNS 缓存过时** | `curl` exit 49 / `Could not resolve host` | 先 `cmd.exe /c ipconfig /flushdns` 再试 |
| 2 | **Windows 命令乱码** | `ipconfig` 输出 `����` | 用 `cmd.exe /c` 包裹，或在 Git Bash 中先 `chcp 936` |
| 3 | **`python3` Store 存根** | `python3` exit 49 / 无输出 | 用 `python` 或 `py -3` 替代 `python3` |
| 4 | **`/tmp/` 路径不存在** | `No such file or directory: '/tmp/xxx'` | 用 `$TEMP` 环境变量指向 Windows 原生临时目录 |
| 5 | **UTF-8 文件被 GBK 解码** | Python `UnicodeDecodeError: 'gbk' can't decode byte` | `open()` 加 `encoding='utf-8'` |

---

## 1. DNS 缓存过时

### 现象

```bash
$ curl -s "https://api.github.com/..."
# → exit code 49, 无输出
```

### 原因

Windows 会缓存 DNS 解析结果。当网络环境变化（切换 WiFi、VPN 重连、代理切换）后，缓存中的旧记录导致域名无法解析。curl exit 49 在 Windows 上表示 `CURLE_COULDNT_CONNECT`。

### 修复

```bash
# ✅ 正确：用 cmd.exe /c 包裹 Windows 原生命令
cmd.exe /c ipconfig /flushdns

# ❌ 错误：直接在 Git Bash 跑 ipconfig
ipconfig /flushdns  # 输出乱码或失败
```

### 验证

```bash
curl -s --max-time 10 "https://api.github.com" > /dev/null && echo "✅ DNS OK" || echo "❌ DNS FAIL"
```

---

## 2. 命令输出乱码 (GBK vs UTF-8)

### 现象

```bash
$ ipconfig /flushdns
# → 输出: ����: �޷�ʶ...
```

### 原因

Git Bash 终端默认 UTF-8 编码，但 Windows 原生命令（`ipconfig`、`chcp`、`netstat` 等）输出 GBK 编码。直接运行会在终端显示乱码。

### 修复

```bash
# 方案 A：用 cmd.exe /c 包裹（推荐）
cmd.exe /c "ipconfig /flushdns"

# 方案 B：临时切换编码
chcp 936 > /dev/null && ipconfig /flushdns
```

---

## 3. `python3` 被 Windows Store 存根拦截

### 现象

```bash
$ python3 -c "print('hello')"
# → exit code 49, 无输出
# → 或弹 Windows Store 窗口
```

### 原因

Windows 10/11 默认安装的 `python3.exe` / `python.exe` 是 Microsoft Store 存根（stub），位于 `%LOCALAPPDATA%\Microsoft\WindowsApps\`。这个存根 exit code 总是 49（`ERROR_STORE_STUB`），无法执行任何 Python 代码。

### 修复

```bash
# ✅ 正确：用 Python Launcher
py -3 -c "print('hello')"

# ✅ 或者用完整路径
/c/Python314/python -c "print('hello')"  # Git Bash 风格

# ❌ 错误：依赖 python3
python3 -c "print('hello')"  # 可能触发行星存根
```

### 检测方法

```bash
# 检查实际运行的 python3 路径
which python3
# → /c/Users/xxx/AppData/Local/Microsoft/WindowsApps/python3  ← 就是存根！
# → /c/Python314/python3                                              ← 正常安装
```

---

## 4. `/tmp/` 路径不可用

### 现象

```bash
$ curl -s "https://..." -o /tmp/data.json
$ python3 -c "open('/tmp/data.json')"
# → FileNotFoundError: /tmp/data.json
```

### 原因

Git Bash 的 `/tmp/` 在 **进程级别** 模拟，并非 Windows 原生路径。在某些 Bash 调用上下文中（尤其是 Claude Code 的子进程），`/tmp/` 指向不存在或不可写的目录。

### 修复

```bash
# ✅ 正确：用 Windows TEMP 环境变量
curl -s "https://..." -o "$TEMP/data.json"

# ✅ Python 中也能用
py -3 -c "
import tempfile, json
# 或用 os.environ['TEMP']
print(tempfile.gettempdir())  # → C:\Users\rog\AppData\Local\Temp
"

# ❌ 错误：硬编码 /tmp/
curl -s "https://..." -o /tmp/data.json
```

---

## 5. UTF-8 JSON 被 GBK 解码

### 现象

```bash
$ py -3 -c "
with open('data.json') as f:
    json.load(f)
# → UnicodeDecodeError: 'gbk' codec can't decode byte 0xa2 in position 328
"
```

### 原因

Windows 中文版 Python 的默认编码是 **GBK**（不是 UTF-8）。当你 `open()` 一个 UTF-8 编码的 JSON 文件（如 GitHub API 响应）时，Python 用 GBK 解码，遇到非 ASCII 字符就爆炸。

### 修复

```python
# ✅ 正确：显式指定 encoding
with open('data.json', encoding='utf-8') as f:
    json.load(f)

# ❌ 错误：依赖默认编码（Windows 上 = GBK）
with open('data.json') as f:  # 炸！
    json.load(f)
```

---

## 通用原则：跨工具链命令的 5 条规则

> 当命令需要从 Git Bash 调用 Python + 网络 + 文件时，遵守以下优先级：

1. **首选纯 Python** — 用 `urllib.request` 替代 `curl`，消除对 curl 的依赖
2. **用 `py -3` 而非 `python3`** — 避免 Store 存根
3. **显式 `encoding='utf-8'`** — 所有文件操作都加，不在 Windows 上依赖默认编码
4. **用 `$TEMP` 而非 `/tmp/`** — 始终指向 Windows 原生临时目录
5. **包裹 Windows 原生命令** — 用 `cmd.exe /c` 运行 ipconfig/netstat 等

### 推荐模式：自包含 Python 单行

```python
# 替代 curl → file → python3 → file 的脆弱链条
py -3 -c "
import json, urllib.request
try:
    req = urllib.request.Request('URL', headers={'User-Agent': '...'})
    with urllib.request.urlopen(req, timeout=10) as r:
        data = json.loads(r.read().decode('utf-8'))
    # ... 处理 data ...
except Exception as e:
    print(f'ERROR: {e}')
"
```

这个模式：
- 无外部命令依赖（不需要 curl）
- 无中间文件（不在 `/tmp/` 写文件）
- 显式 UTF-8 解码
- 统一错误处理

---

## 关系图谱

```
┌──────────────┐     ┌──────────────────┐
│  Git Bash    │────→│  #1 DNS 过时     │──→ curl exit 49
│  (POSIX 层)  │     │  #2 乱码输出     │──→ ipconfig 不可读
│              │     │  #4 /tmp/ 失效   │──→ 文件操作失败
├──────────────┤     └──────────────────┘
│  Python      │────→│  #3 Store 存根   │──→ python3 exit 49
│  (解释器层)  │     │  #5 GBK vs UTF-8 │──→ JSON 解码失败
└──────────────┘     └──────────────────┘
```

## 相关文档

- [🐍 Python 运行时](python-runtime.md) — Python 特有（torch crash、pydantic 兼容）
- [🌐 Git 网络](git-network.md) — 纯网络问题（代理、SSH、国内镜像）

---

> **最后更新**：2026-06-22 | 首次编写，覆盖 Git Bash on Windows 5 个常见不兼容模式
