import os
import platform
import sys
from logger_config import logger


class BaseShell(object):
    """基础Shell命令执行类"""

    def _get_exe_path(self):
        """根据操作系统获取可执行文件路径 - 已废弃，使用bin目录"""
        return 'bin'

    def _get_mysql_client_path(self):
        """获取MySQL官方版本的根目录"""
        # 获取当前文件所在目录
        current_dir = os.path.dirname(os.path.abspath(__file__))
        # 获取项目根目录（src的父目录）
        project_root = os.path.dirname(current_dir)
        # 使用自动下载的MySQL官方版本
        mysql_official_path = os.path.join(project_root, 'mysql')
        if not os.path.exists(mysql_official_path):
            raise BaseException(f'MySQL官方版本未安装: {mysql_official_path}')
        return mysql_official_path

    def _get_mysqldump_exe(self):
        """获取mysqldump可执行文件完整路径"""
        mysql_path = self._get_mysql_client_path()
        mysqldump_exe = 'mysqldump.exe' if platform.system() == 'Windows' else 'mysqldump'
        return os.path.join(mysql_path, 'bin', mysqldump_exe)

    def _get_mysql_exe(self):
        """获取mysql可执行文件完整路径"""
        mysql_path = self._get_mysql_client_path()
        mysql_exe = 'mysql.exe' if platform.system() == 'Windows' else 'mysql'
        return os.path.join(mysql_path, 'bin', mysql_exe)

    def _exe_command(self, command, cwd=None, success_msg=None):
        """
        执行 shell 命令并实时打印输出
        :param command: shell 命令
        :param cwd: 工作目录
        :param success_msg: 成功时的自定义消息
        :return: (success: bool, exit_code: int, output: list)
        """
        # 记录实际执行的命令
        # logger.info(f"执行命令: {command}")

        try:
            import subprocess

            # 统一使用subprocess.run执行所有命令
            process = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                cwd=cwd
            )

            output_lines = process.stdout.splitlines() if process.stdout else []
            error_lines = process.stderr.splitlines() if process.stderr else []

            # 实时输出（只输出非空行）
            for line in output_lines:
                if line.strip():
                    logger.info(f"  {line}")

            for line in error_lines:
                if line.strip():
                    if 'Using a password on the command' not in line:
                        logger.warning(f"  ⚠️ {line}")

            exitcode = process.returncode
            all_output = output_lines + error_lines

            if exitcode == 0:
                return True, exitcode, all_output
            else:
                logger.error(f'❌ 命令执行失败 (exit code: {exitcode})')
                return False, exitcode, all_output

        except Exception as e:
            logger.error(f'🚨 执行命令时发生异常: {str(e)}')
            return False, -1, [str(e)]


class Mysql:
    """MySQL连接配置类"""
    __slots__ = ['db_host', 'db_port', 'db_user', 'db_pass']

    def __init__(self, db_host, db_port, db_user, db_pass):
        self.db_host = db_host
        self.db_port = db_port
        self.db_user = db_user
        self.db_pass = db_pass
