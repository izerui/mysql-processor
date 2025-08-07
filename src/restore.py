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
    从SQL文件导入到MySQL数据库 - 重构版
    提供清晰的进度显示和结构化日志
    """

    def __init__(self, mysql: Mysql):
        super().__init__()
        self.mysql = mysql

    def restore_db(self, database: str, dump_folder: str, threads: int = 8) -> bool:
        """
        从SQL文件导入整个数据库，提供清晰的进度显示
        :param database: 数据库名
        :param dump_folder: 导出文件夹路径
        :param threads: 导入线程池数量
        :return: bool 成功返回True，失败返回False
        """
        start_time = time.time()
        logger.log_database_start(database, "导入")

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
                return True

            # 收集所有数据文件
            data_files = self._collect_data_files(db_data_folder)
            if not data_files:
                return True

            # 3. 并发导入表数据
            success_count = self._import_tables_data(database, data_files, threads)

            total_duration = time.time() - start_time
            if success_count == len(data_files):
                return True
            else:
                logger.error(f"导入失败: {len(data_files) - success_count} 个文件导入失败")
                return False

        except Exception as e:
            logger.error(f"导入过程发生错误 - 数据库: {database}, 错误: {str(e)}")
            return False

    def _import_structure(self, structure_file: str, database: str) -> bool:
        """导入数据库结构"""
        try:
            start_time = time.time()
            success = self._execute_import(structure_file, database)

            if success:
                return True
            else:
                return False

        except Exception as e:
            logger.error(f"数据库结构导入失败 - 数据库: {database}, 错误: {str(e)}")
            return False

    def _collect_data_files(self, db_data_folder: str) -> List[str]:
        """收集所有需要导入的数据文件，包括拆分后的文件"""
        data_files = []

        for file in sorted(os.listdir(db_data_folder)):
            if file.endswith('.sql'):
                file_path = os.path.join(db_data_folder, file)
                file_size = os.path.getsize(file_path)

                if file_size > 0:
                    data_files.append(file_path)

        return data_files

    def _import_tables_data(self, database: str, data_files: List[str], threads: int = 8) -> int:
        """并发导入所有表数据"""
        success_count = 0
        failed_files = []
        imported_total_size = 0.0  # 已导入的总大小

        # 使用tqdm的并发支持来正确显示进度
        with tqdm(total=len(data_files), desc=f"导入 {database} 数据库", unit="文件", dynamic_ncols=True, disable=False, file=sys.stdout, ascii=True) as pbar:
            def update_progress(result, file_name):
                nonlocal imported_total_size
                if result['success']:
                    imported_total_size += result['size_mb']
                    pbar.set_postfix_str(f"✓ {os.path.basename(file_name)} ({result['size_mb']:.1f}MB) 已导入: {imported_total_size:.1f}MB")
                else:
                    pbar.set_postfix_str(f"✗ {os.path.basename(file_name)} 已导入: {imported_total_size:.1f}MB")
                pbar.update(1)
                return result

            with concurrent.futures.ThreadPoolExecutor(max_workers=threads) as pool:
                # 提交所有导入任务
                futures = []
                for sql_file in data_files:
                    future = pool.submit(
                        self._import_single_table,
                        sql_file, database, 1, 1  # 这些参数在进度显示中不再需要
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
                            logger.error(f"文件导入失败 - 文件: {os.path.basename(sql_file)}, 错误: {result['error']}")
                    except Exception as e:
                        failed_files.append(os.path.basename(sql_file))
                        logger.error(f"文件导入异常 - 文件: {os.path.basename(sql_file)}, 错误: {str(e)}")

        if failed_files:
            logger.error(f"导入失败文件列表: {', '.join(failed_files)}")

        return success_count

    def _import_single_table(self, sql_file: str, database: str,
                           current_num: int, total_files: int) -> Dict[str, Any]:
        """导入单个表的数据"""
        start_time = time.time()

        try:
            file_size = os.path.getsize(sql_file)
            file_size_mb = file_size / 1024 / 1024

            success = self._execute_import(sql_file, database)

            return {
                'success': success,
                'duration': time.time() - start_time,
                'size_mb': file_size_mb,
                'error': None if success else "导入执行失败"
            }

        except Exception as e:
            return {
                'success': False,
                'duration': time.time() - start_time,
                'size_mb': 0,
                'error': str(e)
            }

    def _execute_import(self, sql_file: str, database: str) -> bool:
        """执行单个SQL文件的导入"""
        try:
            mysql_path = self._get_mysql_exe()
            mysql_bin_dir = os.path.dirname(mysql_path)

            # 构建优化的mysql命令
            init_commands = [
                "SET autocommit=0",
                "SET foreign_key_checks=0",
                "SET unique_checks=0",
                "SET SESSION innodb_lock_wait_timeout=3600"
            ]
            init_command_str = ";".join(init_commands)

            cmd = (
                f'{mysql_path} '
                f'-h {self.mysql.db_host} '
                f'-u {self.mysql.db_user} '
                f'-p\'{self.mysql.db_pass}\' '
                f'--port={self.mysql.db_port} '
                f'--default-character-set=utf8 '
                f'--max_allowed_packet=268435456 '
                f'--net_buffer_length=1048576 '
                f'--init-command="{init_command_str}"'
                f' {database}'
            )

            import_command = f'{cmd} < "{sql_file}"'

            success, exit_code, output = self._exe_command(
                import_command, cwd=mysql_bin_dir
            )

            if success:
                # 导入成功后提交事务
                commit_cmd = (
                    f'{mysql_path} '
                    f'-h {self.mysql.db_host} '
                    f'-u {self.mysql.db_user} '
                    f'-p\'{self.mysql.db_pass}\' '
                    f'--port={self.mysql.db_port} '
                    f'--default-character-set=utf8 '
                    f'--execute="COMMIT; SET foreign_key_checks=1; SET unique_checks=1; SET autocommit=1;"'
                    f' {database}'
                )

                commit_success, commit_exit_code, commit_output = self._exe_command(
                    commit_cmd, cwd=mysql_bin_dir
                )

                if commit_success:
                    return True
                else:
                    error_msg = "\n".join([line for line in commit_output if line.strip()])
                    logger.error(f"MySQL事务提交失败 - exit_code: {commit_exit_code}, 错误: {error_msg}")
                    return False
            else:
                # 导入失败时回滚事务
                rollback_cmd = (
                    f'{mysql_path} '
                    f'-h {self.mysql.db_host} '
                    f'-u {self.mysql.db_user} '
                    f'-p\'{self.mysql.db_pass}\' '
                    f'--port={self.mysql.db_port} '
                    f'--default-character-set=utf8 '
                    f'--execute="ROLLBACK; SET foreign_key_checks=1; SET unique_checks=1; SET autocommit=1;"'
                    f' {database}'
                )

                self._exe_command(rollback_cmd, cwd=mysql_bin_dir)

                error_msg = "\n".join([line for line in output if line.strip()])
                logger.error(f"MySQL导入失败 - exit_code: {exit_code}, 错误: {error_msg}")
                return False

        except Exception as e:
            logger.error(f"导入执行异常: {str(e)}")
            return False
