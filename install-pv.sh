#!/bin/bash

# pv工具安装脚本
# 支持macOS和Linux系统的自动安装

set -e

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "🔧 pv工具安装脚本"
echo "================"

# 检查是否已安装pv
if command -v pv &> /dev/null; then
    echo -e "${GREEN}✅ pv工具已安装${NC}"
    echo "版本信息：$(pv --version | head -n1)"
    exit 0
fi

echo -e "${YELLOW}⚠️  未检测到pv工具，开始安装...${NC}"

# 检测操作系统
if [[ "$OSTYPE" == "darwin"* ]]; then
    # macOS
    echo "🍎 检测到macOS系统"

    if command -v brew &> /dev/null; then
        echo "使用Homebrew安装pv..."
        brew install pv
    else
        echo -e "${RED}❌ 未检测到Homebrew，请先安装Homebrew:${NC}"
        echo "   /bin/bash -c \"\$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)\""
        exit 1
    fi

elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
    # Linux
    echo "🐧 检测到Linux系统"

    # 检测包管理器
    if command -v apt-get &> /dev/null; then
        # Ubuntu/Debian
        echo "使用apt-get安装pv..."
        sudo apt-get update
        sudo apt-get install -y pv
    elif command -v yum &> /dev/null; then
        # CentOS/RHEL
        echo "使用yum安装pv..."
        sudo yum install -y pv
    elif command -v dnf &> /dev/null; then
        # Fedora
        echo "使用dnf安装pv..."
        sudo dnf install -y pv
    elif command -v pacman &> /dev/null; then
        # Arch Linux
        echo "使用pacman安装pv..."
        sudo pacman -S pv
    elif command -v zypper &> /dev/null; then
        # openSUSE
        echo "使用zypper安装pv..."
        sudo zypper install pv
    else
        echo -e "${RED}❌ 未检测到支持的包管理器${NC}"
        echo "请手动安装pv工具"
        exit 1
    fi

else
    echo -e "${RED}❌ 不支持的操作系统: $OSTYPE${NC}"
    echo "请手动安装pv工具"
    exit 1
fi

# 验证安装
if command -v pv &> /dev/null; then
    echo -e "${GREEN}✅ pv工具安装成功！${NC}"
    echo "版本信息：$(pv --version | head -n1)"
else
    echo -e "${RED}❌ pv工具安装失败${NC}"
    exit 1
fi
