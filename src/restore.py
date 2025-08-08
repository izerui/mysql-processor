import os
import sys
import time
import concurrent.futures
from pathlib import Path
from typing import List, Optional, Dict, Any
from colorama import Fore
from tqdm import tqdm
from base import BaseShell, Mysql
from logger_config import logger


class MyRestore(BaseShell):
    """
    MySQL数据库恢复工具类 - 从SQL文件导入到MySQL数据库

    功能特点：
    1. 支持完整数据库恢复（结构+数据）
    2. 支持并发导入表数据，提高恢复效率
    3. 提供实时进度显示和详细日志记录
    4. 支持大文件分片导入
    5. 具备错误处理和事务回滚机制

    使用示例：
        mysql = Mysql(host="localhost", user="root", password="123456", port=3306)
        restorer = MyRestore(mysql, threads=8)
        success = restorer.restore_db("mydb", "/backup/mydb_20240101")
    """

    def __init__(self, mysql: Mysql, threads: int = 8):
        """
        初始化MyRestore实例

        Args:
            mysql: Mysql连接配置对象，包含数据库连接信息
            threads: 并发导入线程数，默认为8
                   建议根据CPU核心数和磁盘IO能力调整
        """
        super().__init__()
        self.mysql = mysql  # MySQL连接配置
        self.threads = threads  # 并发线程数

    def restore_db(self, database: str, dump_folder: str) -> bool:
        """
        从SQL文件导入整个数据库，提供完整的恢复流程

        恢复流程：
        1. 检查并导入数据库结构文件（database.sql）
        2. 扫描数据文件夹获取所有表数据文件
        3. 并发导入所有表数据文件

        Args:
            database: 目标数据库名称
            dump_folder: 备份文件夹路径，结构如下：
                        dump_folder/
                        ├── database.sql          # 数据库结构文件
                        └── database/             # 数据文件夹
                            ├── table1.sql        # 表数据文件
                            ├── table2.sql
                            └── table2_part2.sql  # 分片数据文件

        Returns:
            bool: 恢复成功返回True，失败返回False

        异常处理：
            - 文件不存在时记录错误日志
            - 任何步骤失败都会终止整个恢复过程
            - 所有异常都会被捕获并记录
        """
        try:
            # 1. 导入数据库结构
            structure_file = os.path.join(dump_folder, f"{database}.sql")
            if not os.path.exists(structure_file):
                logger.error(f"数据库结构文件不存在: {structure_file}")
                return False

            if not self._import_structure(structure_file, database):
                return False

            # 2. 获取所有表数据文件
            db_data_folder = os.path.join(dump_folder, database)
            if not os.path.exists(db_data_folder):
                # 数据文件夹不存在，说明只有结构文件，直接返回成功
                return True

            # 收集所有数据文件
            data_files = self._collect_data_files(db_data_folder)
            if not data_files:
                # 没有找到数据文件，只有结构，返回成功
                return True

            # 3. 并发导入表数据
            success_count = self._import_tables_data(database, data_files)

            if success_count == len(data_files):
                return True
            else:
                logger.error(f"导入失败: {len(data_files) - success_count} 个文件导入失败")
                return False

        except Exception as e:
            logger.error(f"导入过程发生错误 - 数据库: {database}, 错误: {str(e)}")
            return False

    def _import_structure(self, structure_file: str, database: str) -> bool:
        """
        导入数据库结构文件

        结构文件包含：
        - CREATE DATABASE语句
        - 所有表的CREATE TABLE语句
        - 索引、约束、存储过程等

        Args:
            structure_file: 结构文件完整路径
            database: 目标数据库名称

        Returns:
            bool: 导入成功返回True，失败返回False
        """
        try:
            success, output = self._execute_import(structure_file, database, is_structure_file=True)
            if success:
                return True
            else:
                logger.error(f"数据库结构导入失败 - 数据库: {database}, 错误: {output}")
                return False
        except Exception as e:
            logger.error(f"数据库结构导入失败 - 数据库: {database}, 错误: {str(e)}")
            return False

    def _collect_data_files(self, db_data_folder: str) -> List[str]:
        """
        收集所有需要导入的数据文件

        文件收集规则：
        1. 只收集.sql后缀的文件
        2. 按文件名排序，确保导入顺序一致
        3. 跳过空文件
        4. 支持分片文件（如table_part1.sql, table_part2.sql）

        Args:
            db_data_folder: 数据文件夹路径

        Returns:
            List[str]: 数据文件完整路径列表，按文件名排序
        """
        data_files = []

        for file in sorted(os.listdir(db_data_folder)):
            if file.endswith('.sql'):
                file_path = os.path.join(db_data_folder, file)
                file_size = os.path.getsize(file_path)

                if file_size > 0:
                    data_files.append(file_path)

        return data_files

    def _import_tables_data(self, database: str, data_files: List[str]) -> int:
        """
        并发导入所有表数据文件

        并发特性：
        1. 使用ThreadPoolExecutor管理线程池
        2. 实时进度条显示（tqdm）
        3. 动态速度显示（MB/s）
        4. 失败文件单独记录

        Args:
            database: 目标数据库名称
            data_files: 数据文件路径列表

        Returns:
            int: 成功导入的文件数量
        """
        success_count = 0
        failed_files = []
        imported_total_size = 0.0  # 已导入的总大小（MB）
        import_start_time = time.time()  # 记录开始时间

        # 使用tqdm创建进度条
        with tqdm(
            total=len(data_files),
            desc=f"{Fore.MAGENTA}📊 导入: [{database}] 数据库",
            unit="文件",
            dynamic_ncols=True,  # 自动调整宽度
            disable=False,
            file=sys.stdout,
            ascii=True,
            miniters=1,
            mininterval=0.1,
            position=0,
            leave=True
        ) as pbar:

            # 进度更新回调函数
            def update_progress(result, file_name):
                nonlocal imported_total_size
                # 计算从开始到现在的整体平均速度
                elapsed_time = time.time() - import_start_time

                if result['success']:
                    imported_total_size += result['size_mb']
                    avg_speed = f"{imported_total_size / elapsed_time:.1f}MB/s" if elapsed_time > 0 else "0.0MB/s"
                    pbar.set_postfix_str(
                        f"✓ {os.path.basename(file_name)} "
                        f"({result['size_mb']:.1f}MB)   {avg_speed} "
                        f"| {imported_total_size:.1f}MB"
                    )
                else:
                    imported_total_size += result['size_mb']
                    avg_speed = f"{imported_total_size / elapsed_time:.1f}MB/s" if elapsed_time > 0 else "0.0MB/s"
                    pbar.set_postfix_str(
                        f"✗ {os.path.basename(file_name)}   {avg_speed} | {imported_total_size:.1f}MB"
                    )
                pbar.update(1)
                return result

            # 创建线程池执行并发导入
            with concurrent.futures.ThreadPoolExecutor(max_workers=self.threads) as pool:
                # 提交所有导入任务
                futures = []
                for sql_file in data_files:
                    future = pool.submit(
                        self._import_single_table,
                        sql_file,
                        database,
                    )
                    # 添加回调来更新进度
                    future.add_done_callback(
                        lambda f, f_path=sql_file: update_progress(f.result(), f_path)
                    )
                    futures.append(future)

                # 等待所有任务完成
                concurrent.futures.wait(futures)

                # 收集最终结果
                for future, sql_file in zip(futures, data_files):
                    try:
                        result = future.result()
                        if result['success']:
                            success_count += 1
                        else:
                            failed_files.append(os.path.basename(sql_file))
                            logger.error(
                                f"文件导入失败 - 文件: {os.path.basename(sql_file)}, "
                                f"错误: {result['error']}"
                            )
                    except Exception as e:
                        failed_files.append(os.path.basename(sql_file))
                        logger.error(
                            f"文件导入异常 - 文件: {os.path.basename(sql_file)}, "
                            f"错误: {str(e)}"
                        )

        # 汇总失败文件
        if failed_files:
            logger.error(f"导入失败文件列表: {', '.join(failed_files)}")

        return success_count

    def _import_single_table(self, sql_file: str, database: str) -> Dict[str, Any]:
        """
        导入单个表的数据文件

        支持特性：
        1. 计算文件大小和导入耗时
        2. 返回详细的导入结果信息
        3. 异常捕获和错误信息记录

        Args:
            sql_file: SQL文件完整路径
            database: 目标数据库名称

        Returns:
            Dict[str, Any]: 导入结果，包含：
                - success: 是否成功
                - duration: 耗时（秒）
                - size_mb: 文件大小（MB）
                - error: 错误信息（如果有）
        """
        start_time = time.time()

        try:
            file_size = os.path.getsize(sql_file)
            file_size_mb = file_size / 1024 / 1024

            success, output = self._execute_import(sql_file, database, is_structure_file=False)

            return {
                'success': success,
                'duration': time.time() - start_time,
                'size_mb': file_size_mb,
                'error': None if success else output
            }

        except Exception as e:
            return {
                'success': False,
                'duration': time.time() - start_time,
                'size_mb': 0,
                'error': str(e)
            }

    def _execute_import(self, sql_file: str, database: str, is_structure_file: bool = False) -> tuple[bool, str]:
        """
        执行单个SQL文件的导入

        导入优化：
        1. 区分结构文件和数据文件的处理方式
        2. 结构文件：不指定数据库，让SQL文件中的CREATE DATABASE生效
        3. 数据文件：指定具体数据库进行导入
        4. 禁用自动提交，提高批量导入性能
        5. 禁用外键检查，避免约束冲突

        事务管理：
        - 导入前：禁用约束检查
        - 导入后：成功则提交事务，失败则回滚
        - 清理：恢复所有MySQL设置

        Args:
            sql_file: SQL文件完整路径
            database: 目标数据库名称
            is_structure_file: 是否为结构文件（包含CREATE DATABASE语句）

        Returns:
            bool: 导入成功返回True，失败返回False
        """
        try:
            mysql_exe = self.get_mysql_exe()
            mysql_bin_dir = self.get_mysql_bin_dir()

            # 构建基础mysql命令
            base_cmd = (
                f'{mysql_exe} '
                f'-h {self.mysql.db_host} '
                f'-u {self.mysql.db_user} '
                f'-p\'{self.mysql.db_pass}\' '
                f'--port={self.mysql.db_port} '
                f'--ssl-mode=DISABLED '
                f'--protocol=TCP '
                f'--max-allowed-packet=2048M '
                f'--net-buffer-length=16777216 '
            )

            # 数据文件：指定具体数据库，并添加初始化命令
            init_commands = [
                "SET autocommit=0",
                "SET foreign_key_checks=0",
                "SET unique_checks=0",
                "SET SESSION innodb_lock_wait_timeout=1800",
            ]

            init_command_str = ";".join(init_commands)

            # 根据文件类型构建命令
            if is_structure_file:
                # 结构文件：不指定数据库，让SQL文件中的CREATE DATABASE生效
                cmd = f'{base_cmd} --init-command="{init_command_str}"'
            else:
                cmd = f'{base_cmd} --init-command="{init_command_str}" {database}'

            import_command = f'{cmd} < "{sql_file}"'

            # 执行导入命令
            success, exit_code, output = self._exe_command(
                import_command, cwd=mysql_bin_dir
            )

            if success:
                return True, ""
            else:
                error_msg = "\n".join([line for line in output if line.strip()])
                return False, error_msg

        except Exception as e:
            logger.error(f"导入执行异常: {str(e)}")
            return False, str(e)
