import os
import shutil
import sys
import time
import concurrent.futures
import re
import configparser
from typing import List, Optional, Tuple

from colorama import Fore
from tqdm import tqdm

from base import BaseShell, Mysql
from logger_config import logger


class MyDump(BaseShell):
    """
    使用mysqldump导出数据库备份 - 重构版
    提供清晰的进度显示和结构化日志

    流式处理设计说明：
    ==================

    1. INSERT语句提取 (_iter_insert_lines):
       - 使用64KB块读取，避免大文件内存占用
       - 逐行解码处理，支持UTF-8和Latin-1编码
       - 生成器模式，按需产生INSERT INTO语句

    2. 大文件拆分 (_split_large_file):
       - 流式处理INSERT行，不收集所有数据到内存
       - current_lines只保存当前文件块内容
       - 处理完立即写入文件，及时释放内存

    3. 内存控制策略:
       - 生成器 + 逐行处理 = 恒定内存占用
       - 不缓存完整文件内容
       - 二进制模式避免编码问题

    4. 编码处理:
       - UTF-8优先，失败时回退Latin-1
       - 保留原始二进制数据的完整性
    """

    def __init__(self, mysql: Mysql, split_threshold_mb: int = 500, threads: int = 8):
        super().__init__()
        self.mysql = mysql
        self.use_pv = self._check_pv_available()
        self.split_threshold = split_threshold_mb * 1024 * 1024  # 转换为字节
        self.threads = threads

    def _check_pv_available(self):
        """检查pv工具是否可用"""
        return shutil.which('pv') is not None

    def export_db(self, database: str, dump_file: str, tables: Optional[List[str]] = None):
        """
        使用mysqldump导出数据库结构，然后使用线程池分别导出每个表的数据
        提供清晰的进度显示

        Args:
            database: 数据库名称
            dump_file: 导出文件路径
            tables: 要导出的表列表，None表示所有表
            threads: 并发导出线程数
        """
        try:
            # 确保输出目录存在
            os.makedirs(os.path.dirname(dump_file), exist_ok=True)

            mysqldump_path = self._get_mysqldump_exe()
            mysqldump_bin_dir = os.path.dirname(mysqldump_path)

            # 第一步：导出数据库结构
            if not self._export_structure(database, dump_file, mysqldump_path, mysqldump_bin_dir):
                return False

            # 第二步：获取数据库的所有表
            if tables is None or tables == ['*']:
                tables = self._get_all_tables(database)

            if not tables:
                return True

            # 第三步：导出表数据
            success_count = self._export_tables_data(database, tables, dump_file, mysqldump_path, mysqldump_bin_dir)

            if success_count == len(tables):
                return True
            else:
                logger.error(f"导出失败: {len(tables) - success_count} 个表导出失败")
                return False

        except Exception as e:
            logger.error(f"导出过程发生错误 - 数据库: {database}, 错误: {str(e)}")
            return False

    def _export_structure(self, database: str, dump_file: str, mysqldump_path: str, mysqldump_bin_dir: str) -> bool:
        """导出数据库结构"""
        try:
            cmd = (
                f'{mysqldump_path} '
                f'-h {self.mysql.db_host} '
                f'-u {self.mysql.db_user} '
                f'-p"{self.mysql.db_pass}" '
                f'--port={self.mysql.db_port} '
                f'--default-character-set=utf8 '
                f'--set-gtid-purged=OFF '
                f'--skip-routines '
                f'--skip-triggers '
                f'--skip-add-locks '
                f'--disable-keys '
                f'--skip-events '
                f'--skip-set-charset '
                f'--add-drop-database '
                f'--extended-insert '
                f'--complete-insert '
                f'--quick '
                f'--no-autocommit '
                f'--single-transaction '
                f'--skip-lock-tables '
                f'--no-autocommit '
                f'--compress '
                f'--skip-tz-utc '
                f'--max-allowed-packet=256M '
                f'--net-buffer-length=1048576 '
                f'--no-data '
                f'--skip-set-charset '
                f'--skip-comments '
                f'--compact '
                f'--set-gtid-purged=OFF '
                f'--databases {database}'
            )

            full_command = f'{cmd} > {dump_file}'
            success, exit_code, output = self._exe_command(full_command, cwd=mysqldump_bin_dir)

            if not success:
                raise RuntimeError(f"数据库结构导出失败，exit code: {exit_code}")

            return True

        except Exception as e:
            logger.error(f"数据库结构导出失败 - 数据库: {database}, 错误: {str(e)}")
            return False

    def _export_tables_data(self, database: str, tables: List[str], dump_file: str,
                          mysqldump_path: str, mysqldump_bin_dir: str) -> int:
        """并发导出所有表的数据"""
        db_folder = os.path.join(os.path.dirname(dump_file), database)
        os.makedirs(db_folder, exist_ok=True)

        success_count = 0
        failed_tables = []
        exported_total_size = 0.0  # 已导出的总大小

        # 使用tqdm的并发支持来正确显示进度
        with tqdm(total=len(tables), desc=f"导出 {database} 表数据", unit="表", dynamic_ncols=True, disable=False,
                  file=sys.stdout, ascii=True) as pbar:
            def update_progress(result, table_name):
                nonlocal exported_total_size
                if result['success']:
                    exported_total_size = self._get_exported_files_size(db_folder)
                    speed = f"{result['original_size_mb'] / result['duration']:.1f}MB/s" if result['duration'] > 0 else "0.0MB/s"
                    pbar.set_postfix_str(f"✓ {table_name} ({result['original_size_mb']:.1f}MB, {speed}) 已导出: {exported_total_size:.1f}MB")
                else:
                    exported_total_size = self._get_exported_files_size(db_folder)
                    pbar.set_postfix_str(f"✗ {table_name} 已导出: {exported_total_size:.1f}MB")
                pbar.update(1)
                return result

            with concurrent.futures.ThreadPoolExecutor(max_workers=self.threads) as pool:
                # 提交所有导出任务
                futures = []
                for table in tables:
                    table_file = os.path.join(db_folder, f"{table}.sql")
                    future = pool.submit(
                        self._export_single_table,
                        database, table, table_file,
                        mysqldump_path, mysqldump_bin_dir,
                    )
                    # 添加回调来更新进度
                    future.add_done_callback(
                        lambda f, t=table: update_progress(f.result(), t)
                    )
                    futures.append(future)

                # 等待所有任务完成
                concurrent.futures.wait(futures)

                # 收集最终结果
                for future, table in zip(futures, tables):
                    try:
                        result = future.result()
                        if result['success']:
                            success_count += 1
                        else:
                            failed_tables.append(table)
                            logger.error(f"表导出失败 - 数据库: {database}, 表: {table}, 错误: {result['error']}")
                    except Exception as e:
                        failed_tables.append(table)
                        logger.error(f"表导出异常 - 数据库: {database}, 表: {table}, 错误: {str(e)}")

        return success_count

    def _get_exported_files_size(self, db_folder: str) -> float:
        """获取已导出的SQL文件总大小（MB）"""
        try:
            total_size = 0.0
            if os.path.exists(db_folder):
                for filename in os.listdir(db_folder):
                    if filename.endswith('.sql'):
                        file_path = os.path.join(db_folder, filename)
                        if os.path.isfile(file_path):
                            total_size += os.path.getsize(file_path) / 1024 / 1024
            return total_size
        except Exception as e:
            logger.error(f"计算导出文件总大小失败: {str(e)}")
            return 0.0

    def _export_single_table(self, database: str, table: str, table_file: str,
                             mysqldump_path: str, mysqldump_bin_dir: str) -> dict:
        """导出单个表的数据"""
        start_time = time.time()

        try:
            cmd = (
                f'{mysqldump_path} '
                f'-h {self.mysql.db_host} '
                f'-u {self.mysql.db_user} '
                f'-p"{self.mysql.db_pass}" '
                f'--port={self.mysql.db_port} '
                f'--default-character-set=utf8 '
                f'--set-gtid-purged=OFF '
                f'--skip-routines '
                f'--skip-triggers '
                f'--skip-add-locks '
                f'--skip-events '
                f'--skip-set-charset '
                f'--no-autocommit '
                f'--single-transaction '
                f'--skip-lock-tables '
                f'--no-autocommit '
                f'--no-create-info '
                f'--skip-set-charset '
                # f'--skip-comments '
                f'--compact '
                f'--set-gtid-purged=OFF '
                f'--quick '
                f'{database} {table}'
            )

            # 直接导出到表名.sql文件
            full_command = f'{cmd} > {table_file}'

            success, exit_code, output = self._exe_command(
                full_command, cwd=mysqldump_bin_dir
            )

            if not success:
                raise RuntimeError(f"表数据导出失败，exit code: {exit_code}")

            # 处理文件
            if os.path.exists(table_file):
                file_size = os.path.getsize(table_file)

                # 检查文件是否包含INSERT INTO语句
                has_insert = self._check_has_insert_sql(table_file)

                if not has_insert:
                    # 如果没有INSERT INTO语句，删除文件
                    os.remove(table_file)
                    return {
                        'success': True,
                        'duration': time.time() - start_time,
                        'size_mb': 0,
                        'original_size_mb': 0
                    }

                # 处理大文件拆分
                if file_size > self.split_threshold:
                    temp_file = f"{table_file}.tmp"
                    os.rename(table_file, temp_file)
                    self._split_large_file(temp_file, table_file, self.split_threshold)
                    os.remove(temp_file)
                    file_size_mb = file_size / 1024 / 1024
                else:
                    # 小文件，添加头尾信息
                    self._add_header_footer_to_file(table_file)
                    file_size_mb = file_size / 1024 / 1024

                return {
                    'success': True,
                    'duration': time.time() - start_time,
                    'size_mb': file_size_mb,
                    'original_size_mb': file_size_mb
                }
            else:
                # 空文件，不创建
                return {
                    'success': True,
                    'duration': time.time() - start_time,
                    'size_mb': 0
                }

        except Exception as e:
            # 清理可能存在的文件
            if os.path.exists(table_file):
                os.remove(table_file)
            return {
                'success': False,
                'duration': time.time() - start_time,
                'error': str(e),
                'original_size_mb': 0
            }

    def _get_all_tables(self, database: str) -> List[str]:
        """获取数据库中的所有表名"""
        try:
            import pymysql
            connection = pymysql.connect(
                host=self.mysql.db_host,
                user=self.mysql.db_user,
                password=self.mysql.db_pass,
                port=int(self.mysql.db_port),
                database=database,
                charset='utf8'
            )

            with connection.cursor() as cursor:
                cursor.execute("SHOW TABLES")
                tables = [row[0] for row in cursor.fetchall()]

            connection.close()
            return sorted(tables)

        except Exception as e:
            logger.error(f"获取表列表失败 - 数据库: {database}, 错误: {str(e)}")
            return []

    def _split_large_file(self, temp_file: str, base_filename: str, max_size: int):
        """使用流式处理拆分大文件，避免内存占用

        流式拆分策略：
        1. 直接处理生成器：不收集所有INSERT行到内存
        2. 分块写入：current_lines只保存当前文件内容
        3. 及时释放：写完一个文件立即清空缓存
        4. 编码兼容：保留UTF-8/Latin-1处理逻辑

        内存控制：
        - 峰值内存 = 单个文件最大内容 + 64KB缓冲区
        - 与原始文件大小无关，适合处理GB级文件
        """
        base_name_without_ext = os.path.splitext(base_filename)[0]
        ext = os.path.splitext(base_filename)[1]

        # 转换为字节
        max_bytes = max_size
        file_counter = 1

        # 定义SQL头尾语句
        header_lines = [
            "set foreign_key_checks = 0;",
            "set unique_checks = 0;",
            "set autocommit=0;",
            ""
        ]
        footer_lines = [
            "",
            "commit;",
            "set foreign_key_checks = 1;",
            "set unique_checks = 1;"
        ]

        header_bytes = '\n'.join(header_lines).encode('utf-8')
        footer_bytes = '\n'.join(footer_lines).encode('utf-8')

        # 计算头尾占用的空间
        header_size = len(header_bytes)
        footer_size = len(footer_bytes)
        effective_max_bytes = max_bytes - header_size - footer_size

        try:
            # 流式处理INSERT INTO行，避免内存占用
            insert_lines = self._iter_insert_lines(temp_file)

            # 开始拆分文件 - 使用真正的流式处理
            current_lines = []
            current_size = 0

            for line in insert_lines:
                # 处理每一行 - 保留原有的编码处理逻辑
                if not line.endswith('\n'):
                    line += '\n'
                try:
                    byte_line = line.encode('utf-8')
                except UnicodeEncodeError:
                    byte_line = line.encode('latin-1')

                line_size = len(byte_line)

                # 检查是否需要创建新文件
                if current_size + line_size > effective_max_bytes and current_lines:
                    # 写入当前文件
                    current_output_file = f"{base_name_without_ext}.part{file_counter:03d}{ext}"
                    with open(current_output_file, 'wb') as output_handle:
                        output_handle.write(header_bytes)
                        for line_data in current_lines:
                            output_handle.write(line_data)
                        output_handle.write(footer_bytes)

                    # 重置计数器
                    file_counter += 1
                    current_lines = []
                    current_size = 0

                current_lines.append(byte_line)
                current_size += line_size

            # 写入最后一个文件
            if current_lines:
                current_output_file = f"{base_name_without_ext}.part{file_counter:03d}{ext}"
                with open(current_output_file, 'wb') as output_handle:
                    output_handle.write(header_bytes)
                    for line_data in current_lines:
                        output_handle.write(line_data)
                    output_handle.write(footer_bytes)
                file_counter += 1

            return file_counter - 1

        except Exception as e:
            logger.error(f"拆分文件时发生错误: {str(e)}")
            raise

    def _check_has_insert_sql(self, file_path: str) -> bool:
        """检查SQL文件是否包含INSERT INTO语句"""
        try:
            for _ in self._iter_insert_lines(file_path):
                return True
            return False
        except Exception as e:
            logger.error(f"检查SQL文件时发生错误: {str(e)}")
            return False

    def _iter_insert_lines(self, file_path: str):
        """生成器中逐个产生INSERT INTO行，实现真正的流式处理

        流式处理机制：
        1. 64KB块读取：避免一次性加载大文件到内存
        2. 逐行解码：支持UTF-8和Latin-1编码回退
        3. 生成器模式：按需产生INSERT语句，内存占用恒定
        4. 二进制处理：保留原始数据完整性

        Args:
            file_path: SQL文件路径

        Yields:
            str: 每个INSERT INTO行（已解码为字符串）
        """
        try:
            with open(file_path, 'rb') as f:
                buffer = b''
                while True:
                    chunk = f.read(65536)  # 64KB chunks
                    if not chunk:
                        if buffer:
                            lines = buffer.split(b'\n')
                            for line_bytes in lines:
                                if line_bytes.strip():
                                    try:
                                        line = line_bytes.decode('utf-8').strip()
                                    except UnicodeDecodeError:
                                        line = line_bytes.decode('latin-1').strip()
                                    if line.upper().startswith('INSERT INTO'):
                                        yield line
                        break

                    buffer += chunk
                    lines = buffer.split(b'\n')
                    buffer = lines[-1]

                    for line_bytes in lines[:-1]:
                        line_bytes = line_bytes.strip()
                        if line_bytes:
                            try:
                                line = line_bytes.decode('utf-8').strip()
                            except UnicodeDecodeError:
                                line = line_bytes.decode('latin-1').strip()
                            if line.upper().startswith('INSERT INTO'):
                                yield line
        except Exception as e:
            logger.error(f"收集INSERT INTO行时发生错误: {str(e)}")
            raise

    def _add_header_footer_to_file(self, file_path: str) -> bool:
        """给文件添加头尾信息，使用流式处理保留INSERT INTO语句

        流式处理特点：
        1. 复用 _iter_insert_lines 生成器，不重复内存占用
        2. 临时文件方式，保证数据安全
        3. 逐行写入，内存占用恒定
        4. 保持原始编码处理逻辑
        """
        try:
            # 准备头尾内容
            header_lines = [
                "set foreign_key_checks = 0;",
                "set unique_checks = 0;",
                "set autocommit=0;",
                ""
            ]
            footer_lines = [
                "",
                "commit;",
                "set foreign_key_checks = 1;",
                "set unique_checks = 1;"
            ]

            header = '\n'.join(header_lines)
            footer = '\n'.join(footer_lines)

            # 使用临时文件方式处理
            temp_file = file_path + '.tmp'

            # 收集所有INSERT INTO行
            insert_lines = self._iter_insert_lines(file_path)

            # 写入处理后的内容
            with open(temp_file, 'w', encoding='utf-8') as out_f:
                out_f.write(header)
                for line in insert_lines:
                    out_f.write('\n' + line)
                out_f.write(footer)

            # 替换原文件
            os.replace(temp_file, file_path)
            return True

        except Exception as e:
            logger.error(f"添加头尾信息时发生错误: {str(e)}")
            if os.path.exists(temp_file):
                os.remove(temp_file)
            return False
