import os
import shutil
import sys
import time
import concurrent.futures
import re
import configparser
from typing import List, Optional

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

        # 使用tqdm的并发支持来正确显示进度
        with tqdm(total=len(tables), desc=f"导出 {database} 表数据", unit="表") as pbar:
            def update_progress(result, table_name):
                if result['success']:
                    # pbar.set_postfix_str(f"✓ {table_name} ({result['size_mb']:.1f}MB)")
                    pbar.write(f"✓ {table_name} ({result['size_mb']:.1f}MB)")
                else:
                    pbar.write(f"✗ {table_name}")
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
                        1, 1  # 这些参数在进度显示中不再需要
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

    def _export_single_table(self, database: str, table: str, table_file: str,
                           mysqldump_path: str, mysqldump_bin_dir: str,
                           current_num: int, total_tables: int) -> dict:
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
                f'--disable-keys '
                f'--skip-events '
                f'--skip-set-charset '
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
                f'--no-create-info '
                f'--skip-set-charset '
                f'--skip-comments '
                f'--compact '
                f'--set-gtid-purged=OFF '
                f'--quick '
                f'{database} {table}'
            )

            # 先导出到临时文件
            temp_file = f"{table_file}.tmp"
            full_command = f'{cmd} > {temp_file}'

            success, exit_code, output = self._exe_command(
                full_command, cwd=mysqldump_bin_dir
            )

            if not success:
                raise RuntimeError(f"表数据导出失败，exit code: {exit_code}")

            # 处理文件
            if os.path.exists(temp_file):
                file_size = os.path.getsize(temp_file)

                if file_size > self.split_threshold:
                    self._split_large_file(temp_file, table_file, self.split_threshold)
                    os.remove(temp_file)
                    # 文件已拆分，使用原始文件大小作为参考
                    file_size_mb = file_size / 1024 / 1024
                else:
                    # 小文件直接重命名
                    os.rename(temp_file, table_file)
                    file_size_mb = os.path.getsize(table_file) / 1024 / 1024
                return {
                    'success': True,
                    'duration': time.time() - start_time,
                    'size_mb': file_size_mb
                }
            else:
                # 空文件
                open(table_file, 'w').close()
                return {
                    'success': True,
                    'duration': time.time() - start_time,
                    'size_mb': 0
                }

        except Exception as e:
            # 清理临时文件
            temp_file = f"{table_file}.tmp"
            if os.path.exists(temp_file):
                os.remove(temp_file)
            return {
                'success': False,
                'duration': time.time() - start_time,
                'error': str(e)
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
        """将大文件按指定大小拆分成多个文件"""
        try:
            file_number = 1
            current_size = 0
            current_file = None

            total_size = os.path.getsize(temp_file)
            processed_size = 0

            with open(temp_file, 'r', encoding='utf-8') as f:
                line_buffer = []
                buffer_size_bytes = 0

                for line in f:
                    line_bytes = line.encode('utf-8')
                    line_size = len(line_bytes)
                    processed_size += line_size

                    # 检查是否需要新文件
                    if line.strip().startswith('INSERT INTO'):
                        if current_file and current_size + buffer_size_bytes + line_size > max_size:
                            current_file.write(''.join(line_buffer))
                            line_buffer = []
                            buffer_size_bytes = 0
                            current_file.close()
                            file_number += 1
                            current_file = None
                            current_size = 0

                        if current_file is None:
                            base_name_without_ext = os.path.splitext(base_filename)[0]
                            ext = os.path.splitext(base_filename)[1]
                            current_file = open(
                                f"{base_name_without_ext}.part{file_number:03d}{ext}",
                                'w', encoding='utf-8'
                            )
                            current_size = 0

                    line_buffer.append(line)
                    buffer_size_bytes += line_size

                    if buffer_size_bytes >= 1024 * 1024:  # 1MB时写入
                        if current_file:
                            current_file.write(''.join(line_buffer))
                            current_size += buffer_size_bytes
                        line_buffer = []
                        buffer_size_bytes = 0

                # 写入剩余内容
                if line_buffer and current_file:
                    current_file.write(''.join(line_buffer))
                    current_file.close()
                elif current_file:
                    current_file.close()

        except Exception as e:
            logger.error(f"拆分文件时发生错误: {str(e)}")
            raise
