import os
import platform
from subprocess import Popen, PIPE, STDOUT

mysqlpump_exe = 'mysqlpump'
mysql_exe = 'mysql'
if platform.system() == 'Windows':
    exe_path = 'win\\x64'
    mysqldump_exe = 'mysqlpump.exe'
    mysql_exe = 'mysql.exe'
elif platform.system() == 'Linux':
    raise BaseException('暂不支持')
elif platform.system() == 'Darwin':
    exe_path = 'mac/arm64'


class Shell(object):

    def _exe_command(self, command):
        """
        执行 shell 命令并实时打印输出
        :param command: shell 命令
        :return: process, exitcode
        """
        print(command)
        process = Popen(command, stdout=PIPE, stderr=STDOUT, shell=True)
        with process.stdout:
            for line in iter(process.stdout.readline, b''):
                print(line.decode().strip())
        exitcode = process.wait()
        if exitcode != 0:
            raise BaseException('命令执行失败')
        return process, exitcode


class Mysql:
    __slots__ = ['db_host', 'db_port', 'db_user', 'db_pass']

    def __init__(self, db_host, db_port, db_user, db_pass):
        self.db_host = db_host
        self.db_port = db_port
        self.db_user = db_user
        self.db_pass = db_pass


class MyDump(Shell):
    """
    导出数据库备份到sql文件
    """

    def __init__(self, mysql: Mysql, ignore_tables: list):
        super().__init__()
        self.mysql = mysql
        self.ignore_tables = ignore_tables
        if not self.ignore_tables:
            self.ignore_tables = ['non_existent_table']

    def export_dbs(self, databases, dump_file):
        """
        导出数据库到dump_sql
        :param databases: 数据库列表
        :param dump_file: dump_sql文件路径
        :return:
        """
        # https://www.cnblogs.com/kevingrace/p/9760185.html
        export_shell = f'''{os.path.join('mysql-client', exe_path, mysqlpump_exe)} \
            -h {self.mysql.db_host} \
            -u {self.mysql.db_user} \
            -p{self.mysql.db_pass} \
            --port={self.mysql.db_port} \
            --default-character-set=utf8 \
            --set-gtid-purged=OFF \
            --skip-routines \
            --skip-triggers \
            --skip-add-locks \
            --skip-events \
            --exclude-tables={",".join(self.ignore_tables)} \
            --skip-definer \
            --add-drop-database \
            --complete-insert \
            --compress \
            --skip-tz-utc \
            --max_allowed_packet=10240 \
            --net_buffer_length=4096 \
            --default-parallelism=6 \
            --watch-progress \
            --databases {' '.join(databases)} > {dump_file}'''
        self._exe_command(export_shell)


class MyImport(Shell):
    """
    从sql文件导入
    """

    def __init__(self, mysql: Mysql):
        super().__init__()
        self.mysql = mysql

    def import_sql(self, sql_file):
        """
        读取sql文件并导入到mysql中
        :param sql_file: sql文件路径
        :return:
        """
        import_shell = f'{os.path.join("mysql-client", exe_path, mysql_exe)} -v --host={self.mysql.db_host} --user={self.mysql.db_user} --password={self.mysql.db_pass} --port={self.mysql.db_port} --default-character-set=utf8 --max_allowed_packet=1048576 --net_buffer_length=4096 < {sql_file}'
        self._exe_command(import_shell)
