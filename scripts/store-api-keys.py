#!/usr/bin/env python3
"""API Key 安全存储工具 — 将密钥存入系统凭据管理器

用法:
    # 交互式设置所有密钥
    python scripts/store-api-keys.py

    # 设置单个密钥
    python scripts/store-api-keys.py --set DEEPSEEK_API_KEY

    # 查看当前凭据状态
    python scripts/store-api-keys.py --status

    # 删除单个密钥
    python scripts/store-api-keys.py --delete DEEPSEEK_API_KEY

原理：
    使用 keyring 库将 API Key 写入操作系统凭据管理器：
    - Windows: Credential Manager
    - macOS: Keychain
    - Linux: Secret Service (gnome-keyring / kwallet)

⚠️  重要：轮换密钥后，务必删除旧密钥并存入新密钥。
"""

import argparse
import getpass
import sys
import textwrap
from pathlib import Path

# 将项目根目录加入 sys.path
_script_dir = Path(__file__).resolve().parent
_project_root = _script_dir.parent
sys.path.insert(0, str(_project_root))

from src.utils.credentials import PROTECTED_KEYS, credential_manager  # noqa: E402


def cmd_status() -> int:
    """显示所有凭据的状态"""
    status = credential_manager.list_keys()
    avail = "✅ 可用" if credential_manager.available else "⚠️ 不可用（降级到环境变量）"
    print(f"\n🔐 凭据管理器状态（{avail}）")
    if credential_manager.available:
        print(f"   后端: {credential_manager._backend_name}")
    print()
    print(f"{'凭据名称':<30s} {'状态':<20s} {'用途'}")
    print("-" * 80)
    for key, s in status.items():
        print(f"{key:<30s} {s:<20s} {PROTECTED_KEYS.get(key, '')}")
    print()
    return 0


def cmd_set(key: str | None = None) -> int:
    """交互式设置凭据"""
    targets = [key] if key else list(PROTECTED_KEYS.keys())

    if not credential_manager.available:
        print("❌ 系统凭据管理器不可用，无法存储凭据。")
        print("   请安装 keyring: pip install keyring")
        return 1

    for k in targets:
        if k not in PROTECTED_KEYS:
            print(f"⚠️  未知凭据: {k}，跳过")
            continue

        print(f"\n--- {k} ({PROTECTED_KEYS[k]}) ---")
        print(f"  当前状态: {'✅ 已配置' if credential_manager.get(k) else '❌ 未设置'}")

        value = getpass.getpass("  输入新值（留空跳过）: ").strip()
        if not value:
            print("  跳过")
            continue

        confirm = getpass.getpass("  再次输入确认: ").strip()
        if value != confirm:
            print("❌ 两次输入不一致，跳过")
            continue

        if credential_manager.store(k, value):
            print(f"  ✅ {k} 已安全存储")
        else:
            print("  ❌ 存储失败")
            return 1

    return 0


def cmd_delete(key: str) -> int:
    """删除指定凭据"""
    if key not in PROTECTED_KEYS:
        print(f"⚠️  未知凭据: {key}，可用: {', '.join(PROTECTED_KEYS.keys())}")
        return 1

    if not credential_manager.available:
        print("❌ 凭据管理器不可用")
        return 1

    current = credential_manager.get(key)
    if not current:
        print(f"  {key} 未设置，无需删除")
        return 0

    confirm = input(f"  确定要删除 {key}? (y/N): ").strip().lower()
    if confirm != "y":
        print("  取消")
        return 0

    if credential_manager.delete(key):
        print(f"  ✅ {key} 已删除")
    else:
        print("  ❌ 删除失败")
        return 1
    return 0


def print_rotation_guide() -> None:
    """打印密钥轮换指南"""
    guide = textwrap.dedent("""\
    ╔══════════════════════════════════════════════════════════╗
    ║          🔑 密钥轮换步骤                              ║
    ╠══════════════════════════════════════════════════════════╣
    ║  1. 登录 DeepSeek 平台，生成新 API Key                  ║
    ║  2. (当前仅使用 DeepSeek，无需其他 LLM Key)              ║
    ║  3. 运行此脚本存储新密钥:                               ║
    ║     python scripts/store-api-keys.py                    ║
    ║  4. 验证系统运行正常                                    ║
    ║     python scripts/check.py --full                        ║
    ║  5. 清理 .env 中的旧密钥（已清空）                      ║
    ╚══════════════════════════════════════════════════════════╝
    """)
    print(guide)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="🔐 litchi-head API Key 安全存储工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent("""\
            示例:
              # 交互式设置所有密钥
              python scripts/store-api-keys.py

              # 查看状态
              python scripts/store-api-keys.py --status

              # 设置单个
              python scripts/store-api-keys.py --set DEEPSEEK_API_KEY
        """),
    )
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--status", action="store_true", help="查看凭据状态")
    group.add_argument(
        "--set", metavar="KEY", nargs="?", const="all",
        help="设置凭据（默认设置所有）",
    )
    group.add_argument("--delete", metavar="KEY", help="删除凭据")

    args = parser.parse_args()

    # 无参数 → 交互式设置所有
    if not any([args.status, args.set, args.delete]):
        print("🔐 litchi-head API Key 安全存储工具")
        print("=" * 50)
        cm_status = "可用" if credential_manager.available else "不可用（降级到环境变量）"
        print(f"凭据管理器: {cm_status}")
        print()
        rc = cmd_set()
        if rc == 0:
            print_rotation_guide()
        return rc

    if args.status:
        return cmd_status()
    if args.set:
        key = None if args.set == "all" else args.set
        return cmd_set(key)
    if args.delete:
        return cmd_delete(args.delete)

    return 0


if __name__ == "__main__":
    sys.exit(main())
