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
    """

    def __init__(self, mysql: Mysql):
        super().__init__()
        self.mysql = mysql
        self.use_pv = self._check_pv_available()
        self.split_threshold = self._get_split_threshold()

    def _check_pv_available(self):
        """检查pv工具是否可用"""
        return shutil.which('pv') is not None

    def _get_split_threshold(self):
        """从配置文件读取文件拆分阈值"""
        try:
            config = configparser.ConfigParser()
            config_path = os.path.join(os.path.dirname(__file__), '..', 'config.ini')
            config.read(config_path, encoding='utf-8')
            threshold = config.getint('global', 'split_threshold', fallback=500)
            return threshold * 1024 * 1024  # 转换为字节
        except Exception:
            return 500 * 1024 * 1024  # 默认500MB

    def export_db(self, database: str, dump_file: str, tables: Optional[List[str]] = None, threads: int = 8):
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
            success_count = self._export_tables_data(database, tables, dump_file, mysqldump_path, mysqldump_bin_dir, threads)

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
                          mysqldump_path: str, mysqldump_bin_dir: str, threads: int = 8) -> int:
        """并发导出所有表的数据"""
        db_folder = os.path.join(os.path.dirname(dump_file), database)
        os.makedirs(db_folder, exist_ok=True)

        success_count = 0
        failed_tables = []
        exported_total_size = 0.0  # 已导出的总大小



        # 使用tqdm的并发支持来正确显示进度
        with tqdm(total=len(tables), desc=f"导出 {database} 表数据", unit="表", dynamic_ncols=True, disable=False, file=sys.stdout, ascii=True) as pbar:
            def update_progress(result, table_name):
                nonlocal exported_total_size
                if result['success']:
                    exported_total_size = self._get_exported_files_size(db_folder)
                    pbar.set_postfix_str(f"✓ {table_name} ({result['original_size_mb']:.1f}MB) 已导出: {exported_total_size:.1f}MB")
                else:
                    exported_total_size = self._get_exported_files_size(db_folder)
                    pbar.set_postfix_str(f"✗ {table_name} 已导出: {exported_total_size:.1f}MB")
                pbar.update(1)
                return result

            with concurrent.futures.ThreadPoolExecutor(max_workers=threads) as pool:
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
                has_insert = self._check_and_process_sql_file(table_file)

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
        """使用二进制模式拆分文件，避免编码问题，只保留INSERT INTO开头的行"""
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

        # 使用二进制模式逐行读取，避免编码问题
        def insert_lines_generator():
            """生成器：只产生INSERT INTO开头的行"""
            try:
                with open(temp_file, 'rb') as f:
                    buffer = b''
                    while True:
                        chunk = f.read(65536)  # 64KB chunks
                        if not chunk:
                            if buffer:
                                # 处理最后剩余的数据
                                lines = buffer.split(b'\n')
                                for line_bytes in lines:
                                    if line_bytes.strip():
                                        yield line_bytes
                            break

                        buffer += chunk
                        lines = buffer.split(b'\n')
                        buffer = lines[-1]  # 保存不完整的行

                        for line_bytes in lines[:-1]:
                            line_bytes = line_bytes.strip()
                            if line_bytes:
                                # 检查是否是INSERT INTO开头
                                try:
                                    line = line_bytes.decode('utf-8').strip()
                                except UnicodeDecodeError:
                                    line = line_bytes.decode('latin-1').strip()

                                if line.upper().startswith('INSERT INTO'):
                                    yield line_bytes
            except Exception as e:
                logger.error(f"读取文件时发生错误: {str(e)}")
                raise

        output_handle = None
        try:
            # 收集所有INSERT INTO行
            all_lines = list(insert_lines_generator())

            if not all_lines:
                # 如果没有INSERT INTO行，不创建任何文件
                return

            # 开始拆分文件
            current_lines = []
            current_size = 0

            for line in all_lines:
                line_with_newline = line
                if not line.endswith(b'\n'):
                    line_with_newline += b'\n'

                line_size = len(line_with_newline)

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

                current_lines.append(line_with_newline)
                current_size += line_size

            # 写入最后一个文件
            if current_lines:
                current_output_file = f"{base_name_without_ext}.part{file_counter:03d}{ext}"
                with open(current_output_file, 'wb') as output_handle:
                    output_handle.write(header_bytes)
                    for line_data in current_lines:
                        output_handle.write(line_data)
                    output_handle.write(footer_bytes)

        except Exception as e:
            logger.error(f"拆分文件时发生错误: {str(e)}")
            raise

    def _check_and_process_sql_file(self, file_path: str) -> bool:
        """检查SQL文件是否包含INSERT INTO语句，并添加指定的SQL语句"""
        try:
            # 使用临时文件方式处理大文件
            temp_file = file_path + '.tmp'

            # 首先检查是否包含INSERT INTO
            has_insert = False
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
                                    if 'INSERT INTO' in line.upper():
                                        has_insert = True
                                        break
                        break

                    buffer += chunk
                    lines = buffer.split(b'\n')
                    buffer = lines[-1]

                    for line_bytes in lines[:-1]:
                        if line_bytes.strip():
                            try:
                                line = line_bytes.decode('utf-8').strip()
                            except UnicodeDecodeError:
                                line = line_bytes.decode('latin-1').strip()
                            if 'INSERT INTO' in line.upper():
                                has_insert = True
                                break
                        if has_insert:
                            break
                    if has_insert:
                        break

            if not has_insert:
                return False

            # 准备头尾内容
            header = """set foreign_key_checks = 0;
set unique_checks = 0;
set autocommit=0;

"""
            footer = """
commit;
set foreign_key_checks = 1;
set unique_checks = 1;
"""

            # 使用流式处理写入新内容
            with open(temp_file, 'w', encoding='utf-8') as out_f:
                out_f.write(header)

                # 逐行复制原文件内容
                with open(file_path, 'rb') as in_f:
                    buffer = b''
                    while True:
                        chunk = in_f.read(65536)
                        if not chunk:
                            if buffer:
                                try:
                                    content = buffer.decode('utf-8')
                                except UnicodeDecodeError:
                                    content = buffer.decode('latin-1')
                                out_f.write(content)
                            break

                        buffer += chunk
                        lines = buffer.split(b'\n')
                        buffer = lines[-1]

                        for line_bytes in lines[:-1]:
                            try:
                                line = line_bytes.decode('utf-8')
                            except UnicodeDecodeError:
                                line = line_bytes.decode('latin-1')
                            out_f.write(line + '\n')

                out_f.write(footer)

            # 替换原文件
            os.replace(temp_file, file_path)
            return True

        except Exception as e:
            logger.error(f"处理SQL文件时发生错误: {str(e)}")
            if os.path.exists(temp_file):
                os.remove(temp_file)
            return False
