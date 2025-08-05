#!/usr/bin/env python3
"""
统一的日志配置模块
为整个项目提供一致的日志格式和配置
"""

import logging
import sys
from typing import Optional


def setup_logger(
    name: Optional[str] = None,
    level: int = logging.INFO,
    format_string: Optional[str] = None
) -> logging.Logger:
    """
    设置并返回一个配置好的logger

    Args:
        name: logger名称，如果为None则使用根logger
        level: 日志级别，默认为INFO
        format_string: 自定义格式字符串

    Returns:
        logging.Logger: 配置好的logger实例
    """
    if format_string is None:
        format_string = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'

    # 创建logger
    logger = logging.getLogger(name)

    # 避免重复添加handler
    if logger.handlers:
        return logger

    # 设置日志级别
    logger.setLevel(level)

    # 创建控制台handler
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(level)

    # 创建formatter
    formatter = logging.Formatter(format_string)
    handler.setFormatter(formatter)

    # 添加handler到logger
    logger.addHandler(handler)

    return logger


# 预定义的logger实例
logger = setup_logger("mysql-processor")

# 导出函数供其他模块使用
__all__ = ['setup_logger', 'logger']
