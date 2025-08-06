import os
import shutil
import time
import concurrent.futures
import re
import configparser
from typing import List, Optional

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

    def export_db(self, database: str, dump_file: str, tables: Optional[List[str]] = None):
        """
        使用mysqldump导出数据库结构，然后使用线程池分别导出每个表的数据
        提供清晰的进度显示
        """
        start_time = time.time()
        logger.log_database_start(database, "导出")

        try:
            # 清理已存在的文件和目录
            self._cleanup_existing_files(dump_file, database)

            # 确保输出目录存在
            os.makedirs(os.path.dirname(dump_file), exist_ok=True)

            mysqldump_path = self._get_mysqldump_exe()
            mysqldump_bin_dir = os.path.dirname(mysqldump_path)

            # 第一步：导出数据库结构
            logger.info(f"📊 正在导出数据库结构...")
            structure_start = time.time()
            if not self._export_structure(database, dump_file, mysqldump_path, mysqldump_bin_dir):
                return False

            # 第二步：获取数据库的所有表
            if tables is None or tables == ['*']:
                tables = self._get_all_tables(database)

            if not tables:
                logger.info(f"ℹ️ 数据库 {database} 中没有表需要导出数据")
                logger.log_database_complete(database, "导出", time.time() - start_time)
                return True

            # 第三步：导出表数据
            logger.info(f"📊 发现 {len(tables)} 个表需要导出数据")
            success_count = self._export_tables_data(database, tables, dump_file, mysqldump_path, mysqldump_bin_dir)

            if success_count == len(tables):
                total_duration = time.time() - start_time
                logger.log_database_complete(database, "导出", total_duration)
                return True
            else:
                logger.error(f"导出失败: {len(tables) - success_count} 个表导出失败")
                return False

        except Exception as e:
            logger.error(f"导出过程发生错误 - 数据库: {database}, 错误: {str(e)}")
            return False

    def _cleanup_existing_files(self, dump_file: str, database: str):
        """清理已存在的文件和目录"""
        # 删除已存在的数据库结构文件
        if os.path.exists(dump_file):
            os.remove(dump_file)
            logger.cleanup(f"数据库结构文件: {dump_file}")

        # 删除已存在的数据库文件夹
        db_folder = os.path.join(os.path.dirname(dump_file), database)
        if os.path.exists(db_folder):
            shutil.rmtree(db_folder)
            logger.cleanup(f"数据库文件夹: {db_folder}")

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
                f'--databases {database}'
            )

            full_command = f'{cmd} > {dump_file}'
            success, exit_code, output = self._exe_command(full_command, cwd=mysqldump_bin_dir)

            if not success:
                raise RuntimeError(f"数据库结构导出失败，exit code: {exit_code}")

            file_size = os.path.getsize(dump_file) / 1024 / 1024
            logger.success(f"数据库结构导出完成 ({file_size:.1f}MB)")
            return True

        except Exception as e:
            logger.error(f"数据库结构导出失败 - 数据库: {database}, 错误: {str(e)}")
            return False

    def _export_tables_data(self, database: str, tables: List[str], dump_file: str,
                          mysqldump_path: str, mysqldump_bin_dir: str) -> int:
        """并发导出所有表的数据"""
        db_folder = os.path.join(os.path.dirname(dump_file), database)
        os.makedirs(db_folder, exist_ok=True)

        logger.info(f"🔄 开始并发导出表数据...")
        export_start = time.time()

        success_count = 0
        failed_tables = []

        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
            # 提交所有导出任务
            futures = []
            for idx, table in enumerate(tables):
                table_file = os.path.join(db_folder, f"{table}.sql")
                future = pool.submit(
                    self._export_single_table,
                    database, table, table_file,
                    mysqldump_path, mysqldump_bin_dir,
                    idx + 1, len(tables)
                )
                futures.append((table, future))

            # 收集结果
            for table, future in futures:
                try:
                    result = future.result()
                    if result['success']:
                        success_count += 1
                        logger.log_table_complete(
                            database, table, result['duration'], result['size_mb']
                        )
                    else:
                        failed_tables.append(table)
                        logger.error(f"表导出失败 - 数据库: {database}, 表: {table}, 错误: {result['error']}")
                except Exception as e:
                    failed_tables.append(table)
                    logger.error(f"表导出异常 - 数据库: {database}, 表: {table}, 错误: {str(e)}")

                # 更新批量进度
                progress = (success_count + len(failed_tables)) / len(tables) * 100
                logger.log_batch_progress(
                    "表数据导出",
                    success_count + len(failed_tables),
                    len(tables),
                    len(failed_tables)
                )

        export_duration = time.time() - export_start
        logger.info(f"表数据导出统计 - 成功: {success_count}, 失败: {len(failed_tables)}, 总计: {len(tables)}, 耗时: {export_duration:.1f}s")

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
                    # 大文件需要拆分
                    file_size_mb = file_size / 1024 / 1024
                    logger.info(
                        f"文件过大，正在拆分",
                        {"table": table, "size": f"{file_size_mb:.1f}MB"}
                    )
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
            logger.info(f"📊 获取表列表完成 - 数据库: {database}, 表数量: {len(tables)}")
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

                    # 进度显示
                    if processed_size % (10 * 1024 * 1024) < line_size:  # 每10MB显示一次进度
                        progress = (processed_size / total_size) * 100
                        logger.log_table_progress(
                            os.path.basename(base_filename).split('.')[0],
                            f"拆分进度",
                            progress,
                            processed_size // 1024 // 1024,
                            total_size // 1024 // 1024
                        )

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

            # 清除进度条
            print(f"\r{' ' * 100}\r", end="")
            logger.info(f"文件拆分完成 - 文件数: {file_number}, 总大小: {total_size/1024/1024:.1f}MB")

        except Exception as e:
            logger.error(f"拆分文件时发生错误: {str(e)}")
            raise
