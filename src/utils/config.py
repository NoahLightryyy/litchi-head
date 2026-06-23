"""统一配置管理

Settings 初始化流程：
1. Pydantic 从 .env 加载所有配置（含 API Keys）
2. model_post_init 从凭据管理器（Credential Manager → 环境变量）补充 API Keys
3. 凭据管理器有值 → 覆盖 .env 明文值
4. 两者都无值 → 保持空字符串 → 后续使用时报错

这样 .env 可以安全地留空或放占位符，
真正的密钥存储在操作系统凭据管理器中。
"""

import logging
import os
from pathlib import Path

from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict

from src.utils.credentials import credential_manager

# 提前加载 .env 到环境变量（让 keyring fallback 也能读到）
load_dotenv()

logger = logging.getLogger("config")

# Settings 中 API Key 字段名 → 环境变量名映射
_API_KEY_FIELDS: dict[str, str] = {
    "deepseek_api_key": "DEEPSEEK_API_KEY",
}


class Settings(BaseSettings):
    # ── LLM 配置 ──
    llm_provider: str = "deepseek"
    deepseek_api_key: str = ""

    # ── 辩论配置 ──
    max_concurrent_agents: int = 10
    debate_timeout_seconds: int = 120
    max_debate_rounds: int = 3
    enable_cross_group_challenge: bool = True

    # ── 风控配置 ──
    max_single_position: float = 0.2
    max_daily_loss: float = 0.05

    # ── 记忆配置 ──
    memory_backend: str = "json"
    memory_max_recent_trades: int = 30

    # ── 数据路径 ──
    data_dir: str = str(Path(__file__).parent.parent.parent / "data")
    log_dir: str = str(Path(__file__).parent.parent.parent / "logs")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    def model_post_init(self, __context: object) -> None:
        """从凭据管理器补充 API Keys（覆盖 .env 明文值）

        优先级：
        1. 系统凭据管理器（Windows Credential Manager）
        2. 环境变量（手动 export 或 CI 设置）
        3. .env 文件（默认 fallback，保留仅用于兼容）
        """
        for field_name, env_name in _API_KEY_FIELDS.items():
            cred_value = credential_manager.get(env_name)
            if cred_value:
                setattr(self, field_name, cred_value)

    def get_key_source(self, field_name: str) -> str:
        """获取指定 API Key 的来源（用于日志/诊断）

        Returns:
            "credential_manager" | "env_var" | "env_file" | "unset"
        """
        env_name = _API_KEY_FIELDS.get(field_name)
        if not env_name:
            return "unknown"

        current = getattr(self, field_name, "")

        # 检查凭据管理器
        if credential_manager.available:
            try:
                import keyring as _kr  # type: ignore[import-untyped]

                cm_value = _kr.get_password(
                    credential_manager._service_name, env_name
                )
                if cm_value == current:
                    return "credential_manager"
            except Exception:
                pass

        # 检查环境变量
        if os.environ.get(env_name) == current:
            return "env_var"

        # 检查 .env（通过默认值判断）
        if current:
            return "env_file"

        return "unset"


settings = Settings()


def ensure_dirs():
    """确保数据目录存在"""
    for d in [settings.data_dir, settings.log_dir]:
        Path(d).mkdir(parents=True, exist_ok=True)
