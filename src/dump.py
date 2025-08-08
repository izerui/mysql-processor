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

# 定义SQL头尾语句
header_lines = [
    "set foreign_key_checks = 0;",  # 禁用外键检查
    "set unique_checks = 0;",  # 禁用唯一性检查
    "set autocommit=0;",  # 禁用自动提交
    "SET SESSION sort_buffer_size = 32*1024*1024;",  # 调整排序缓冲区
    "START TRANSACTION;",  # 开始事务
]
commit_lines = [
    "commit;",
    "START TRANSACTION;",
]
footer_lines = [
    "commit;",
    "set foreign_key_checks = 1;",
    "set unique_checks = 1;",
]


class MyDump(BaseShell):
    """
    MySQL数据库备份导出工具类

    功能特点：
    1. 支持完整数据库结构导出
    2. 支持并发导出表数据，提高导出效率
    3. 支持大文件自动拆分，避免单个文件过大
    4. 提供详细的进度显示和错误处理
    5. 流式处理，内存占用低，适合处理大数据量

    导出流程：
    1. 导出数据库结构（表结构、索引等）
    2. 并发导出每个表的数据
    3. 对大文件进行拆分处理
    4. 添加必要的SQL头尾信息
    """

    def __init__(self, mysql: Mysql, split_threshold_mb: int = 500, threads: int = 8):
        """
        初始化MyDump实例

        Args:
            mysql: MySQL连接配置对象
            split_threshold_mb: 文件拆分阈值（MB），超过此大小的文件会被拆分
            threads: 并发导出线程数
        """
        super().__init__()
        self.mysql = mysql  # MySQL连接配置
        self.use_pv = self._check_pv_available()  # 检查是否安装了pv工具（进度显示）
        self.split_threshold = split_threshold_mb * 1024 * 1024  # 转换为字节
        self.threads = threads  # 并发线程数

    def _check_pv_available(self):
        """检查pv工具是否可用（用于进度条显示）"""
        return shutil.which('pv') is not None

    def export_db(self, database: str, dump_file: str):
        """
        主导出函数：导出整个数据库

        执行流程：
        1. 创建输出目录
        2. 导出数据库结构
        3. 获取所有表列表
        4. 并发导出每个表的数据
        5. 汇总导出结果

        Args:
            database: 要导出的数据库名称
            dump_file: 主SQL文件路径（包含结构）
        """
        try:
            # 确保输出目录存在
            os.makedirs(os.path.dirname(dump_file), exist_ok=True)

            # 第一步：导出数据库结构
            if not self._export_structure(database, dump_file):
                return False

            # 第二步：获取数据库的所有表
            tables = self._get_all_tables(database)

            if not tables:
                logger.warning(f"数据库 {database} 中没有需要导出的表")
                return True

            # 第三步：并发导出表数据
            success_count = self._export_tables_data(database, dump_file)
            return success_count >= 0

        except Exception as e:
            logger.error(f"导出过程发生错误 - 数据库: {database}, 错误: {str(e)}")
            return False

    def _export_structure(self, database: str, dump_file: str) -> bool:
        """
        导出数据库结构（不包含数据）

        导出的结构包括：
        - 数据库创建语句
        - 所有表的CREATE TABLE语句
        - 索引定义
        - 约束定义

        Args:
            database: 数据库名称
            dump_file: 输出文件路径

        Returns:
            bool: 导出成功返回True，失败返回False
        """
        try:

            mysql_dump_exe = self.get_mysqldump_exe()
            mysql_bin_dir = self.get_mysql_bin_dir()

            # 构建mysqldump命令，只导出结构
            cmd = (
                f'{mysql_dump_exe} '
                f'-h {self.mysql.db_host} '
                f'-u {self.mysql.db_user} '
                f'-p\'{self.mysql.db_pass}\' '
                f'--port={self.mysql.db_port} '
                f'--ssl-mode=DISABLED ' # 如果不需要SSL
                f'--protocol=TCP ' # 强制使用TCP
                f'--default-character-set=utf8 '
                f'--set-gtid-purged=OFF '  # 不导出GTID信息
                f'--skip-routines '  # 跳过存储过程和函数
                f'--skip-triggers '  # 跳过触发器
                f'--skip-add-locks '  # 跳过锁表语句
                f'--disable-keys '  # 禁用外键检查
                f'--skip-events '  # 跳过事件
                f'--skip-set-charset '  # 跳过字符集设置
                f'--add-drop-database '  # 添加删除数据库语句
                f'--extended-insert '  # 使用扩展插入格式
                f'--complete-insert '  # 使用完整的列名
                f'--quick '  # 快速导出，逐行读取
                f'--no-autocommit '  # 禁用自动提交
                f'--single-transaction '  # 使用一致性快照
                f'--skip-lock-tables '  # 不锁表
                f'--compress '  # 压缩传输
                f'--skip-tz-utc '  # 不设置时区
                f'--max-allowed-packet=256M '  # 最大包大小
                f'--net-buffer-length=1048576 '  # 网络缓冲区大小
                f'--no-data '  # 关键：不导出数据
                f'--databases {database}'
            )

            full_command = f'{cmd} > {dump_file}'
            success, exit_code, output = self._exe_command(full_command, cwd=mysql_bin_dir)

            if not success:
                raise RuntimeError(f"数据库结构导出失败，exit code: {exit_code}")

            return True

        except Exception as e:
            logger.error(f"数据库结构导出失败 - 数据库: {database}, 错误: {str(e)}")
            return False

    def _export_tables_data(self, database: str, dump_file: str) -> int:
        """
        并发导出所有表的数据

        使用线程池并发导出每个表的数据，提供实时进度显示

        Args:
            database: 数据库名称
            dump_file: 主SQL文件路径（用于确定输出目录）

        Returns:
            int: 成功导出的表数量
        """
        # 为每个数据库创建单独的文件夹存放表数据
        db_folder = os.path.join(os.path.dirname(dump_file), database)
        os.makedirs(db_folder, exist_ok=True)

        # 获取数据库的所有表
        tables = self._get_all_tables(database)
        if not tables:
            logger.warning(f"数据库 {database} 中没有需要导出的表")
            return 0

        success_count = 0
        failed_tables = []
        exported_total_size = 0.0  # 已导出的总大小
        export_start_time = time.time()  # 记录开始时间

        # 使用tqdm显示进度条
        with tqdm(total=len(tables), desc=f"{Fore.MAGENTA}📊 并行[{self.threads}]导出 {database} 表数据", unit="表",
                  dynamic_ncols=True, disable=False,
                  file=sys.stdout, ascii=True) as pbar:
            def update_progress(result, table_name):
                """更新进度条显示"""
                nonlocal exported_total_size
                if result['success']:
                    # 计算已导出的总大小
                    exported_total_size = self._get_exported_files_size(db_folder)
                    # 计算从开始到现在的整体平均速度
                    elapsed_time = time.time() - export_start_time
                    overall_speed = f"{exported_total_size / elapsed_time:.1f}MB/s" if elapsed_time > 0 else "0.0MB/s"
                    pbar.set_postfix_str(
                        f"✓ {table_name} ({result['original_size_mb']:.1f}MB) 平均速度: {overall_speed} 已导出: {exported_total_size:.1f}MB")
                else:
                    exported_total_size = self._get_exported_files_size(db_folder)
                    # 即使失败也计算整体平均速度
                    elapsed_time = time.time() - export_start_time
                    overall_speed = f"{exported_total_size / elapsed_time:.1f}MB/s" if elapsed_time > 0 else "0.0MB/s"
                    pbar.set_postfix_str(
                        f"✗ {table_name} 平均速度: {overall_speed} 已导出: {exported_total_size:.1f}MB")
                pbar.update(1)
                return result

            # 使用线程池并发导出
            with concurrent.futures.ThreadPoolExecutor(max_workers=self.threads) as pool:
                # 提交所有导出任务
                futures = []
                for table in tables:
                    table_file = os.path.join(db_folder, f"{table}.sql")
                    future = pool.submit(
                        self._export_table_data,
                        database,
                        table,
                        table_file,
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
        """
        计算已导出的SQL文件总大小

        Args:
            db_folder: 数据库导出文件夹路径

        Returns:
            float: 总大小（MB）
        """
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

    def _export_table_data(self, database: str, table: str, table_file: str) -> dict:
        """
        导出单个表的数据

        处理逻辑：
        1. 使用mysqldump导出表数据
        2. 检查文件是否包含有效数据（INSERT语句）
        3. 对大文件进行拆分处理
        4. 对小文件添加头尾信息

        Args:
            database: 数据库名称
            table: 表名称
            table_file: 输出文件路径

        Returns:
            dict: 包含导出结果的字典
                - success: 是否成功
                - duration: 耗时（秒）
                - size_mb: 文件大小（MB）
                - error: 错误信息（如果有）
        """
        start_time = time.time()

        try:
            mysql_dump_exe = self.get_mysqldump_exe()
            mysql_bin_dir = self.get_mysql_bin_dir()

            # 构建mysqldump命令，只导出数据
            cmd = (
                f'{mysql_dump_exe} '
                f'-h {self.mysql.db_host} '
                f'-u {self.mysql.db_user} '
                f'-p"{self.mysql.db_pass}" '
                f'--port={self.mysql.db_port} '
                f'--ssl-mode=DISABLED ' # 如果不需要SSL
                f'--protocol=TCP ' # 强制使用TCP
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

            # 直接导出到表名.sql文件
            full_command = f'{cmd} > {table_file}'

            success, exit_code, output = self._exe_command(
                full_command, cwd=mysql_bin_dir
            )

            if not success:
                raise RuntimeError(f"表数据导出失败，exit code: {exit_code}")

            # 处理导出的文件
            if os.path.exists(table_file):
                file_size = os.path.getsize(table_file)

                # 检查文件是否包含INSERT INTO语句
                has_insert = self._check_has_insert_sql(table_file)

                if not has_insert:
                    # 如果没有INSERT INTO语句，说明表为空，删除文件
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
        """
        获取数据库中的所有表名

        Args:
            database: 数据库名称

        Returns:
            List[str]: 表名列表（已排序）
        """
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
        """
        使用流式处理拆分大文件，避免内存占用

        流式拆分策略：
        1. 直接处理生成器：不收集所有INSERT行到内存
        2. 分块写入：current_lines只保存当前文件内容
        3. 及时释放：写完一个文件立即清空缓存
        4. 编码兼容：保留UTF-8/Latin-1处理逻辑
        5. 每50行INSERT后添加commit_lines

        内存控制：
        - 峰值内存 = 单个文件最大内容 + 64KB缓冲区
        - 与原始文件大小无关，适合处理GB级文件

        Args:
            temp_file: 临时文件路径
            base_filename: 基础文件名
            max_size: 最大文件大小（字节）
        """
        base_name_without_ext = os.path.splitext(base_filename)[0]
        ext = os.path.splitext(base_filename)[1]

        # 转换为字节
        max_bytes = max_size
        file_counter = 1

        header_bytes = ('\n'.join(header_lines) + '\n').encode('utf-8')
        footer_bytes = ('\n'.join(footer_lines) + '\n').encode('utf-8')
        commit_bytes = ('\n'.join(commit_lines) + '\n').encode('utf-8')

        # 计算头尾占用的空间
        header_size = len(header_bytes)
        footer_size = len(footer_bytes)
        commit_size = len(commit_bytes)
        effective_max_bytes = max_bytes - header_size - footer_size - commit_size

        try:
            # 流式处理INSERT INTO行，避免内存占用
            insert_lines = self._iter_insert_lines(temp_file)

            # 开始拆分文件 - 使用真正的流式处理
            current_lines = []
            current_size = 0
            insert_count = 0

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
                    insert_count = 0

                current_lines.append(byte_line)
                current_size += line_size
                insert_count += 1

                # 每50行INSERT后添加commit_lines
                if insert_count % 50 == 0 and current_lines:
                    # 添加commit语句（除了最后一个文件的最后一组）
                    current_lines.append(commit_bytes)
                    current_size += commit_size

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
        """
        检查SQL文件是否包含INSERT INTO语句

        Args:
            file_path: SQL文件路径

        Returns:
            bool: 包含INSERT语句返回True，否则返回False
        """
        try:
            for _ in self._iter_insert_lines(file_path):
                return True
            return False
        except Exception as e:
            logger.error(f"检查SQL文件时发生错误: {str(e)}")
            return False

    def _iter_insert_lines(self, file_path: str):
        """
        生成器中逐个产生INSERT INTO行，实现真正的流式处理

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
                        # 处理剩余缓冲区
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
                    buffer = lines[-1]  # 保留不完整的行

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
        """
        给文件添加头尾信息，使用流式处理保留INSERT INTO语句

        流式处理特点：
        1. 复用 _iter_insert_lines 生成器，不重复内存占用
        2. 临时文件方式，保证数据安全
        3. 逐行写入，内存占用恒定
        4. 保持原始编码处理逻辑
        5. 每50行INSERT后添加commit_lines

        Args:
            file_path: SQL文件路径

        Returns:
            bool: 处理成功返回True，失败返回False
        """
        try:
            header = '\n'.join(header_lines) + "\n"
            footer = '\n'.join(footer_lines) + "\n"
            commit = '\n'.join(commit_lines) + "\n"

            # 使用临时文件方式处理，避免数据丢失
            temp_file = file_path + '.tmp'

            # 收集所有INSERT INTO行
            insert_lines = list(self._iter_insert_lines(file_path))
            total_lines = len(insert_lines)

            # 写入处理后的内容
            with open(temp_file, 'w', encoding='utf-8') as out_f:
                out_f.write(header)

                for i, line in enumerate(insert_lines):
                    out_f.write('\n' + line)

                    # 每50行INSERT后添加commit_lines（不是最后一行）
                    if (i + 1) % 50 == 0 and (i + 1) < total_lines:
                        out_f.write('\n' + commit)

                out_f.write('\n' + footer)

            # 原子替换原文件
            os.replace(temp_file, file_path)
            return True

        except Exception as e:
            logger.error(f"添加头尾信息时发生错误: {str(e)}")
            temp_file = file_path + '.tmp'
            if os.path.exists(temp_file):
                os.remove(temp_file)
            return False
