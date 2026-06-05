"""日志系统 —— 多 Agent 调试的核心工具"""

import logging
import sys
from pathlib import Path


class AgentLogger:
    """Agent 专用日志器，每个 Agent 有独立的日志文件"""

    _instances: dict = {}

    def __new__(cls, name: str, log_dir: str = "logs"):
        if name not in cls._instances:
            cls._instances[name] = super().__new__(cls)
        return cls._instances[name]

    def __init__(self, name: str, log_dir: str = "logs"):
        if hasattr(self, "_initialized"):
            return
        self._initialized = True

        self.name = name
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)

        self.logger = logging.getLogger(name)
        self.logger.setLevel(logging.DEBUG)

        # 控制台 handler（带颜色）
        console = logging.StreamHandler(sys.stdout)
        console.setLevel(logging.DEBUG)
        console.setFormatter(_ColorFormatter())
        self.logger.addHandler(console)

        # 文件 handler
        file_handler = logging.FileHandler(
            self.log_dir / f"{name}.log",
            encoding="utf-8",
        )
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(logging.Formatter(
            "%(asctime)s | %(name)s | %(levelname)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        ))
        self.logger.addHandler(file_handler)

    def debug(self, msg: str, **extra):
        self.logger.debug(msg, extra={"extra": extra})

    def info(self, msg: str, **extra):
        self.logger.info(msg, extra={"extra": extra})

    def warning(self, msg: str, **extra):
        self.logger.warning(msg, extra={"extra": extra})

    def error(self, msg: str, **extra):
        self.logger.error(msg, extra={"extra": extra})

    def agent_action(self, action: str, agent: str, detail: dict | None = None):
        """记录 Agent 的关键动作"""
        detail_str = f" | {detail}" if detail else ""
        self.info(f"[{agent}] {action}{detail_str}")


class _ColorFormatter(logging.Formatter):
    """控制台彩色输出"""

    _COLORS = {
        "DEBUG": "\033[36m",
        "INFO": "\033[32m",
        "WARNING": "\033[33m",
        "ERROR": "\033[31m",
        "CRITICAL": "\033[41m",
        "RESET": "\033[0m",
    }

    def format(self, record):
        color = self._COLORS.get(record.levelname, self._COLORS["RESET"])
        reset = self._COLORS["RESET"]
        record.levelname = f"{color}{record.levelname}{reset}"
        return super().format(record)
