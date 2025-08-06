import os
import sys
import time
import concurrent.futures
from pathlib import Path
from typing import List, Optional, Dict, Any
from colorama import Fore
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

    def restore_db(self, database: str, dump_folder: str) -> bool:
        """
        从SQL文件导入整个数据库，提供清晰的进度显示
        :param database: 数据库名
        :param dump_folder: 导出文件夹路径
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

            logger.info(f"开始导入数据库结构...")
            if not self._import_structure(structure_file, database):
                return False

            # 2. 获取所有表数据文件
            db_data_folder = os.path.join(dump_folder, database)
            if not os.path.exists(db_data_folder):
                logger.info(f"ℹ️ 数据库 {database} 无表数据文件，跳过表数据导入")
                logger.log_database_complete(database, "导入", time.time() - start_time)
                return True

            # 收集所有数据文件
            data_files = self._collect_data_files(db_data_folder)
            if not data_files:
                logger.info(f"ℹ️ 数据库 {database} 无有效表数据需要导入")
                logger.log_database_complete(database, "导入", time.time() - start_time)
                return True

            # 3. 并发导入表数据
            logger.info(f"开始并发导入 {len(data_files)} 个表数据文件...")
            success_count = self._import_tables_data(database, data_files)

            total_duration = time.time() - start_time
            if success_count == len(data_files):
                logger.log_database_complete(database, "导入", total_duration)
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
            file_size = os.path.getsize(structure_file) / 1024 / 1024
            logger.info(f"导入数据库结构文件 ({file_size:.1f}MB)")

            start_time = time.time()
            success = self._execute_import(structure_file, database)

            if success:
                duration = time.time() - start_time
                logger.info(f"\n{Fore.GREEN}   📊 数据库结构导入完成")
                logger.info(f"{Fore.GREEN}   ⏰ 耗时: {duration:.2f}秒")
                logger.info(f"{Fore.GREEN}   {'=' * 30}\n")
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
                else:
                    logger.info(f"⏭️ 跳过空文件: {file}")

        return data_files

    def _import_tables_data(self, database: str, data_files: List[str]) -> int:
        """并发导入所有表数据"""
        import_start = time.time()
        success_count = 0
        failed_files = []

        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
            # 提交所有导入任务
            futures = []
            for idx, sql_file in enumerate(data_files):
                future = pool.submit(
                    self._import_single_table,
                    sql_file, database, idx + 1, len(data_files)
                )
                futures.append((sql_file, future))

            # 收集结果 - 使用as_completed实现异步显示
            for future in concurrent.futures.as_completed([f for _, f in futures]):
                sql_file = None
                try:
                    # 找到对应的文件名
                    sql_file = next(f_path for f_path, f_obj in futures if f_obj == future)
                    result = future.result()
                    if result['success']:
                        success_count += 1
                        logger.log_table_complete(
                            database,
                            os.path.basename(sql_file).replace('.sql', ''),
                            result['duration'],
                            result['size_mb']
                        )
                    else:
                        failed_files.append(os.path.basename(sql_file))
                        logger.error(f"文件导入失败 - 文件: {os.path.basename(sql_file)}, 错误: {result['error']}")
                except Exception as e:
                    if sql_file:
                        failed_files.append(os.path.basename(sql_file))
                    logger.error(f"文件导入异常 - 文件: {os.path.basename(sql_file) or 'unknown'}, 错误: {str(e)}")

                # 更新批量进度
                progress = (success_count + len(failed_files)) / len(data_files) * 100
                logger.log_batch_progress(
                    "表数据导入",
                    success_count + len(failed_files),
                    len(data_files),
                    len(failed_files)
                )

        import_duration = time.time() - import_start
        logger.info(f"📊 表数据导入统计 - 成功: {success_count}, 失败: {len(failed_files)}, 总计: {len(data_files)}, 耗时: {import_duration:.1f}s")

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
            table_name = os.path.basename(sql_file).replace('.sql', '')

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

            start_time = time.time()
            success, exit_code, output = self._exe_command(
                import_command, cwd=mysql_bin_dir
            )
            duration = time.time() - start_time

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

    def restore_db_legacy(self, sql_file: str) -> bool:
        """兼容旧版本的单文件导入方法"""
        logger.warning("⚠️ 使用旧版导入方法，建议改用新的分步导入方式")
        return self._execute_import(sql_file, None)
