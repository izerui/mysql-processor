import os
import platform
import sys
from pathlib import Path
from subprocess import Popen, PIPE, TimeoutExpired


class BaseShell(object):
    """基础Shell命令执行类"""

    def _get_exe_path(self):
        """根据操作系统获取可执行文件路径"""
        system = platform.system()
        if system == 'Windows':
            return 'win\\x64'
        elif system == 'Darwin':
            return 'mac/arm64'
        elif system == 'Linux':
            return 'linux/x64'
        else:
            raise BaseException(f'不支持的操作系统: {system}')

    def _get_mysql_client_path(self):
        """获取mysql-client目录的绝对路径"""
        # 获取当前文件所在目录
        current_dir = os.path.dirname(os.path.abspath(__file__))
        # 获取项目根目录（src的父目录）
        project_root = os.path.dirname(current_dir)
        # 优先使用自动下载的MySQL官方版本
        mysql_official_path = os.path.join(project_root, 'mysql')
        if os.path.exists(mysql_official_path):
            return mysql_official_path
        # 回退到mysql-client目录
        return os.path.join(project_root, 'mysql-client')

    def _get_mysqldump_exe(self):
        """获取mysqldump可执行文件完整路径"""
        mysql_path = self._get_mysql_client_path()
        mysqldump_exe = 'mysqldump.exe' if platform.system() == 'Windows' else 'mysqldump'

        # 优先使用bin目录下的mysqldump
        bin_mysqldump = os.path.join(mysql_path, 'bin', mysqldump_exe)
        if os.path.exists(bin_mysqldump):
            return bin_mysqldump

        # 回退到旧的路径结构
        exe_path = self._get_exe_path()
        old_mysqldump = os.path.join(mysql_path, exe_path, mysqldump_exe)
        return old_mysqldump

    def _get_mysql_exe(self):
        """获取mysql可执行文件完整路径"""
        mysql_path = self._get_mysql_client_path()
        mysql_exe = 'mysql.exe' if platform.system() == 'Windows' else 'mysql'

        # 优先使用bin目录下的mysql
        bin_mysql = os.path.join(mysql_path, 'bin', mysql_exe)
        if os.path.exists(bin_mysql):
            return bin_mysql

        # 回退到旧的路径结构
        exe_path = self._get_exe_path()
        old_mysql = os.path.join(mysql_path, exe_path, mysql_exe)
        return old_mysql

    def _exe_command(self, command, timeout=3600, cwd=None):
        """
        执行 shell 命令并实时打印输出
        :param command: shell 命令
        :param timeout: 超时时间（秒），默认1小时
        :param cwd: 工作目录
        :return: (success: bool, exit_code: int, output: list)
        """
        print(f"执行命令: {command}")
        print(f"超时时间: {timeout}秒")

        try:
            # 使用更可靠的方式执行命令
            import subprocess

            # 对于shell命令，使用subprocess.run更可靠
            if '|' in command or '>' in command or '<' in command:
                # 包含管道或重定向的命令
                process = subprocess.run(
                    command,
                    shell=True,
                    capture_output=True,
                    text=True,
                    timeout=timeout,
                    cwd=cwd
                )

                output_lines = process.stdout.splitlines() if process.stdout else []
                error_lines = process.stderr.splitlines() if process.stderr else []

                # 实时输出
                for line in output_lines:
                    if line.strip():
                        print(line)

                for line in error_lines:
                    if line.strip():
                        print(f"STDERR: {line}", file=sys.stderr)

                exitcode = process.returncode
                all_output = output_lines + error_lines

            else:
                # 简单命令，使用Popen实时输出
                process = Popen(
                    command,
                    stdout=PIPE,
                    stderr=PIPE,
                    shell=True,
                    text=True,
                    bufsize=1,
                    universal_newlines=True,
                    cwd=cwd
                )

                output_lines = []
                error_lines = []

                try:
                    # 实时输出stdout并收集结果
                    if process.stdout:
                        for line in iter(process.stdout.readline, ''):
                            line = line.rstrip()
                            if line:
                                print(line)
                                output_lines.append(line)

                    # 实时输出stderr并收集错误信息
                    if process.stderr:
                        for line in iter(process.stderr.readline, ''):
                            line = line.rstrip()
                            if line:
                                print(f"STDERR: {line}", file=sys.stderr)
                                error_lines.append(line)

                    # 等待进程完成，带超时
                    exitcode = process.wait(timeout=timeout)
                    all_output = output_lines + error_lines

                except TimeoutExpired:
                    process.kill()
                    process.wait()
                    print(f'⏰ 命令执行超时 ({timeout}秒)')
                    return False, -1, output_lines + error_lines

            if exitcode == 0:
                print('✅ 命令执行成功')
                return True, exitcode, all_output
            else:
                print(f'❌ 命令执行失败 (exit code: {exitcode})')
                if error_lines:
                    print(f'错误信息: {"; ".join(error_lines[-5:])}')
                elif output_lines:
                    print(f'输出信息: {"; ".join(output_lines[-5:])}')
                return False, exitcode, all_output

        except subprocess.TimeoutExpired:
            print(f'⏰ 命令执行超时 ({timeout}秒)')
            return False, -1, ["命令执行超时"]
        except Exception as e:
            print(f'🚨 执行命令时发生异常: {str(e)}')
            return False, -1, [str(e)]


class Mysql:
    """MySQL连接配置类"""
    __slots__ = ['db_host', 'db_port', 'db_user', 'db_pass']

    def __init__(self, db_host, db_port, db_user, db_pass):
        self.db_host = db_host
        self.db_port = db_port
        self.db_user = db_user
        self.db_pass = db_pass
