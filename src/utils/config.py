"""统一配置管理"""

from pathlib import Path

from dotenv import load_dotenv
from pydantic_settings import BaseSettings

load_dotenv()


class Settings(BaseSettings):
    # ── LLM 配置 ──
    llm_provider: str = "deepseek"
    deepseek_api_key: str = ""
    openai_api_key: str = ""

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

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


settings = Settings()


def ensure_dirs():
    """确保数据目录存在"""
    for d in [settings.data_dir, settings.log_dir]:
        Path(d).mkdir(parents=True, exist_ok=True)
