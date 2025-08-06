#!/usr/bin/env python3
"""极简文件监控模块"""

import time
import threading
from pathlib import Path
from typing import Optional, Callable, Dict, Any
from logger_config import logger

class FileMonitor:
    """文件监控器"""

    def __init__(self, target_dir: str, interval: int = 2):
        self.target_dir = Path(target_dir)
        self.interval = interval
        self._thread = None
        self._stop = threading.Event()
        self._last_size = 0.0
        self._last_time = 0.0
        self._last_files: Dict[str, Dict[str, float]] = {}
        self._callbacks = {}

    def start(self) -> bool:
        """启动监控"""
        if self.is_running():
            return False
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()
        logger.info(f"监控启动: {self.target_dir}")
        return True

    def stop(self) -> bool:
        """停止监控"""
        if not self.is_running():
            return False
        self._stop.set()
        self._thread.join()
        self._thread = None
        logger.info("监控停止")
        return True

    def is_running(self) -> bool:
        """检查运行状态"""
        return self._thread and self._thread.is_alive()

    def add_callback(self, name: str, callback: Callable[[Dict[str, Any]], None]):
        """添加回调"""
        self._callbacks[name] = callback

    def _loop(self):
        """监控循环"""
        self._last_time = float(time.time())
        self._last_files = self._get_files_info()
        self._last_size = sum(info['size'] for info in self._last_files.values())

        while not self._stop.is_set():
            try:
                current_files = self._get_files_info()
                current_size = sum(float(info['size']) for info in current_files.values())
                current_count = len(current_files)
                current_time = float(time.time())
                elapsed = max(current_time - self._last_time, 0.001)

                # 检测变化
                changed_files = self._detect_changes(current_files)
                size_change = current_size - self._last_size

                if changed_files or abs(size_change) > 0.001:
                    speed_mbps = abs(size_change) / (1024.0 * 1024.0) / elapsed
                    has_changed = True
                else:
                    speed_mbps = 0.0
                    has_changed = False

                if has_changed:
                    # 构建变化详情字符串
                    change_details = []
                    for change in changed_files:
                        filename = Path(change['path']).name
                        action = change['action']
                        size_mb = float(change['size_mb'])
                        size_diff = float(change.get('size_diff', 0))

                        if action == '新增':
                            change_details.append(f"📄 {filename}: {size_mb:.2f}MB / +{size_mb:.2f}MB")
                        elif action == '删除':
                            change_details.append(f"📄 {filename}: 0.00MB / -{size_mb:.2f}MB")
                        else:  # 修改
                            change_details.append(f"📄 {filename}: {size_mb:.2f}MB / {size_diff:+.2f}MB")

                    details_str = "\t\t" + "\t|\t".join(change_details) if change_details else ""
                    logger.info(f"📊 总计: {current_count}个文件 | {current_size/1024/1024:.2f}MB | 速度: {speed_mbps:.2f}MB/s{details_str}")
                # 文件无变化时不输出日志

                # 通知回调函数
                info = {
                    'total_size': current_size,
                    'total_size_mb': current_size/1024/1024,
                    'file_count': current_count,
                    'time_elapsed': elapsed,
                    'has_changed': has_changed,
                    'speed_mbps': speed_mbps,
                    'changed_files': changed_files
                }
                self._notify(info)

                self._last_files = current_files
                self._last_size = current_size
                self._last_time = current_time

            except Exception as e:
                logger.error(f"监控错误: {str(e)}")
                import traceback
                logger.error(traceback.format_exc())

            time.sleep(self.interval)

    def _get_files_info(self) -> Dict[str, Dict[str, float]]:
        """获取所有文件信息"""
        files = {}
        if not self.target_dir.exists():
            return files

        for f in self.target_dir.rglob('*'):
            if f.is_file():
                try:
                    stat = f.stat()
                    files[str(f)] = {
                        'path': str(f),
                        'size': float(stat.st_size),
                        'size_mb': float(stat.st_size) / (1024.0 * 1024.0),
                        'mtime': float(stat.st_mtime)
                    }
                except Exception:
                    pass
        return files

    def _detect_changes(self, current_files: Dict[str, Dict[str, float]]) -> list:
        """检测文件变化"""
        changes = []

        # 检测新增和修改的文件
        for path, info in current_files.items():
            if path not in self._last_files:
                changes.append({
                    'action': '新增',
                    'path': path,
                    'size_mb': float(info['size_mb']),
                    'size_diff': float(info['size_mb'])
                })
            elif abs(float(info['mtime']) - float(self._last_files[path]['mtime'])) > 0.001 or \
                 abs(float(info['size']) - float(self._last_files[path]['size'])) > 0.001:
                size_diff = float(info['size']) - float(self._last_files[path]['size'])
                changes.append({
                    'action': '修改',
                    'path': path,
                    'size_mb': float(info['size_mb']),
                    'size_diff': float(size_diff) / (1024.0 * 1024.0)
                })

        # 检测删除的文件
        for path, info in self._last_files.items():
            if path not in current_files:
                changes.append({
                    'action': '删除',
                    'path': path,
                    'size_mb': float(info['size_mb']),
                    'size_diff': -float(info['size_mb'])
                })

        return changes

    def _notify(self, info: Dict[str, Any]):
        """通知回调"""
        for name, cb in self._callbacks.items():
            try:
                cb(info)
            except Exception as e:
                logger.error(f"回调错误 {name}: {str(e)}")

# 全局监控器
_monitor = None

def start_monitor(path: str, interval: int = 2) -> bool:
    """启动全局监控"""
    global _monitor
    if _monitor is None:
        _monitor = FileMonitor(path, interval)
    return _monitor.start()

def stop_monitor() -> bool:
    """停止全局监控"""
    global _monitor
    if _monitor:
        success = _monitor.stop()
        _monitor = None
        return success
    return False

def get_monitor() -> Optional[FileMonitor]:
    """获取监控器"""
    return _monitor

def add_callback(name: str, callback: Callable[[Dict[str, Any]], None]):
    """添加回调"""
    if _monitor:
        _monitor.add_callback(name, callback)

# 清理
import atexit
atexit.register(stop_monitor)
