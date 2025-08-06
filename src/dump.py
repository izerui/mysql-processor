import os
import shutil

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

    def _check_pv_available(self):
        """检查pv工具是否可用"""
        return shutil.which('pv') is not None

    def export_db(self, database, dump_file, tables=None):
        """
        使用mysqldump导出单个数据库到SQL文件
        :param database: 数据库名
        :param dump_file: 导出的SQL文件路径
        :param tables: 表名列表，默认为None导出所有表
        :return:
        """
        try:
            # 确保输出目录存在
            os.makedirs(os.path.dirname(dump_file), exist_ok=True)

            mysqldump_path = self._get_mysqldump_exe()

            # 构建mysqldump命令，使用完整路径
            if tables and tables != ['*']:
                # 指定表导出
                cmd = f'{mysqldump_path} -h {self.mysql.db_host} -u {self.mysql.db_user} -p"{self.mysql.db_pass}" --port={self.mysql.db_port} --default-character-set=utf8 --set-gtid-purged=OFF --skip-routines --skip-triggers --skip-add-locks --disable-keys --skip-events --skip-set-charset --compact --add-drop-database --extended-insert --complete-insert --quick --skip-lock-tables --no-autocommit --compress --skip-tz-utc --max-allowed-packet=256M --net-buffer-length=65536 {database} {" ".join(tables)}'
            else:
                # 完整数据库导出
                cmd = f'{mysqldump_path} -h {self.mysql.db_host} -u {self.mysql.db_user} -p"{self.mysql.db_pass}" --port={self.mysql.db_port} --default-character-set=utf8 --set-gtid-purged=OFF --skip-routines --skip-triggers --skip-add-locks --disable-keys --skip-events --skip-set-charset --compact --add-drop-database --extended-insert --complete-insert --quick --skip-lock-tables --no-autocommit --compress --skip-tz-utc --max-allowed-packet=256M --net-buffer-length=65536 {database}'

            # 获取mysqldump的bin目录作为工作目录
            mysqldump_bin_dir = os.path.dirname(mysqldump_path)

            # 使用标准mysqldump命令
            full_command = f'{cmd} > {dump_file}'
            logger.info("正在导出数据库...")

            # 使用BaseShell的_exe_command方法执行命令
            success, exit_code, output = self._exe_command(
                full_command,
                cwd=mysqldump_bin_dir
            )

            if not success:
                raise RuntimeError(f"mysqldump导出失败，exit code: {exit_code}")

            logger.info('✅ 命令执行成功')
            return True

        except RuntimeError as e:
            raise e
        except Exception as e:
            raise RuntimeError(f"导出过程发生错误: {str(e)}")
