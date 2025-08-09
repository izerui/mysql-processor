import sys
import threading
import time
from datetime import datetime
from typing import Optional, Dict
import os

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
        self.log_file = "logs/stdio.log"
        self.progress_trackers: Dict[str, ProgressTracker] = {}
        # 确保logs目录存在
        os.makedirs("logs", exist_ok=True)

    def print(self, message: str):
        """同时输出到控制台和文件"""
        print(message)
        # 写入文件（去除颜色代码）
        clean_message = message.replace(Fore.CYAN, "").replace(Fore.GREEN, "").replace(Fore.YELLOW, "").replace(Fore.RED, "").replace(Fore.MAGENTA, "").replace(Back.RED, "").replace(Back.WHITE, "").replace(Fore.WHITE, "").replace(Style.RESET_ALL, "")
        with open(self.log_file, "a", encoding="utf-8") as f:
            f.write(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | {clean_message}\n")

    def cleanup(self, path: str):
        """记录清理操作"""
        self.print(f"{Fore.YELLOW}🧹 清理: {path}")

    # 兼容旧接口的方法
    def info(self, message: str, *args, **kwargs):
        """记录信息"""
        self.print(f"{Fore.CYAN}ℹ️ {message}")

    def process(self, message: str, *args, **kwargs):
        """进度信息"""
        self.print(f"{Fore.MAGENTA}📊 {message}")

    def error(self, message: str, *args, **kwargs):
        """记录错误"""
        context = kwargs.get('context', None)
        context_str = f" - {context}" if context else ""
        self.print(f"\n{Fore.RED}❌ 错误: {message}{context_str}")

    def warning(self, message: str, *args, **kwargs):
        """记录警告"""
        self.print(f"{Fore.YELLOW}⚠️ 警告: {message}")

    def debug(self, message: str, *args, **kwargs):
        """兼容旧logger接口"""
        self.print(f"{Fore.CYAN}🐛 {str(message)}")

    def success(self, message: str, total_duration: float = None):
        """兼容旧logger接口"""
        msg = f"{Fore.GREEN}✅ {str(message)}"
        if total_duration:
            duration = time.time() - total_duration
            # 格式化时间显示
            if duration >= 3600:  # 大于等于1小时
                hours = int(duration // 3600)
                minutes = int((duration % 3600) // 60)
                time_str = f"{hours}小时{minutes}分钟"
            elif duration >= 60:  # 大于等于1分钟
                minutes = int(duration // 60)
                seconds = int(duration % 60)
                time_str = f"{minutes}分钟{seconds}秒"
            else:  # 小于1分钟
                time_str = f"{duration:.2f}秒"
            msg += f" | 耗时: {time_str}"
        self.print(msg)



    def log_system_start(self, databases: list):
        """记录系统启动信息"""
        self.print(f"\n{Fore.CYAN}{'=' * 80}")
        self.print(f"{Fore.CYAN}🚀 MySQL Processor 启动")
        self.print(f"{Fore.CYAN}⏰ 时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        self.print(f"{Fore.CYAN}📊 数据库: {len(databases)}个")
        self.print(f"{Fore.CYAN}{'=' * 80}\n")

    def log_start(self, message: str):
        """记录数据库操作开始"""
        self.print(f"{Fore.CYAN}🚀 {message}")
        return time.time()

    def log_summary(self, results: list, total_duration: float):
        """记录操作汇总"""
        success_count = sum(1 for r in results if r.get('status') == 'success')
        failed_count = len(results) - success_count

        # 格式化时间显示
        if total_duration >= 3600:  # 大于等于1小时
            hours = int(total_duration // 3600)
            minutes = int((total_duration % 3600) // 60)
            time_str = f"{hours}小时{minutes}分钟"
        elif total_duration >= 60:  # 大于等于1分钟
            minutes = int(total_duration // 60)
            seconds = int(total_duration % 60)
            time_str = f"{minutes}分钟{seconds}秒"
        else:  # 小于1分钟
            time_str = f"{total_duration:.2f}秒"

        self.print(f"\n{Fore.CYAN}{'=' * 80}")
        self.print(f"{Fore.CYAN} 🏆 所有操作完成汇总 🏆")
        self.print(f"{Fore.CYAN}{'=' * 80}")
        self.print(f"{Fore.GREEN} ✅ 成功: {success_count} 个数据库")
        if failed_count > 0:
            self.print(f"{Fore.RED} ❌ 失败: {failed_count} 个数据库")
        self.print(f"{Fore.CYAN} ⏰ 总耗时: {time_str}")
        self.print(f"{Fore.CYAN}{'=' * 80}\n")

        # 显示失败详情
        if failed_count > 0:
            self.print(f"\n{Fore.RED}失败详情:")
            for result in results:
                if result.get('status') == 'failed':
                    self.print(f"{Fore.RED}  - {result.get('database', 'Unknown')}: {result.get('error', 'Unknown error')}")


# 创建全局日志器实例
logger = StructuredLogger()
