#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import subprocess
import sys
import platform

def test_mydumper():
    """测试 mydumper 和 myloader 是否可用"""
    
    print(f"操作系统: {platform.system()}")
    
    # 检查 mydumper
    result = subprocess.run(['mydumper', '--version'], capture_output=True, text=True)
    if result.returncode == 0:
        print(f"✓ mydumper 可用: {result.stdout.strip()}")
    else:
        print("✗ mydumper 未找到")
        print("请运行 ./install_mydumper.sh 安装 mydumper")
    
    # 检查 myloader
    result = subprocess.run(['myloader', '--version'], capture_output=True, text=True)
    if result.returncode == 0:
        print(f"✓ myloader 可用: {result.stdout.strip()}")
    else:
        print("✗ myloader 未找到")
        print("请运行 ./install_mydumper.sh 安装 myloader")

if __name__ == "__main__":
    test_mydumper()