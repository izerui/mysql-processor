import os
import shutil
import time
import concurrent.futures
import re
import configparser

from base import BaseShell, Mysql
from logger_config import logger


class MyDump(BaseShell):
    """
    使用mysqldump导出数据库备份
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

    def export_db(self, database, dump_file, tables=None):
        """
        使用mysqldump导出数据库结构，然后使用线程池分别导出每个表的数据
        :param database: 数据库名
        :param dump_file: 导出的SQL文件路径
        :param tables: 表名列表，默认为None导出所有表
        :return:
        """
        try:
            # 确保输出目录存在
            os.makedirs(os.path.dirname(dump_file), exist_ok=True)

            mysqldump_path = self._get_mysqldump_exe()
            mysqldump_bin_dir = os.path.dirname(mysqldump_path)

            # 第一步：导出数据库结构（仅表结构，不包含数据）
            logger.info(f"正在导出数据库结构: {database}")
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
                f'--databases {database}'
            )

            full_command = f'{cmd} > {dump_file}'
            success, exit_code, output = self._exe_command(
                full_command,
                cwd=mysqldump_bin_dir
            )

            if not success:
                raise RuntimeError(f"数据库结构导出失败，exit code: {exit_code}")

            logger.info(f'✅ 数据库结构导出成功: {database}')

            # 第二步：获取数据库的所有表
            if tables is None or tables == ['*']:
                tables = self._get_all_tables(database)

            if not tables:
                logger.info(f"数据库 {database} 中没有表需要导出数据")
                return True

            # 第三步：创建数据库文件夹
            db_folder = os.path.join(os.path.dirname(dump_file), database)
            os.makedirs(db_folder, exist_ok=True)

            # 第四步：使用线程池导出每个表的数据
            logger.info(f"正在使用线程池导出 {len(tables)} 个表的数据...")
            start_time = time.time()

            with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
                futures = []
                for table in tables:
                    table_file = os.path.join(db_folder, f"{table}.sql")
                    future = pool.submit(self._export_table_data, database, table, table_file, mysqldump_path, mysqldump_bin_dir)
                    futures.append(future)

                # 等待所有任务完成
                for future in concurrent.futures.as_completed(futures):
                    try:
                        future.result()
                    except Exception as e:
                        logger.error(f"导出表数据时发生错误: {str(e)}")
                        raise

            duration = time.time() - start_time
            logger.info(f'✅ 所有表数据导出完成 (耗时: {duration:.2f}秒)')
            return True

        except RuntimeError as e:
            raise e
        except Exception as e:
            raise RuntimeError(f"导出过程发生错误: {str(e)}")

    def _get_all_tables(self, database):
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
            return tables

        except Exception as e:
            logger.error(f"获取表列表失败: {str(e)}")
            return []

    def _export_table_data(self, database, table, table_file, mysqldump_path, mysqldump_bin_dir):
        """导出单个表的数据（仅insert语句），并按500MB拆分大文件"""
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
                f'{database} {table}'
            )

            # 先导出到临时文件
            temp_file = f"{table_file}.tmp"
            full_command = f'{cmd} > {temp_file}'
            logger.info(f"正在导出表数据: {database}.{table}")

            start_time = time.time()
            success, exit_code, output = self._exe_command(
                full_command,
                cwd=mysqldump_bin_dir
            )
            duration = time.time() - start_time

            if not success:
                raise RuntimeError(f"表数据导出失败: {database}.{table}, exit code: {exit_code}")

            # 检查文件大小并拆分
            if os.path.exists(temp_file):
                file_size = os.path.getsize(temp_file)
                max_size = self.split_threshold

                if file_size > max_size:
                    logger.info(f"表 {database}.{table} 数据文件过大 ({file_size / 1024 / 1024:.2f}MB)，正在拆分...")
                    self._split_large_file(temp_file, table_file, max_size)
                    os.remove(temp_file)
                    logger.info(f'✅ 表数据导出并拆分成功: {database}.{table} (耗时: {duration:.2f}秒)')
                else:
                    # 文件不大，直接重命名
                    os.rename(temp_file, table_file)
                    logger.info(f'✅ 表数据导出成功: {database}.{table} (耗时: {duration:.2f}秒)')
            else:
                # 空文件，创建空文件
                open(table_file, 'w').close()
                logger.info(f'✅ 表数据为空: {database}.{table} (耗时: {duration:.2f}秒)')

        except Exception as e:
            logger.error(f"导出表 {database}.{table} 数据时发生错误: {str(e)}")
            if os.path.exists(f"{table_file}.tmp"):
                os.remove(f"{table_file}.tmp")
            raise

    def _split_large_file(self, temp_file, base_filename, max_size):
        """将大文件按500MB拆分成多个文件，使用流式处理避免内存问题"""
        try:
            file_number = 1
            current_size = 0
            current_file = None

            # 只使用UTF-8编码
            with open(temp_file, 'r', encoding='utf-8') as f:
                line_buffer = []
                buffer_size_bytes = 0

                for line in f:
                    line_bytes = line.encode('utf-8')
                    line_size = len(line_bytes)

                    # 如果是INSERT语句的开头，检查是否需要新文件
                    if line.strip().startswith('INSERT INTO'):
                        # 如果已有缓冲内容且会超出限制，先写入当前文件
                        if current_file and current_size + buffer_size_bytes + line_size > max_size:
                            current_file.write(''.join(line_buffer))
                            line_buffer = []
                            buffer_size_bytes = 0
                            current_file.close()
                            file_number += 1
                            current_file = None
                            current_size = 0

                        # 如果需要新文件
                        if current_file is None:
                            # 将.sql后缀放在.partxxx之前，保持正确的文件扩展名
                            base_name_without_ext = os.path.splitext(base_filename)[0]
                            ext = os.path.splitext(base_filename)[1]
                            current_file = open(f"{base_name_without_ext}.part{file_number:03d}{ext}", 'w', encoding='utf-8')
                            current_size = 0

                    # 添加到缓冲区
                    line_buffer.append(line)
                    buffer_size_bytes += line_size

                    # 定期写入，避免缓冲区过大
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
