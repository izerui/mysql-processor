#!/usr/bin/env python3
"""
MyDumper 数据库导出类
使用 mydumper 工具进行高性能并行数据库导出
"""

import os
import shutil
import sys
from pathlib import Path
from typing import List, Optional

from base import BaseShell, Mysql


class MyDumper(BaseShell):
    """
    使用 mydumper 进行高性能并行数据库导出
    支持多线程、压缩、分块等高级特性
    """

    def __init__(self, mysql: Mysql):
        super().__init__()
        self.mysql = mysql

    def _get_mydumper_exe(self) -> str:
        """获取 mydumper 可执行文件完整路径"""
        import shutil
        # 优先使用系统安装的版本
        system_path = shutil.which('mydumper')
        if system_path:
            return system_path
        return '/opt/homebrew/bin/mydumper'  # macOS brew 默认路径

    def export_databases(
        self,
        databases: List[str],
        output_dir: str,
        threads: int = 8,
        compress: bool = True,
        rows: int = 500000,
        chunk_filesize: int = 256,
        no_lock: bool = True
    ) -> bool:
        """
        使用 mydumper 导出数据库

        Args:
            databases: 数据库列表
            output_dir: 输出目录
            threads: 并行线程数（默认8，提升性能）
            compress: 是否压缩输出（默认True，节省空间）
            rows: 每个文件的最大行数（默认50万，平衡文件大小和性能）
            chunk_filesize: 每个文件的最大大小(MB)（默认256MB，大文件减少IO）
            no_lock: 是否避免锁表（默认True，避免影响业务）

        Returns:
            bool: 导出是否成功
        """
        try:
            # 确保输出目录存在
            output_path = Path(output_dir)
            output_path.mkdir(parents=True, exist_ok=True)

            mydumper_path = self._get_mydumper_exe()

            # 构建 mydumper 命令
            cmd_parts = [
                mydumper_path,
                f"--host={self.mysql.db_host}",
                f"--port={self.mysql.db_port}",
                f"--user={self.mysql.db_user}",
                f"--password={self.mysql.db_pass}",
                f"--outputdir={output_dir}",
                f"--threads={threads}",
                f"--rows={rows}",
                f"--chunk-filesize={chunk_filesize}",
                "--verbose=3",
                "--sync-thread-lock-mode=NO_LOCK"
            ]

            # 添加数据库列表
            for db in databases:
                cmd_parts.append(f"--database={db}")

            # 添加优化选项
            # 添加选项
            if compress:
                cmd_parts.append("--compress")
            if no_lock:
                cmd_parts.append("--sync-thread-lock-mode=NO_LOCK")

            # 构建完整命令
            cmd = " ".join(cmd_parts)

            print("正在使用 mydumper 导出数据库...")
            print(f"目标数据库: {', '.join(databases)}")
            print(f"输出目录: {output_dir}")
            print(f"并行线程: {threads}")
            print(f"分块大小: {chunk_filesize}MB")
            print(f"每文件行数: {rows}")

            # 使用 BaseShell 的 _exe_command 方法执行命令
            success, exit_code, output = self._exe_command(cmd)

            if not success:
                raise RuntimeError(f"mydumper 导出失败，exit code: {exit_code}")

            print('✅ 数据库导出成功')
            return True

        except RuntimeError as e:
            raise e
        except Exception as e:
            raise RuntimeError(f"导出过程发生错误: {str(e)}")

    def export_database(
        self,
        database: str,
        output_dir: str,
        tables: Optional[List[str]] = None,
        **kwargs
    ) -> bool:
        """
        导出单个数据库

        Args:
            database: 数据库名
            output_dir: 输出目录
            tables: 指定表名列表，None表示所有表
            **kwargs: 其他导出参数

        Returns:
            bool: 导出是否成功
        """
        if tables:
            # 如果指定了表，使用 --tables-list 参数
            kwargs['tables_list'] = ",".join(tables)

        return self.export_databases([database], output_dir, **kwargs)

    def export_all_databases(
        self,
        output_dir: str,
        exclude_databases: Optional[List[str]] = None,
        **kwargs
    ) -> bool:
        """
        导出所有数据库

        Args:
            output_dir: 输出目录
            exclude_databases: 排除的数据库列表
            **kwargs: 其他导出参数

        Returns:
            bool: 导出是否成功
        """
        # 获取所有数据库列表
        all_dbs = self._get_all_databases()

        if exclude_databases:
            databases = [db for db in all_dbs if db not in exclude_databases]
        else:
            databases = all_dbs

        return self.export_databases(databases, output_dir, **kwargs)

    def _get_all_databases(self) -> List[str]:
        """获取所有数据库列表"""
        # 这里可以通过查询 information_schema 获取所有数据库
        # 暂时返回空列表，实际使用时需要实现
        return []

    def get_export_info(self, output_dir: str) -> dict:
        """
        获取导出信息

        Args:
            output_dir: 导出目录

        Returns:
            dict: 导出信息统计
        """
        output_path = Path(output_dir)
        if not output_path.exists():
            return {}

        # 统计文件信息
        sql_files = list(output_path.glob("*.sql*"))
        metadata_files = list(output_path.glob("*.metadata"))

        # 从 metadata 文件中提取数据库信息
        databases = set()
        for metadata_file in metadata_files:
            if metadata_file.name.endswith('.metadata'):
                db_name = metadata_file.name.replace('.metadata', '')
                databases.add(db_name)

        return {
            "total_files": len(sql_files),
            "metadata_files": len(metadata_files),
            "databases": list(databases),
            "directory_size": sum(f.stat().st_size for f in output_path.rglob("*") if f.is_file()),
            "export_path": str(output_path)
        }
