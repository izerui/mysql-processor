import os
import sys

from src.base import BaseShell, Mysql


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

            # 使用BaseShell的_exe_command方法执行命令
            success, exit_code, output = self._exe_command(
                import_shell,
                timeout=3600,
                cwd=mysql_bin_dir
            )

            # 显示输出
            for line in output:
                if line.strip():
                    print(f"  {line}")

            if not success:
                raise RuntimeError(f"MySQL导入失败，exit code: {exit_code}")

            print('✅ SQL文件导入成功')
            return True

        except RuntimeError as e:
            raise e
        except Exception as e:
            raise RuntimeError(f"导入过程发生错误: {str(e)}")
