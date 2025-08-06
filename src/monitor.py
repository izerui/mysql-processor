#!/usr/bin/env python3
"""
全局文件系统监控模块
独立于dump.py，提供可复用的文件监控功能
"""

import os
import time
import threading
from pathlib import Path
from typing import Optional, Callable, Dict, Any
from logger_config import logger

# 全局监控管理器
_global_monitor_manager = None
_global_monitor_lock = threading.Lock()


class FileMonitor:
    """独立的文件系统监控类"""

    def __init__(self, target_dir: str, interval: int = 2):
        """
        初始化文件监控器

        Args:
            target_dir: 要监控的目录路径
            interval: 检查间隔时间（秒）
        """
        self.target_dir = Path(target_dir)
        self.interval = interval
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._no_change_counter = 0
        self._last_total_size = 0
        self._last_check_time = time.time()
        self._callbacks: Dict[str, Callable] = {}

    def start(self) -> bool:
        """启动监控线程"""
        with _global_monitor_lock:
            if self.is_running():
                logger.warning("监控线程已在运行")
                return False

            self._stop_event.clear()
            self._thread = threading.Thread(
                target=self._monitor_loop,
                daemon=True
            )
            self._thread.start()
            logger.info(f"🚀 文件监控已启动: {self.target_dir}")
            return True

    def stop(self) -> bool:
        """停止监控线程"""
        with _global_monitor_lock:
            if not self.is_running():
                logger.warning("监控线程未运行")
                return False

            self._stop_event.set()
            self._thread.join(timeout=10)
            if self._thread.is_alive():
                logger.error("监控线程停止超时")
                return False

            self._thread = None
            logger.info("🛑 文件监控已停止")
            return True

    def is_running(self) -> bool:
        """检查监控线程是否在运行"""
        return self._thread is not None and self._thread.is_alive()

    def add_callback(self, name: str, callback: Callable[[Dict[str, Any]], None]) -> None:
        """
        添加回调函数

        Args:
            name: 回调名称
            callback: 回调函数，接收包含监控信息的字典
        """
        self._callbacks[name] = callback

    def remove_callback(self, name: str) -> bool:
        """移除回调函数"""
        if name in self._callbacks:
            del self._callbacks[name]
            return True
        return False

    def _monitor_loop(self):
        """监控主循环"""
        logger.info("🌐 文件监控线程开始运行")

        while not self._stop_event.is_set():
            try:
                if self.target_dir.exists():
                    total_size, file_count = self._get_dir_info()
                    current_time = time.time()
                    time_elapsed = current_time - self._last_check_time

                    info = {
                        'total_size': total_size,
                        'total_size_mb': total_size / (1024 * 1024),
                        'file_count': file_count,
                        'time_elapsed': time_elapsed,
                        'has_changed': total_size != self._last_total_size,
                        'speed_mbps': 0
                    }

                    if info['has_changed']:
                        # 有变化立即处理
                        if time_elapsed > 0:
                            info['speed_mbps'] = (total_size - self._last_total_size) / (1024 * 1024) / time_elapsed
                        self._notify_callbacks(info)
                        self._no_change_counter = 0
                    else:
                        # 无变化时计数
                        self._no_change_counter += 1
                        if self._no_change_counter % 10 == 0:
                            self._notify_callbacks(info)

                    self._last_total_size = total_size
                    self._last_check_time = current_time
                else:
                    # 目录不存在时计数
                    self._no_change_counter += 1
                    if self._no_change_counter % 10 == 0:
                        info = {
                            'total_size': 0,
                            'total_size_mb': 0,
                            'file_count': 0,
                            'time_elapsed': 0,
                            'has_changed': False,
                            'speed_mbps': 0
                        }
                        self._notify_callbacks(info)

            except Exception as e:
                logger.error(f"监控线程出错: {str(e)}")

            time.sleep(self.interval)

        logger.info("🛑 文件监控线程已停止")

    def _get_dir_info(self) -> tuple[int, int]:
        """获取目录信息"""
        total_size = 0
        file_count = 0

        if self.target_dir.exists():
            for file_path in self.target_dir.rglob('*'):
                if file_path.is_file():
                    try:
                        total_size += file_path.stat().st_size
                        file_count += 1
                    except (OSError, IOError):
                        pass

        return total_size, file_count

    def _notify_callbacks(self, info: Dict[str, Any]):
        """通知所有回调函数"""
        for name, callback in self._callbacks.items():
            try:
                callback(info)
            except Exception as e:
                logger.error(f"回调函数 {name} 执行失败: {str(e)}")


class GlobalMonitorManager:
    """全局监控管理器"""

    def __init__(self):
        self._monitors: Dict[str, FileMonitor] = {}

    def start_monitor(self, monitor_id: str, target_dir: str, interval: int = 2) -> bool:
        """启动全局监控"""
        if monitor_id in self._monitors:
            logger.warning(f"监控ID {monitor_id} 已存在")
            return False

        monitor = FileMonitor(target_dir, interval)
        if monitor.start():
            self._monitors[monitor_id] = monitor
            return True
        return False

    def stop_monitor(self, monitor_id: str) -> bool:
        """停止指定监控"""
        if monitor_id not in self._monitors:
            return False

        success = self._monitors[monitor_id].stop()
        if success:
            del self._monitors[monitor_id]
        return success

    def stop_all(self):
        """停止所有监控"""
        for monitor_id in list(self._monitors.keys()):
            self.stop_monitor(monitor_id)

    def get_monitor(self, monitor_id: str) -> Optional[FileMonitor]:
        """获取指定监控器"""
        return self._monitors.get(monitor_id)

    def list_monitors(self) -> list[str]:
        """列出所有监控ID"""
        return list(self._monitors.keys())


# 全局监控管理器实例
_global_monitor_manager = GlobalMonitorManager()

# 便捷函数
def start_global_monitor(monitor_id: str, target_dir: str, interval: int = 2) -> bool:
    """启动全局监控"""
    return _global_monitor_manager.start_monitor(monitor_id, target_dir, interval)

def stop_global_monitor(monitor_id: str) -> bool:
    """停止指定全局监控"""
    return _global_monitor_manager.stop_monitor(monitor_id)

def stop_all_monitors():
    """停止所有全局监控"""
    _global_monitor_manager.stop_all()

def get_global_monitor(monitor_id: str) -> Optional[FileMonitor]:
    """获取全局监控器"""
    return _global_monitor_manager.get_monitor(monitor_id)

# 默认监控器
_default_monitor = None

def start_default_monitor(target_dir: str, interval: int = 2) -> bool:
    """启动默认监控器"""
    global _default_monitor
    if _default_monitor is None:
        _default_monitor = FileMonitor(target_dir, interval)
    return _default_monitor.start()

def stop_default_monitor() -> bool:
    """停止默认监控器"""
    global _default_monitor
    if _default_monitor is not None:
        success = _default_monitor.stop()
        _default_monitor = None
        return success
    return False

def add_default_callback(name: str, callback: Callable[[Dict[str, Any]], None]) -> None:
    """为默认监控器添加回调"""
    if _default_monitor is not None:
        _default_monitor.add_callback(name, callback)

# 程序退出时清理
import atexit
atexit.register(stop_all_monitors)
