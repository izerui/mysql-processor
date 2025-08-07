import logging
import sys
import threading
import time
from datetime import datetime
from typing import Optional, Dict

import colorama
from colorama import Fore, Back, Style

# 初始化colorama，支持Windows终端颜色
colorama.init(autoreset=True)


class ProgressTracker:
    """进度追踪器"""

    def __init__(self, total: int, description: str = ""):
        self.total = total
        self.current = 0
        self.description = description
        self.start_time = time.time()
        self.lock = threading.Lock()

    def update(self, increment: int = 1):
        with self.lock:
            self.current += increment

    @property
    def percentage(self) -> float:
        return (self.current / self.total * 100) if self.total > 0 else 0

    @property
    def elapsed_time(self) -> float:
        return time.time() - self.start_time

    @property
    def eta(self) -> Optional[float]:
        if self.current == 0:
            return None
        rate = self.current / self.elapsed_time
        remaining = self.total - self.current
        return remaining / rate if rate > 0 else None


class StructuredLogger:
    """结构化日志系统"""

    # 日志级别颜色映射
    LEVEL_COLORS = {
        'DEBUG': Fore.CYAN,
        'INFO': Fore.GREEN,
        'WARNING': Fore.YELLOW,
        'ERROR': Fore.RED,
        'CRITICAL': Back.RED + Fore.WHITE,
    }

    # 状态图标
    STATUS_ICONS = {
        'START': '🚀',
        'PROGRESS': '⏳',
        'SUCCESS': '✅',
        'ERROR': '❌',
        'WARNING': '⚠️',
        'INFO': 'ℹ️',
        'COMPLETE': '🎉',
        'CLEAN': '🧹',
        'DATABASE': '🗄️',
        'TABLE': '📊',
        'FILE': '📄',
        'TIME': '⏰',
        'STATS': '📊',
    }

    def __init__(self, name: str = "MySQLProcessor"):
        self.logger = logging.getLogger(name)
        self.progress_trackers: Dict[str, ProgressTracker] = {}
        self.setup_logger()

    def cleanup(self, path: str):
        """记录清理操作"""
        print(f"{Fore.YELLOW}🧹 清理: {path}")

    # 兼容旧接口的方法
    def info(self, message: str, *args, **kwargs):
        """记录信息"""
        print(f"{Fore.CYAN}ℹ️ {message}")

    def process(self, message: str, *args, **kwargs):
        """进度信息"""
        print(f"{Fore.MAGENTA}📊 {message}")

    def error(self, message: str, *args, **kwargs):
        """记录错误"""
        context = kwargs.get('context', None)
        context_str = f" - {context}" if context else ""
        print(f"{Fore.RED}❌ 错误: {message}{context_str}")

    def warning(self, message: str, *args, **kwargs):
        """记录警告"""
        print(f"{Fore.YELLOW}⚠️ 警告: {message}")

    def debug(self, message: str, *args, **kwargs):
        """兼容旧logger接口"""
        print(f"{Fore.CYAN}🐛 {str(message)}")

    def success(self, message: str, total_duration: float = None):
        """兼容旧logger接口"""
        msg = f"{Fore.GREEN}✅ {str(message)}"
        if total_duration:
            msg += f" | 耗时: {(time.time() - total_duration):.2f} 秒"
        print(msg)

    def setup_logger(self):
        """设置日志器"""
        if self.logger.handlers:
            return

        self.logger.setLevel(logging.INFO)

        # 创建控制台处理器
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)

        # 创建格式化器
        formatter = logging.Formatter(
            '%(asctime)s | %(levelname)8s | %(message)s',
            datefmt='%H:%M:%S'
        )
        console_handler.setFormatter(formatter)

        # 添加处理器
        self.logger.addHandler(console_handler)

    def log_system_start(self, databases: list):
        """记录系统启动信息"""
        print(f"\n{Fore.CYAN}{'=' * 80}")
        print(f"{Fore.CYAN}🚀 MySQL Processor 启动")
        print(f"{Fore.CYAN}⏰ 时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"{Fore.CYAN}📊 数据库: {len(databases)}个")
        print(f"{Fore.CYAN}{'=' * 80}\n")

    def log_start(self, message: str):
        """记录数据库操作开始"""
        print(f"{Fore.CYAN}🚀 {message}")
        return time.time()

    def log_summary(self, results: list, total_duration: float):
        """记录操作汇总"""
        success_count = sum(1 for r in results if r.get('status') == 'success')
        failed_count = len(results) - success_count

        print(f"\n{Fore.CYAN}{'=' * 80}")
        print(f"{Fore.CYAN} 🏆 所有操作完成汇总 🏆")
        print(f"{Fore.CYAN}{'=' * 80}")
        print(f"{Fore.GREEN} ✅ 成功: {success_count} 个数据库")
        if failed_count > 0:
            print(f"{Fore.RED} ❌ 失败: {failed_count} 个数据库")
        print(f"{Fore.CYAN} ⏰ 总耗时: {total_duration:.2f} 秒")
        print(f"{Fore.CYAN}{'=' * 80}\n")

        # 显示失败详情
        if failed_count > 0:
            print(f"\n{Fore.RED}失败详情:")
            for result in results:
                if result.get('status') == 'failed':
                    print(f"{Fore.RED}  - {result.get('database', 'Unknown')}: {result.get('error', 'Unknown error')}")


# 创建全局日志器实例
logger = StructuredLogger()
