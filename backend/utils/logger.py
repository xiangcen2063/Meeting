"""
中文简洁日志系统
提供彩色输出和结构化日志记录
"""

import sys
import json
from datetime import datetime
from pathlib import Path
from enum import Enum
from typing import Any


class LogLevel(Enum):
    """日志级别"""
    DEBUG = "调试"
    INFO = "信息"
    SUCCESS = "成功"
    WARNING = "警告"
    ERROR = "错误"


class Colors:
    """终端颜色代码"""
    RESET = "\033[0m"
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    MAGENTA = "\033[95m"
    CYAN = "\033[96m"
    GRAY = "\033[90m"
    BOLD = "\033[1m"


class Logger:
    """中文日志记录器"""
    
    def __init__(self, name: str = "系统"):
        self.name = name
        self.log_file: Path | None = None
    
    def set_log_file(self, log_file: Path):
        """设置日志文件路径"""
        self.log_file = log_file
        log_file.parent.mkdir(parents=True, exist_ok=True)
    
    def _format_message(self, level: LogLevel, module: str, message: str) -> str:
        """格式化日志消息"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        return f"[{timestamp}] [{level.value}] [{module}] {message}"
    
    def _print_colored(self, message: str, color: str):
        """打印彩色消息"""
        print(f"{color}{message}{Colors.RESET}", flush=True)
    
    def _write_to_file(self, message: str):
        """写入日志文件"""
        if self.log_file:
            with open(self.log_file, "a", encoding="utf-8") as f:
                f.write(message + "\n")
    
    def debug(self, module: str, message: str):
        """调试日志"""
        msg = self._format_message(LogLevel.DEBUG, module, message)
        self._print_colored(msg, Colors.GRAY)
        self._write_to_file(msg)
    
    def info(self, module: str, message: str):
        """信息日志"""
        msg = self._format_message(LogLevel.INFO, module, message)
        self._print_colored(msg, Colors.CYAN)
        self._write_to_file(msg)
    
    def success(self, module: str, message: str):
        """成功日志"""
        msg = self._format_message(LogLevel.SUCCESS, module, message)
        self._print_colored(msg, Colors.GREEN)
        self._write_to_file(msg)
    
    def warning(self, module: str, message: str):
        """警告日志"""
        msg = self._format_message(LogLevel.WARNING, module, message)
        self._print_colored(msg, Colors.YELLOW)
        self._write_to_file(msg)
    
    def error(self, module: str, message: str):
        """错误日志"""
        msg = self._format_message(LogLevel.ERROR, module, message)
        self._print_colored(msg, Colors.RED)
        self._write_to_file(msg)
    
    def section(self, title: str):
        """章节分隔符"""
        separator = "=" * 50
        msg = f"\n{separator}\n{title}\n{separator}"
        self._print_colored(msg, Colors.BOLD + Colors.BLUE)
        self._write_to_file(msg)
    
    def step(self, step_num: int, total: int, description: str):
        """步骤日志"""
        msg = f"  步骤 [{step_num}/{total}] {description}"
        self._print_colored(msg, Colors.MAGENTA)
        self._write_to_file(msg)


def save_json_log(data: dict, filename: str, storage_dir: Path) -> Path:
    """
    保存 JSON 格式的详细日志
    
    Args:
        data: 要保存的数据
        filename: 文件名
        storage_dir: 存储目录
        
    Returns:
        保存的文件路径
    """
    storage_dir.mkdir(parents=True, exist_ok=True)
    filepath = storage_dir / filename
    
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    
    return filepath


# 全局日志实例
logger = Logger("会面推荐")
