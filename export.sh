#!/bin/bash

# MySQL 数据库导出脚本
# 支持实时进度显示（需要安装pv工具）

# 检查是否安装了pv工具
check_pv() {
    if ! command -v pv &> /dev/null; then
        echo "⚠️  未检测到pv工具，无法显示实时进度"
        echo "📦  安装pv工具："

        # 检测操作系统并提供安装命令
        if [[ "$OSTYPE" == "darwin"* ]]; then
            echo "   macOS: brew install pv"
        elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
            if command -v apt-get &> /dev/null; then
                echo "   Ubuntu/Debian: sudo apt-get install pv"
            elif command -v yum &> /dev/null; then
                echo "   CentOS/RHEL: sudo yum install pv"
            elif command -v dnf &> /dev/null; then
                echo "   Fedora: sudo dnf install pv"
            else
                echo "   请使用您的包管理器安装pv"
            fi
        fi

        return 1
    fi
    return 0
}

# 数据库配置
DB_HOST="161.189.137.213"
DB_PORT="8007"
DB_USER="admin"
DB_PASS="'lSKC.zGzl^RhLTqw'"
DB_NAME="p3"
DUMP_FILE="dumps/p3.sql"

# 确保dumps目录存在
mkdir -p dumps

# 构建mysqldump命令
MYSQLDUMP_CMD="mysql-client/mac/arm64/mysqldump \
  -h $DB_HOST \
  -u $DB_USER \
  -p$DB_PASS \
  --port=$DB_PORT \
  --default-character-set=utf8 \
  --set-gtid-purged=OFF \
  --skip-routines \
  --skip-triggers \
  --skip-add-locks \
  --skip-events \
  --skip-definer \
  --add-drop-database \
  --complete-insert \
  --skip-tz-utc \
  --max-allowed-packet=256M \
  --net-buffer-length=65536 \
  --extended-insert=5000 \
  --quick \
  --skip-lock-tables \
  --no-autocommit \
  --databases $DB_NAME"

# 执行导出
echo "🚀 开始导出数据库: $DB_NAME"
echo "📁 导出文件: $DUMP_FILE"

if check_pv; then
    # 使用pv显示进度
    echo "📊 使用pv显示实时进度..."
    eval $MYSQLDUMP_CMD | pv > "$DUMP_FILE"
else
    # 不使用pv
    echo "⏳ 正在导出，请稍候..."
    eval $MYSQLDUMP_CMD > "$DUMP_FILE"
fi

# 检查导出结果
EXIT_CODE=$?
if [ $EXIT_CODE -eq 0 ]; then
    echo "✅ 数据库导出成功！"
    echo "📊 导出文件大小: $(ls -lh "$DUMP_FILE" | awk '{print $5}')"
else
    echo "❌ 数据库导出失败！"
    echo "🔍 请检查："
    echo "   1. 用户名和密码是否正确"
    echo "   2. 网络连接是否正常"
    echo "   3. MySQL 服务器是否允许远程连接"
    echo "   4. 用户是否有足够权限"
    echo "   5. 磁盘空间是否充足"
fi
