import os
import subprocess
import sys

from base import BaseShell, Mysql


class MyImport(BaseShell):
    """
    从SQL文件导入到MySQL数据库
    """

    def __init__(self, mysql: Mysql, max_allowed_packet: str, net_buffer_length: str):
        super().__init__()
        self.mysql = mysql
        self.max_allowed_packet = max_allowed_packet
        self.net_buffer_length = net_buffer_length

    def import_sql(self, sql_file):
        """
        读取SQL文件并导入到MySQL中
        :param sql_file: SQL文件路径
        :return:
        """
        try:
            if not os.path.exists(sql_file):
                raise RuntimeError(f"SQL文件不存在: {sql_file}")

            mysql_path = self._get_mysql_exe()

            # 获取mysql的bin目录作为工作目录
            mysql_bin_dir = os.path.dirname(mysql_path)

            # 构建mysql命令，使用完整路径（暂时移除pv）
            import_shell = f'{mysql_path} -v --host={self.mysql.db_host} --user={self.mysql.db_user} --password={self.mysql.db_pass} --port={self.mysql.db_port} --default-character-set=utf8 --max_allowed_packet={self.max_allowed_packet} --net_buffer_length={self.net_buffer_length} < {sql_file}'

            print(f"📥 开始导入SQL文件: {sql_file}")
            print(f"执行命令: {import_shell}")

            # 执行命令，在mysql的bin目录下运行
            result = subprocess.run(
                import_shell,
                shell=True,
                capture_output=True,
                text=True,
                timeout=3600,
                cwd=mysql_bin_dir
            )

            if result.stdout:
                print("📊 导入输出:")
                for line in result.stdout.splitlines():
                    if line.strip():
                        print(f"  {line}")

            if result.returncode != 0:
                error_msg = f"MySQL导入失败，exit code: {result.returncode}"
                if result.stderr:
                    error_msg += f"\n错误详情: {result.stderr.strip()}"
                if result.stdout:
                    error_msg += f"\n输出信息: {result.stdout.strip()}"
                raise RuntimeError(error_msg)

            print('✅ SQL文件导入成功')
            return True

        except subprocess.TimeoutExpired:
            raise RuntimeError("导入超时（超过1小时）")
        except Exception as e:
            raise RuntimeError(f"导入过程发生错误: {str(e)}")
