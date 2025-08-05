#!/bin/bash

# MySQL dumps 目录实时监控脚本
# 每2秒在终端显示 dumps 目录下的文件信息
# 不记录日志，纯终端显示

# 设置 dumps 目录路径
DUMPS_DIR="./dumps"

# 检查 dumps 目录是否存在
if [ ! -d "$DUMPS_DIR" ]; then
    echo "错误: dumps 目录不存在: $DUMPS_DIR"
    echo "正在创建 dumps 目录..."
    mkdir -p "$DUMPS_DIR"
fi

echo "=========================================="
echo "实时监控 dumps 目录 (每2秒更新)"
echo "目录路径: $(pwd)/$DUMPS_DIR"
echo "按 Ctrl+C 停止监控"
echo "=========================================="

# 使用无限循环每2秒更新一次
while true; do
    clear
    echo "=========================================="
    echo "dumps 目录实时监控 - $(date '+%Y-%m-%d %H:%M:%S')"
    echo "=========================================="

    if [ -d "$DUMPS_DIR" ]; then
        echo ""
        echo "文件列表:"
        echo "------------------------------------------"

        # 显示文件详细信息
        if [ "$(ls -A "$DUMPS_DIR")" ]; then
            printf "%-40s %10s %20s\n" "文件名" "大小" "修改时间"
            echo "------------------------------------------"

            for file in "$DUMPS_DIR"/*; do
                if [ -f "$file" ]; then
                    filename=$(basename "$file")
                    size=$(du -h "$file" | cut -f1)
                    mtime=$(stat -c "%y" "$file" 2>/dev/null || stat -f "%Sm" "$file" 2>/dev/null || echo "未知")
                    printf "%-40s %10s %20s\n" "$filename" "$size" "$mtime"
                fi
            done

            echo ""
            echo "统计信息:"
            echo "文件总数: $(ls -1 "$DUMPS_DIR" | wc -l)"
            echo "总大小: $(du -sh "$DUMPS_DIR" | cut -f1)"
        else
            echo "目录为空"
        fi
    else
        echo "错误: dumps 目录不存在"
    fi

    echo ""
    echo "=========================================="
    echo "下次更新: $(date -v+2S '+%H:%M:%S')"
    echo "=========================================="

    sleep 2
done
