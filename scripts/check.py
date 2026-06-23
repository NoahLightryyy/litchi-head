#!/usr/bin/env python3
"""check.py — 本地 CI 一键检查

替代 `make check`，跨平台（Windows/Linux/macOS）。
功能：
  1. ruff 代码风格检查
  2. pyright 类型检查（src/）
  3. 按变更范围智能选择测试子集

用法：
  python scripts/check.py              # 检测变更范围 + 按需跑测试
  python scripts/check.py --full       # 强制跑全部测试（-m "not slow"）
  python scripts/check.py --diff main  # 跟 main 分支比变更范围

退出码：0 全通过，1 有失败
"""

import argparse
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

# ── 源码目录 → 测试目录映射 ─────────────────────────────
# None = 该模块无独立测试目录，归入全量子集
SRC_TO_TEST: dict[str, str | None] = {
    "src/utils":    "tests/test_utils",
    "src/data":     "tests/test_data",
    "src/debate":   "tests/test_debate",
    "src/agents":   "tests/test_agents",
    "src/memory":   "tests/test_memory",
    "src/risk":     "tests/test_risk",
    "src/trader":   None,
    "src/backtest": "tests/test_backtest",
    "src/core":     "tests/test_agents",  # core 被 agents 使用
    "backend":      "tests/test_backend",
}
# 不被映射覆盖的变更 -> 触发全量子集


def _s(text: str) -> str:
    """安全输出：抑制 Windows GBK 终端的 emoji/Unicode 错误。"""
    try:
        print(text)
    except UnicodeEncodeError:
        safe = text.encode("ascii", errors="replace").decode("ascii")
        print(safe)


def _bool_symbol(ok: bool) -> str:
    """返回状态符号（安全编码）。"""
    return "[PASS]" if ok else "[FAIL]"


def git_diff(target: str = "HEAD") -> set[str]:
    """返回当前分支相对 target 的变更文件路径集合（相对 REPO_ROOT）。"""
    result = subprocess.run(
        ["git", "diff", "--name-only", target],
        capture_output=True, text=True, cwd=REPO_ROOT,
    )
    staged = subprocess.run(
        ["git", "diff", "--cached", "--name-only"],
        capture_output=True, text=True, cwd=REPO_ROOT,
    )
    files: set[str] = set()
    for out in (result.stdout, staged.stdout):
        for line in out.strip().splitlines():
            line = line.strip()
            if line:
                files.add(line)
    return files


def pick_test_targets(changed_files: set[str]) -> list[str] | None:
    """根据变更文件决定跑哪些测试。

    返回：
      - 具体测试目标列表（如 ["tests/test_utils", "tests/test_data"]）
      - None 表示跑全量子集（-m "not slow"）
      - [] 表示无相关测试可跑
    """
    if not changed_files:
        _s("  [info] 无变更文件，跳过测试")
        return []

    matched_tests: set[str] = set()
    cross_module = False

    for f in changed_files:
        # 工具目录/文档/配置变更 -> 不影响业务代码，不触发测试
        if (
            f.startswith("docs/")
            or f.startswith("scripts/")
            or f.startswith("frontend/")
            or f.startswith(".github/")
            or f in (".env.example", "pyproject.toml", "README.md")
        ):
            continue

        # 非 .py 文件且不在上面列表中 -> 忽略
        if not f.endswith(".py"):
            continue

        # 测试文件本身 -> 跑对应目录
        if f.startswith("tests/"):
            test_dir = str(Path(f).parent).replace("\\", "/")
            if test_dir != "tests":
                matched_tests.add(test_dir)
            continue

        # 源文件 -> 查映射
        matched_one = False
        for src_prefix, test_dir in SRC_TO_TEST.items():
            if f.startswith(src_prefix):
                if test_dir is not None:
                    matched_tests.add(test_dir)
                matched_one = True
                break

        if not matched_one:
            # 不在映射表中 -> 跨模块变更
            cross_module = True

    # 匹配到多个不同测试目录 -> 跨模块
    if len(matched_tests) > 2:
        cross_module = True

    if cross_module:
        _s("  [info] 检测到跨模块变更，跑全量子集")
        return None

    return sorted(matched_tests) if matched_tests else []


def run_step(name: str, cmd: list[str]) -> bool:
    """运行一个检查步骤。返回 True 表示通过。"""
    _s(f"\n  === {name} ===")
    result = subprocess.run(cmd, cwd=REPO_ROOT)
    ok = result.returncode == 0
    _s(f"  {_bool_symbol(ok)} {name}")
    return ok


def ensure_deps() -> None:
    """检测并安装可能缺失的依赖。"""
    deps: list[str] = []
    try:
        import slowapi  # noqa: F401
    except ImportError:
        deps.append("slowapi")

    if deps:
        _s(f"  [info] 安装缺失依赖: {', '.join(deps)}")
        subprocess.run(
            [sys.executable, "-m", "pip", "install", *deps, "-q"],
            cwd=REPO_ROOT,
        )


def _print_header() -> None:
    _s("")
    _s("=" * 60)
    _s("  litchi-head 本地 CI 检查")
    _s("  ruff -> pyright -> 按变更范围智能测试")
    _s("=" * 60)


def _print_summary(passes: int, total: int) -> None:
    _s("")
    _s("=" * 60)
    all_ok = passes == total
    if all_ok:
        _s(f"  全部通过 ({passes}/{total})")
    else:
        _s(f"  通过 {passes}/{total}，需要修复")
    _s("")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="litchi-head 本地 CI 检查",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--full", action="store_true",
        help="强制跑全量测试（-m 'not slow'），忽略变更范围检测",
    )
    parser.add_argument(
        "--diff", metavar="REF", default="HEAD",
        help="跟哪个 ref 比较变更范围（默认 HEAD，即上次提交）",
    )
    args = parser.parse_args()

    _print_header()
    ensure_deps()

    passes = 0
    total = 3  # ruff + pyright + tests

    # ── 1. Ruff ──
    if run_step("ruff", ["ruff", "check", "."]):
        passes += 1

    # ── 2. Pyright ──
    if run_step("pyright", ["pyright", "src/"]):
        passes += 1

    # ── 3. 测试 ──
    changed = git_diff(args.diff) if not args.full else set()

    if args.full:
        test_target: list[str] | None = None
        _s("  [info] --full 模式：跑全量子集")
    else:
        test_target = pick_test_targets(changed)
        if changed:
            _s(f"  [info] 检测到 {len(changed)} 个变更文件")
            for f in sorted(changed):
                _s(f"         {f}")

    test_ok = True
    if test_target == []:
        _s("  [tests] 无相关测试，跳过")
    elif test_target is None:
        test_ok = run_step(
            "tests (not slow)",
            [sys.executable, "-m", "pytest", "-x", "--tb=short", "-m", "not slow"],
        )
    else:
        _s(f"  [info] 按变更范围选择测试目录: {', '.join(test_target)}")
        test_ok = run_step(
            "tests (module subset)",
            [sys.executable, "-m", "pytest", "-x", "--tb=short", *test_target],
        )

    if test_ok:
        passes += 1

    _print_summary(passes, total)
    return 0 if passes == total else 1


if __name__ == "__main__":
    sys.exit(main())
