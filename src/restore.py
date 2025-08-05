import os
import sys
import logging

from base import BaseShell, Mysql

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)


class MyRestore(BaseShell):
    """
    从SQL文件导入到MySQL数据库
    """

    def __init__(self, mysql: Mysql, max_allowed_packet: str, net_buffer_length: str):
        super().__init__()
        self.mysql = mysql
        self.max_allowed_packet = max_allowed_packet
        self.net_buffer_length = net_buffer_length

    def restore_db(self, sql_file, target_database=None):
        """
        从SQL文件导入到MySQL数据库
        :param sql_file: SQL文件路径
        :param target_database: 目标数据库名（可选）
        :return: bool 成功返回True，失败返回False
        """
        try:
            if not os.path.exists(sql_file):
                raise RuntimeError(f"SQL文件不存在: {sql_file}")

            mysql_path = self._get_mysql_exe()

            # 获取mysql的bin目录作为工作目录
            mysql_bin_dir = os.path.dirname(mysql_path)

            # 构建mysql命令
            cmd = f'{mysql_path} -h {self.mysql.db_host} -u {self.mysql.db_user} -p\'{self.mysql.db_pass}\' --port={self.mysql.db_port} --default-character-set=utf8 --max_allowed_packet={self.max_allowed_packet} --net_buffer_length={self.net_buffer_length}'

            # 如果指定了目标数据库
            if target_database:
                cmd += f' {target_database}'

            # 完整的导入命令
            import_shell = f'{cmd} < "{sql_file}"'

            logger.info("正在导入数据库...")
            logger.info(f"SQL文件: {sql_file}")
            if target_database:
                logger.info(f"目标数据库: {target_database}")

            # 使用BaseShell的_exe_command方法执行命令
            success, exit_code, output = self._exe_command(
                import_shell,
                cwd=mysql_bin_dir
            )

            # 显示输出
            for line in output:
                if line.strip():
                    logger.info(f"  {line}")

            if not success:
                raise RuntimeError(f"MySQL导入失败，exit code: {exit_code}")

            logger.info('✅ 数据库导入成功')
            return True

        except RuntimeError as e:
            raise e
        except Exception as e:
            logger.error(f"❌ 导入过程发生错误: {str(e)}")
            return False
