#!/usr/bin/env python3
"""
MySQL Processor 启动脚本
从根目录运行 src/main.py
"""

import sys
import os

# 将src目录添加到Python路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

# 导入并运行main函数
from main import main

if __name__ == "__main__":
    main()
