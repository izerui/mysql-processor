#!/usr/bin/env python3
"""MySQL Processor - 数据库备份导出导入工具"""

import os
import sys
from pathlib import Path
from configparser import ConfigParser

from dump import MyDump
from restore import MyRestore
from base import Mysql



# 导入MySQL下载器
try:
    from mysql_downloader import MySQLDownloader
except ImportError:
    from mysql_downloader import MySQLDownloader


def ensure_mysql_installed():
    """确保MySQL工具已安装"""
    downloader = MySQLDownloader()

    if not downloader.is_mysql_installed():
        print("🔍 MySQL工具未找到，正在自动下载...")
        if not downloader.setup_mysql_tools():
            print("❌ MySQL工具下载失败，请手动安装或检查网络连接")
            sys.exit(1)
        print("✅ MySQL工具下载完成")

    mysqldump_path = downloader.get_mysqldump_path()
    mysql_dir = downloader.mysql_dir

    # 设置环境变量，让子进程能找到MySQL工具
    mysql_bin_path = str(mysql_dir / 'bin')
    if 'PATH' not in os.environ:
        os.environ['PATH'] = mysql_bin_path
    elif mysql_bin_path not in os.environ['PATH']:
        os.environ['PATH'] = f"{mysql_bin_path}:{os.environ['PATH']}"

    return mysqldump_path


def main():
    """主函数：执行MySQL数据库备份导出导入流程"""
    # 确保MySQL工具已安装
    mysqldump_path = ensure_mysql_installed()
    print(f"📍 使用 mysqldump: {mysqldump_path}")

    config = ConfigParser()
    config_path = Path(__file__).parent.parent / 'config.ini'
    config.read(config_path)

    source = Mysql(config.get('source', 'db_host'), config.get('source', 'db_port'), config.get('source', 'db_user'),
                   config.get('source', 'db_pass'))
    target = Mysql(config.get('target', 'db_host'), config.get('target', 'db_port'), config.get('target', 'db_user'),
                   config.get('target', 'db_pass'))
    import_max_allowed_packet = config.get('global', 'import_max_allowed_packet')
    import_net_buffer_length = config.get('global', 'import_net_buffer_length')

    databases = config.get('global', 'databases').split(',')
    dump_folder = Path(__file__).parent.parent / 'dumps'
    dump_folder.mkdir(exist_ok=True)

    _export_databases(source, databases, str(dump_folder))
    _import_databases(target, databases, str(dump_folder), import_max_allowed_packet, import_net_buffer_length)


def _export_databases(source, databases, dump_folder):
    """导出所有数据库"""
    for db in databases:
        sql_file = f'{dump_folder}/{db}.sql'
        print(f'---------------------------------------------> 从{source.db_host}导出: {db}')
        try:
            exporter = MyDump(source)
            exporter.export_dbs([db], sql_file)
            print(f'---------------------------------------------> 成功 从{source.db_host}导出: {db}')
        except RuntimeError as e:
            print(f'---------------------------------------------> 导出失败: {str(e)}')
            _safe_remove(sql_file)


def _import_databases(target, databases, dump_folder, max_packet, buffer_len):
    """导入所有数据库"""
    for db in databases:
        sql_file = f'{dump_folder}/{db}.sql'
        print(f'---------------------------------------------> 导入{target.db_host}: {db}')
        try:
            MyRestore(target, max_packet, buffer_len).restore_db(sql_file)
            print(f'---------------------------------------------> 成功 导入{target.db_host}: {db}')
            _safe_remove(sql_file, keep_on_error=False)
        except RuntimeError as e:
            print(f'---------------------------------------------> 导入失败: {str(e)}')
            print(f'--------------------------------------------->> 保留文件用于调试: {sql_file}')


def _safe_remove(path, keep_on_error=True):
    """安全删除文件"""
    if not os.path.exists(path):
        return
    try:
        os.remove(path)
        msg = '删除失败的临时文件' if keep_on_error else '成功删除'
        print(f'--------------------------------------------->> {msg}: {path}')
    except Exception as e:
        print(f'--------------------------------------------->> 删除文件失败: {str(e)}')


if __name__ == "__main__":
    main()
