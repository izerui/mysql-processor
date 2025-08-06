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

    def _format_message(self, level: str, message: str, context: Optional[Dict] = None) -> str:
        """格式化消息"""
        color = self.LEVEL_COLORS.get(level, '')
        reset = Style.RESET_ALL

        # 添加上下文信息
        context_str = ""
        if context:
            context_parts = []
            for key, value in context.items():
                if key == 'progress':
                    context_parts.append(f"{value:.1f}%")
                elif key == 'time':
                    context_parts.append(f"{value:.2f}s")
                elif key == 'size':
                    context_parts.append(f"{value:.2f}MB")
                else:
                    context_parts.append(f"{key}={value}")
            if context_parts:
                context_str = f" [{', '.join(context_parts)}]"

        return f"{color}{message}{context_str}{reset}"

    def log_system_start(self, databases: list, tables: list):
        """记录系统启动信息"""
        print(f"\n{Fore.CYAN}{'=' * 80}")
        print(f"{Fore.CYAN}🚀 MySQL Processor 启动")
        print(f"{Fore.CYAN}⏰ 时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"{Fore.CYAN}📊 数据库: {len(databases)}个")
        if tables and tables != ['*']:
            print(f"{Fore.CYAN}📊 指定表: {len(tables)}个")
        print(f"{Fore.CYAN}{'=' * 80}\n")

    def log_database_start(self, database: str, operation: str):
        """记录数据库操作开始"""
        print(f"\n{Fore.GREEN}{'─' * 60}")
        print(f"{Fore.GREEN}🗄️ {operation.upper()} 数据库: {Fore.YELLOW}{database}")
        print(f"{Fore.GREEN}{'─' * 60}")

    def log_database_complete(self, database: str, operation: str, duration: float):
        """记录数据库操作完成"""
        print(f"\n{Fore.GREEN}✅ {operation.upper()} 完成: {Fore.YELLOW}{database} {Fore.GREEN}(耗时: {duration:.2f}s)")

    def log_table_progress(self, database: str, table: str, progress: float,
                           current: int = 0, total: int = 0, speed: Optional[float] = None):
        """记录表操作进度"""
        bar_length = 30
        filled_length = int(bar_length * progress // 100)
        bar = '█' * filled_length + '░' * (bar_length - filled_length)

        progress_str = f"[{bar}] {progress:5.1f}%"
        if total > 0:
            progress_str += f" ({current}/{total})"
        if speed:
            progress_str += f" {speed:.1f}MB/s"

        print(f"\r{Fore.CYAN}📊 {database}.{table} {progress_str}", end="", flush=True)

    def log_table_complete(self, database: str, table: str, duration: float, size_mb: float = 0):
        """记录表操作完成"""
        # 清除进度条行
        print(f"\r{' ' * 100}\r", end="")
        size_str = f" ({size_mb:.1f}MB)" if size_mb > 0 else ""
        print(f"{Fore.GREEN}✅ {database}.{table}{size_str} 完成 (耗时: {duration:.2f}s)")

    def log_batch_progress(self, operation: str, completed: int, total: int,
                           failed: int = 0, eta: Optional[float] = None):
        """记录批量操作进度"""
        progress = (completed / total * 100) if total > 0 else 0

        status_parts = [f"{completed}/{total}"]
        if failed > 0:
            status_parts.append(f"{Fore.RED}失败: {failed}")
        if eta:
            status_parts.append(f"ETA: {eta:.0f}s")

        status_str = " | ".join(status_parts)
        print(f"\n{Fore.YELLOW}📊 {operation}: {progress:.1f}% [{status_str}]")

    def log_summary(self, results: list, total_duration: float):
        """记录操作汇总"""
        success_count = sum(1 for r in results if r.get('status') == 'success')
        failed_count = len(results) - success_count

        print(f"\n{Fore.CYAN}{'=' * 80}")
        print(f"{Fore.CYAN}🎉 操作完成汇总")
        print(f"{Fore.CYAN}{'=' * 80}")
        print(f"{Fore.GREEN}✅ 成功: {success_count}")
        if failed_count > 0:
            print(f"{Fore.RED}❌ 失败: {failed_count}")
        print(f"{Fore.CYAN}⏰ 总耗时: {total_duration:.2f}s")

        # 显示失败详情
        if failed_count > 0:
            print(f"\n{Fore.RED}失败详情:")
            for result in results:
                if result.get('status') == 'failed':
                    print(f"{Fore.RED}  - {result.get('database', 'Unknown')}: {result.get('error', 'Unknown error')}")

    def cleanup(self, path: str):
        """记录清理操作"""
        print(f"{Fore.YELLOW}🧹 清理: {path}")

    # 兼容旧接口的方法
    def info(self, message: str, *args, **kwargs):
        """记录信息"""
        print(f"{Fore.CYAN}ℹ️ {message}")

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

    def success(self, message: str, *args, **kwargs):
        """兼容旧logger接口"""
        print(f"{Fore.GREEN}✅ {str(message)}")


# 创建全局日志器实例
logger = StructuredLogger()
