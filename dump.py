# -*- coding: utf-8 -*-
import os
import platform
from subprocess import Popen, PIPE, STDOUT

mydumper_exe = 'mydumper'
myloader_exe = 'myloader'
mysql_exe = 'mysql'


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
                try:
                    print(line.decode().strip())
                except:
                    print(str(line))
        exitcode = process.wait()
        if exitcode != 0:
            print('错误: 命令执行失败, 继续下一条... ')
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
    使用mydumper导出数据库备份
    """

    def __init__(self, mysql):
        super().__init__()
        self.mysql = mysql

    def export_dbs(self, databases, dump_dir, threads=4):
        """
        使用mydumper导出数据库到指定目录
        :param databases: 数据库列表
        :param dump_dir: 导出目录路径
        :param threads: 并行线程数
        :return:
        """
        export_shell = f'''{mydumper_exe} \
            --host={self.mysql.db_host} \
            --user={self.mysql.db_user} \
            --password={self.mysql.db_pass} \
            --port={self.mysql.db_port} \
            --outputdir={dump_dir} \
            --database={' '.join(databases)} \
            --threads={threads} \
            --compress \
            --build-empty-files \
            --kill-long-queries \
            --verbose=3'''
        self._exe_command(export_shell)

    def export_tables(self, database, tables, dump_dir, threads=4):
        """
        使用mydumper导出指定表到指定目录
        :param database: 数据库
        :param tables: 数据表列表
        :param dump_dir: 导出目录路径
        :param threads: 并行线程数
        :return:
        """
        export_shell = f'''{mydumper_exe} \
            --host={self.mysql.db_host} \
            --user={self.mysql.db_user} \
            --password={self.mysql.db_pass} \
            --port={self.mysql.db_port} \
            --outputdir={dump_dir} \
            --database={database} \
            --tables={' '.join(tables)} \
            --threads={threads} \
            --compress \
            --build-empty-files \
            --kill-long-queries \
            --verbose=3'''
        self._exe_command(export_shell)


class MyImport(Shell):
    """
    使用myloader导入备份数据
    """

    def __init__(self, mysql):
        super().__init__()
        self.mysql = mysql

    def import_dump(self, dump_dir, threads=4):
        """
        使用myloader从指定目录导入备份数据
        :param dump_dir: mydumper导出的目录路径
        :param threads: 并行线程数
        :return:
        """
        import_shell = f'''{myloader_exe} \
            --host={self.mysql.db_host} \
            --user={self.mysql.db_user} \
            --password={self.mysql.db_pass} \
            --port={self.mysql.db_port} \
            --directory={dump_dir} \
            --threads={threads} \
            --compress-protocol \
            --verbose=3 \
            --overwrite-tables'''
        self._exe_command(import_shell)