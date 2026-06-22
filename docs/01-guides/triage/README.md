# 🚑 技术急救手册

> **出问题先翻这里。** 扫一眼症状速查表，定位到对应分类文件。
>
> 新问题解决了 → 追加到对应文件，补充新行到速查表。
> 不费事，但下次节省 10 分钟。

---

## 🏃 症状速查（扫这里！）

你看到什么报错 → 看这列 | → 去这个分类
:---|:---|:---
`Recv failure: Connection was reset` | git push 网络问题 | [🌐 Git 网络](git-network.md)
`Could not connect to server` | git push 连不上 | [🌐 Git 网络](git-network.md)
`Failed to connect to github.com port 443` | git push 超时 | [🌐 Git 网络](git-network.md)
`fatal: unable to access` | 网络问题 | [🌐 Git 网络](git-network.md)
`ruff` 报 `F841` / `E501` / `F401` / `E402` / `F541` | 代码风格/导入问题 | [🔬 CI 健康](ci-health.md)
`pyright` 报 `reportCallIssue` / `reportAttributeAccessIssue` | 类型错误 | [🔬 CI 健康](ci-health.md) + [🧪 类型检查](type-checking.md)
`No parameter named "stock_codes"` | adata API 参数名不对 | [📊 adata API](adata-api.md)
`'Info' object has no attribute 'all_industry'` | adata 版本属性缺失 | [📊 adata API](adata-api.md)
`Windows fatal exception: access violation` | torch 导入 crash | [🐍 Python 运行时](python-runtime.md)
`Access violation reading location` | Windows + torch | [🐍 Python 运行时](python-runtime.md)
`Core Pydantic V1 functionality isn't compatible` | Python 3.14 兼容性 | [🐍 Python 运行时](python-runtime.md)
`Cannot access attribute "xxx"` - Pyright | 属性不存在 | [🧪 类型检查](type-checking.md)
`No parameter named "xxx"` - Pyright | 参数名不匹配 | [🧪 类型检查](type-checking.md)
`row["col"]` Pyright type mismatch | pandas iterrows | [🧪 类型检查](type-checking.md)
`except:pass` | 静默吞异常 | 已修 → 见 `docs/04-changelog/` Phase R
`exit code 49` + 无输出 | curl 网络错误 | [🌐 Git Bash 兼容](git-bash-compat.md) — DNS 过时
`exit code 49` + 无输出 | python3 命令 | [🌐 Git Bash 兼容](git-bash-compat.md) — Store 存根
`UnicodeDecodeError: 'gbk' can't decode` | 文件编码 | [🌐 Git Bash 兼容](git-bash-compat.md) — UTF-8 vs GBK
`No such file or directory: '/tmp/...'` | Git Bash /tmp/ 无效 | [🌐 Git Bash 兼容](git-bash-compat.md) — 路径问题
`/flushdns` 输出乱码 / `����` | Git Bash 编码 | [🌐 Git Bash 兼容](git-bash-compat.md) — 乱码

---

## 分类索引

| 分类 | 文件 | 覆盖范围 |
|:----|:-----|:---------|
| 🌐 Git 网络 | [git-network.md](git-network.md) | DNS/代理/SSH/国内备选 |
| 🔬 CI 健康 | [ci-health.md](ci-health.md) | Ruff/Pyright/Pytest 修复套路 |
| 📊 adata API | [adata-api.md](adata-api.md) | 参数名/属性缺失/版本兼容 |
| 🐍 Python 运行时 | [python-runtime.md](python-runtime.md) | Windows torch/惰性导入/编码 |
| 🧪 类型检查 | [type-checking.md](type-checking.md) | pandas/import 位置/Pydantic |
| 🌐 Git Bash 兼容 | [git-bash-compat.md](git-bash-compat.md) | DNS/cURL/Python3/编码/路径交叉问题 |

---

## AI 查询机制

CLAUDE.md 已加入规则（见「核心规则」第 9 条）：

> **遇技术报错先查 `docs/01-guides/triage/`** — 按症状匹配分类，定位到对应文件再读。

所以下次报错，AI 会自动来这查。

---

## 贡献规则

- 解决一个问题后，如果 **30 秒内能想到"以后可能还会碰到"** → 追加到对应文件
- 具体加什么：
  - 症状速查表加一行（你看到的报错信息）
  - 对应的修复代码片段
- 如果现有分类都不匹配 → 新建 `.md` 文件，更新上面的症状速查表
