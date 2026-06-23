"""凭据管理器 — 安全存储 API Keys

优先级链（自动降级）：
1. 系统凭据管理器（Windows Credential Manager / macOS Keychain）
2. 环境变量（用于 CI/容器/无头环境）
3. .env 文件（通过 settings fallback，最末位）

用法:
    from src.utils.credentials import credential_manager

    # 读取凭据（自动走优先级链）
    api_key = credential_manager.get("DEEPSEEK_API_KEY")

    # 存储凭据（写入系统凭据管理器）
    credential_manager.store("DEEPSEEK_API_KEY", "sk-xxx")

    # 删除凭据
    credential_manager.delete("DEEPSEEK_API_KEY")
"""

import logging
import os
from typing import Optional

logger = logging.getLogger("credentials")

# 凭据服务名称（Windows Credential Manager 中显示为此名称）
SERVICE_NAME = "litchi-head"

# 需要保护的 API Key 列表（名称 → 用途说明）
PROTECTED_KEYS: dict[str, str] = {
    "DEEPSEEK_API_KEY": "DeepSeek LLM API",
}


class CredentialManager:
    """凭据管理器

    职责：
    - 从系统凭据管理器（keyring）读取/写入/删除凭据
    - 优雅降级：keyring 不可用时回退到环境变量
    - 提供统一读取接口（供 config.py 使用）
    """

    def __init__(self, service_name: str = SERVICE_NAME) -> None:
        self._service_name = service_name
        self._keyring: bool = False
        self._backend_name: str = ""
        self._init_keyring()

    def _init_keyring(self) -> None:
        """尝试初始化 keyring，失败时降级到环境变量"""
        try:
            import keyring as _kr  # type: ignore[import-untyped]

            # 尝试一次读写来验证后端真正可用
            test_key = "__litchi_head_cred_test__"
            _kr.set_password(self._service_name, test_key, "ok")
            _kr.delete_password(self._service_name, test_key)
            self._keyring = True
            self._backend_name = getattr(_kr, "backend", None) or "unknown"
            logger.info(f"凭据管理器后端: {self._backend_name}")
        except ImportError:
            logger.info("keyring 未安装，凭据读取降级到环境变量")
        except Exception as e:
            logger.warning(f"keyring 初始化失败 ({e})，降级到环境变量")

    @property
    def available(self) -> bool:
        """系统凭据管理器是否可用"""
        return self._keyring

    def get(self, key: str) -> Optional[str]:
        """按优先级读取凭据：凭据管理器 → 环境变量

        Args:
            key: 凭据名称（如 "DEEPSEEK_API_KEY"）

        Returns:
            凭据值，未找到返回 None
        """
        # 1. 系统凭据管理器
        if self._keyring:
            try:
                import keyring as _kr  # type: ignore[import-untyped]

                value = _kr.get_password(self._service_name, key)
                if value is not None:
                    logger.debug(f"凭据 {key} 来自系统凭据管理器")
                    return value
            except Exception as e:
                logger.debug(f"keyring.get_password({key}) 失败: {e}")

        # 2. 环境变量
        value = os.environ.get(key)
        if value:
            logger.debug(f"凭据 {key} 来自环境变量")
            return value

        return None

    def store(self, key: str, value: str) -> bool:
        """存储凭据到系统凭据管理器

        Args:
            key: 凭据名称
            value: 凭据值

        Returns:
            是否成功
        """
        if not self._keyring:
            logger.error(f"凭据管理器不可用，无法存储 {key}")
            return False
        try:
            import keyring as _kr  # type: ignore[import-untyped]

            _kr.set_password(self._service_name, key, value)
            logger.info(f"✅ 凭据 {key} 已安全存储到系统凭据管理器")
            return True
        except Exception as e:
            logger.error(f"存储凭据 {key} 失败: {e}")
            return False

    def delete(self, key: str) -> bool:
        """从系统凭据管理器删除凭据

        Args:
            key: 凭据名称

        Returns:
            是否成功
        """
        if not self._keyring:
            return False
        try:
            import keyring as _kr  # type: ignore[import-untyped]

            _kr.delete_password(self._service_name, key)
            logger.info(f"凭据 {key} 已从系统凭据管理器删除")
            return True
        except Exception as e:
            logger.debug(f"删除凭据 {key} 失败: {e}")
            return False

    def list_keys(self) -> dict[str, str]:
        """列出所有已存储的凭据名称（不包含值）

        Returns:
            名称 → 状态映射
        """
        result: dict[str, str] = {}
        for key in PROTECTED_KEYS:
            value = self.get(key)
            if value:
                result[key] = "✅ 已配置"
            else:
                result[key] = "❌ 未设置"
        return result


credential_manager = CredentialManager()
