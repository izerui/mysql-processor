import os
import sys
import time
import concurrent.futures
from pathlib import Path
from base import BaseShell, Mysql
from logger_config import logger


class MyRestore(BaseShell):
    """
    从SQL文件导入到MySQL数据库
    支持分步骤导入：先导入库结构，再并发导入表数据
    """

    def __init__(self, mysql: Mysql):
        super().__init__()
        self.mysql = mysql

    def restore_db(self, database, dump_folder):
        """
        从SQL文件导入整个数据库
        :param database: 数据库名
        :param dump_folder: 导出文件夹路径
        :return: bool 成功返回True，失败返回False
        """
        try:
            # 1. 先导入数据库结构文件
            structure_file = os.path.join(dump_folder, f"{database}.sql")
            if not os.path.exists(structure_file):
                raise RuntimeError(f"数据库结构文件不存在: {structure_file}")

            logger.info(f"🔄 开始导入数据库结构: {database}")
            if not self._restore_single_file(structure_file, database):
                return False

            # 2. 获取所有表数据文件
            db_data_folder = os.path.join(dump_folder, database)
            if not os.path.exists(db_data_folder):
                logger.info(f"✅ 数据库 {database} 无表数据文件，跳过表数据导入")
                return True

            # 收集所有数据文件
            all_data_files = []
            for file in os.listdir(db_data_folder):
                if file.endswith('.sql'):
                    file_path = os.path.join(db_data_folder, file)
                    if os.path.getsize(file_path) > 0:  # 跳过空文件
                        all_data_files.append(file_path)

            if not all_data_files:
                logger.info(f"✅ 数据库 {database} 无有效表数据需要导入")
                return True

            # 3. 使用8线程并发导入所有表数据文件
            logger.info(f"🔄 开始并发导入 {len(all_data_files)} 个表数据文件...")
            start_time = time.time()

            with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
                futures = []
                for sql_file in all_data_files:
                    future = pool.submit(self._restore_single_file, sql_file, database)
                    futures.append((sql_file, future))

                # 等待所有任务完成
                failed_files = []
                for sql_file, future in futures:
                    try:
                        success = future.result()
                        if not success:
                            failed_files.append(os.path.basename(sql_file))
                    except Exception as e:
                        logger.error(f"❌ 导入文件 {sql_file} 失败: {str(e)}")
                        failed_files.append(os.path.basename(sql_file))

            duration = time.time() - start_time

            if failed_files:
                logger.error(f"❌ 以下文件导入失败: {', '.join(failed_files)}")
                return False

            logger.info(f'✅ 数据库 {database} 导入完成 (耗时: {duration:.2f}秒)')
            return True

        except Exception as e:
            logger.error(f"❌ 导入数据库 {database} 失败: {str(e)}")
            return False

    def _restore_single_file(self, sql_file, database=None):
        """导入单个SQL文件"""
        try:
            if not os.path.exists(sql_file):
                raise RuntimeError(f"SQL文件不存在: {sql_file}")

            # 检查文件大小，跳过空文件
            file_size = os.path.getsize(sql_file)
            if file_size == 0:
                logger.info(f"⏭️ 跳过空文件: {os.path.basename(sql_file)}")
                return True

            mysql_path = self._get_mysql_exe()
            mysql_bin_dir = os.path.dirname(mysql_path)

            # 构建mysql命令，使用--init-command优化导入性能
            init_commands = [
                "SET autocommit=0",
                "SET foreign_key_checks=0",
                "SET unique_checks=0",
                "SET SESSION innodb_lock_wait_timeout=3600"
            ]

            init_command_str = ";".join(init_commands)

            # 构建mysql命令
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
            )

            # 如果有指定数据库，直接导入到该数据库
            if database:
                cmd += f" {database}"

            import_shell = f'{cmd} < "{sql_file}"'

            logger.info(f"🔄 开始导入: {os.path.basename(sql_file)} ({file_size / 1024 / 1024:.2f}MB)")

            start_time = time.time()
            success, exit_code, output = self._exe_command(
                import_shell,
                cwd=mysql_bin_dir
            )
            duration = time.time() - start_time

            if not success:
                error_msg = "\n".join([line for line in output if line.strip()])
                raise RuntimeError(f"MySQL导入失败，exit code: {exit_code}\n{error_msg}")

            logger.info(f'✅ 文件导入成功: {os.path.basename(sql_file)} (耗时: {duration:.2f}秒)')
            return True

        except RuntimeError as e:
            logger.error(f"❌ 导入文件失败: {str(e)}")
            return False
        except Exception as e:
            logger.error(f"❌ 导入过程发生错误: {str(e)}")
            return False

    def restore_db_legacy(self, sql_file):
        """
        兼容旧版本的单文件导入方法
        :param sql_file: SQL文件路径
        :return: bool 成功返回True，失败返回False
        """
        logger.warning("⚠️ 使用旧版导入方法，建议改用新的分步导入方式")
        return self._restore_single_file(sql_file)
