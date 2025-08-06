import os
import sys
import time
from base import BaseShell, Mysql
from logger_config import logger


class MyRestore(BaseShell):
    """
    从SQL文件导入到MySQL数据库
    """

    def __init__(self, mysql: Mysql):
        super().__init__()
        self.mysql = mysql

    def restore_db(self, sql_file):
        """
        从SQL文件导入到MySQL数据库
        :param sql_file: SQL文件路径
        :return: bool 成功返回True，失败返回False
        """
        try:
            if not os.path.exists(sql_file):
                raise RuntimeError(f"SQL文件不存在: {sql_file}")

            mysql_path = self._get_mysql_exe()

            # 获取mysql的bin目录作为工作目录
            mysql_bin_dir = os.path.dirname(mysql_path)

            # 构建mysql命令，使用--init-command优化导入性能
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
            )

            # 完整的导入命令，不自动恢复设置，需要手动提交
            import_shell = f'{cmd} < "{sql_file}"'

            logger.info(f"🔄 开始导入SQL文件: {os.path.basename(sql_file)}")

            start_time = time.time()

            # 使用BaseShell的_exe_command方法执行命令
            success, exit_code, output = self._exe_command(
                import_shell,
                cwd=mysql_bin_dir
            )

            duration = time.time() - start_time

            # 显示输出
            for line in output:
                if line.strip():
                    logger.info(f"  {line}")

            if not success:
                raise RuntimeError(f"MySQL导入失败，exit code: {exit_code}")

            logger.info(f'✅ SQL文件导入成功: {os.path.basename(sql_file)} (耗时: {duration:.2f}秒)')
            return True

        except RuntimeError as e:
            raise e
        except Exception as e:
            logger.error(f"❌ 导入过程发生错误: {str(e)}")
            return False
