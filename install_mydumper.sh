#!/bin/bash

# mydumper 安装脚本

set -e

echo "开始安装 mydumper..."

# 检测操作系统
if [[ "$OSTYPE" == "linux-gnu"* ]]; then
    # Linux
    if command -v apt-get &> /dev/null; then
        echo "检测到 Ubuntu/Debian 系统，使用 apt 安装..."
        sudo apt update
        sudo apt install -y mydumper
    elif command -v yum &> /dev/null; then
        echo "检测到 CentOS/RHEL 系统，使用 yum 安装..."
        sudo yum install -y epel-release
        sudo yum install -y mydumper
    else
        echo "未检测到支持的包管理器，请手动安装 mydumper"
        exit 1
    fi
elif [[ "$OSTYPE" == "darwin"* ]]; then
    # macOS
    if command -v brew &> /dev/null; then
        echo "检测到 macOS 系统，使用 Homebrew 安装..."
        brew install mydumper
    else
        echo "请先安装 Homebrew: https://brew.sh"
        exit 1
    fi
else
    echo "不支持的操作系统: $OSTYPE"
    exit 1
fi

# 验证安装
if command -v mydumper &> /dev/null && command -v myloader &> /dev/null; then
    echo "mydumper 和 myloader 安装成功！"
    mydumper --version
    myloader --version
else
    echo "安装失败，请检查错误信息"
    exit 1
fi