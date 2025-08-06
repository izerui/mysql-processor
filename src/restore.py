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

            # 构建mysql命令
            cmd = f'{mysql_path} -h {self.mysql.db_host} -u {self.mysql.db_user} -p\'{self.mysql.db_pass}\' --port={self.mysql.db_port} --default-character-set=utf8 --max_allowed_packet=268435456 --net_buffer_length=1048576'

            # 完整的导入命令
            import_shell = f'{cmd} < "{sql_file}"'

            logger.info(f"正在导入SQL文件: {sql_file}")

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

            logger.info(f'✅ SQL文件导入成功: {sql_file} (耗时: {duration:.2f}秒)')
            return True

        except RuntimeError as e:
            raise e
        except Exception as e:
            logger.error(f"❌ 导入过程发生错误: {str(e)}")
            return False
