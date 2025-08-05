#!/usr/bin/env python3
"""
MyLoader 数据库导入类
使用 myloader 工具进行高性能并行数据库导入
"""

import os
import shutil
import sys
from pathlib import Path
from typing import List, Optional

from base import BaseShell, Mysql


class MyLoader(BaseShell):
    """
    使用 myloader 进行高性能并行数据库导入
    支持多线程、压缩文件导入等高级特性
    """

    def __init__(self, mysql: Mysql, max_allowed_packet: str = "256M", net_buffer_length: str = "65536"):
        super().__init__()
        self.mysql = mysql
        self.max_allowed_packet = max_allowed_packet
        self.net_buffer_length = net_buffer_length

    def _get_myloader_exe(self) -> str:
        """获取 myloader 可执行文件完整路径"""
        import shutil
        # 优先使用系统安装的版本
        system_path = shutil.which('myloader')
        if system_path:
            return system_path
        return '/opt/homebrew/bin/myloader'  # macOS brew 默认路径

    def import_databases(
        self,
        input_dir: str,
        threads: int = 8,
        overwrite_tables: bool = False,
        disable_keys: bool = True
    ) -> bool:
        """
        使用 myloader 导入数据库

        Args:
            input_dir: 输入目录（包含 mydumper 导出的文件）
            threads: 并行线程数
            overwrite_tables: 是否覆盖已存在的表
            enable_binlog: 是否启用 binlog
            skip_triggers: 是否跳过触发器
            skip_routines: 是否跳过存储过程和函数

        Returns:
            bool: 导入是否成功
        """
        try:
            input_path = Path(input_dir)
            if not input_path.exists():
                raise RuntimeError(f"输入目录不存在: {input_dir}")

            myloader_path = self._get_myloader_exe()

            # 构建 myloader 命令
            cmd_parts = [
                myloader_path,
                f"--host={self.mysql.db_host}",
                f"--port={self.mysql.db_port}",
                f"--user={self.mysql.db_user}",
                f"--password={self.mysql.db_pass}",
                f"--directory={input_dir}",
                f"--threads={threads}",
                f"--max-threads-for-index-creation={max_threads_for_index_creation}",
                f"--max-threads-for-post-creation={max_threads_for_post_creation}",
                f"--max-rows={max_rows_per_statement}",
                f"--commit-every={commit_every}",
                "--verbose=3",
                "--disable-binlog",
                "--overwrite-tables"
            ]

            # 添加导入选项
            if overwrite_tables:
                cmd_parts.append("--overwrite-tables")



            if skip_triggers:
                cmd_parts.append("--skip-triggers")

            if disable_keys:
                cmd_parts.append("--disable-keys")

            # 构建完整命令
            cmd = " ".join(cmd_parts)

            print("正在使用 myloader 导入数据库...")
            print(f"输入目录: {input_dir}")
            print(f"并行线程: {threads}")

            # 使用 BaseShell 的 _exe_command 方法执行命令
            success, exit_code, output = self._exe_command(cmd)

            if not success:
                raise RuntimeError(f"myloader 导入失败，exit code: {exit_code}")

            print('✅ 数据库导入成功')
            return True

        except RuntimeError as e:
            raise e
        except Exception as e:
            raise RuntimeError(f"导入过程发生错误: {str(e)}")

    def import_database(
        self,
        input_dir: str,
        source_database: str,
        target_database: Optional[str] = None,
        threads: int = 8,
        disable_keys: bool = True,
        **kwargs
) -> bool:
        """
        导入单个数据库

        Args:
            input_dir: 输入目录
            source_database: 源数据库名（导出时的数据库名）
            target_database: 目标数据库名（导入时的数据库名），如果为None则使用源数据库名
            **kwargs: 其他导入参数

        Returns:
            bool: 导入是否成功
        """
        if target_database is None:
            target_database = source_database

        # 构建 myloader 命令，使用 --source-db 和 --database 参数
        myloader_path = self._get_myloader_exe()

        cmd_parts = [
            myloader_path,
            f"--host={self.mysql.db_host}",
            f"--port={self.mysql.db_port}",
            f"--user={self.mysql.db_user}",
            f"--password={self.mysql.db_pass}",
            f"--directory={input_dir}",
            f"--source-db={source_database}",
            f"--database={target_database}",
            f"--threads={threads}",
            "--verbose=3",
            "--disable-binlog",
            "--overwrite-tables"
        ]

        # 添加其他选项
        if kwargs.get('overwrite_tables', False):
            cmd_parts.append("--overwrite-tables")

        if not kwargs.get('enable_binlog', False):
            cmd_parts.append("--disable-binlog")

        if kwargs.get('skip_triggers', False):
            cmd_parts.append("--skip-triggers")

        if disable_keys:
            cmd_parts.append("--disable-keys")

        cmd = " ".join(cmd_parts)

        print(f"正在导入数据库 {source_database} -> {target_database}...")
        success, exit_code, output = self._exe_command(cmd)

        if not success:
            raise RuntimeError(f"数据库导入失败，exit code: {exit_code}")

        print('✅ 数据库导入成功')
        return True

    def validate_backup(self, input_dir: str) -> bool:
        """
        验证 mydumper 备份的完整性

        Args:
            input_dir: 备份目录

        Returns:
            bool: 备份是否有效
        """
        input_path = Path(input_dir)
        if not input_path.exists():
            return False

        # 检查必要的文件
        required_files = ['metadata']
        metadata_files = list(input_path.glob("*.metadata"))

        if not metadata_files:
            print("❌ 未找到 metadata 文件，可能不是有效的 mydumper 备份")
            return False

        # 检查 SQL 文件
        sql_files = list(input_path.glob("*.sql*"))
        if not sql_files:
            print("❌ 未找到 SQL 文件")
            return False

        print(f"✅ 备份验证通过，找到 {len(sql_files)} 个 SQL 文件")
        return True

    def get_import_info(self, input_dir: str) -> dict:
        """
        获取导入信息

        Args:
            input_dir: 导入目录

        Returns:
            dict: 导入信息统计
        """
        input_path = Path(input_dir)
        if not input_path.exists():
            return {}

        # 统计文件信息
        sql_files = list(input_path.glob("*.sql*"))
        metadata_files = list(input_path.glob("*.metadata"))

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
            "directory_size": sum(f.stat().st_size for f in input_path.rglob("*") if f.is_file()),
            "import_path": str(input_path)
        }
