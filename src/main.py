#!/usr/bin/env python3
"""MySQL Processor - 数据库备份导出导入工具"""

import os
import sys
import shutil
from pathlib import Path
from configparser import ConfigParser

from mydumper import MyDumper
from myloader import MyLoader
from base import Mysql



# 导入MyDumper安装器
try:
    from mydumper_downloader import MyDumperDownloader
except ImportError:
    from mydumper_downloader import MyDumperDownloader


def ensure_mydumper_installed():
    """确保MyDumper工具已安装"""
    downloader = MyDumperDownloader()

    if not downloader.is_mydumper_installed():
        print("🔍 MyDumper工具未找到，正在自动安装...")
        if not downloader.setup_mydumper_tools():
            print("❌ MyDumper工具安装失败，请手动安装或检查网络连接")
            sys.exit(1)
        print("✅ MyDumper工具安装完成")

    mydumper_path = downloader.get_mydumper_path()
    myloader_path = downloader.get_myloader_path()

    return mydumper_path, myloader_path


def main():
    """主函数：执行MySQL数据库备份导出导入流程"""
    # 确保MyDumper工具已安装
    mydumper_path, myloader_path = ensure_mydumper_installed()
    print(f"📍 使用 mydumper: {mydumper_path}")
    print(f"📍 使用 myloader: {myloader_path}")

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
        db_output_dir = f'{dump_folder}/{db}'
        print(f'---------------------------------------------> 从{source.db_host}导出: {db}')
        try:
            exporter = MyDumper(source)
            exporter.export_database(
                db,
                db_output_dir,
                threads=8,
                rows=500000,
                chunk_filesize=256,
                no_lock=True
            )
            print(f'---------------------------------------------> 成功 从{source.db_host}导出: {db}')
        except RuntimeError as e:
            print(f'---------------------------------------------> 导出失败: {str(e)}')
            _safe_remove(db_output_dir)


def _import_databases(target, databases, dump_folder, max_packet, buffer_len):
    """导入所有数据库"""
    for db in databases:
        db_input_dir = f'{dump_folder}/{db}'
        print(f'---------------------------------------------> 导入{target.db_host}: {db}')
        try:
            loader = MyLoader(target, max_packet, buffer_len)
            if loader.validate_backup(db_input_dir):
                loader.import_database(
                    db_input_dir,
                    db,
                    threads=8
                )
                print(f'---------------------------------------------> 成功 导入{target.db_host}: {db}')
                _safe_remove(db_input_dir, keep_on_error=False)
            else:
                raise RuntimeError("备份验证失败")
        except RuntimeError as e:
            print(f'---------------------------------------------> 导入失败: {str(e)}')
            print(f'--------------------------------------------->> 保留文件用于调试: {db_input_dir}')


def _safe_remove(path, keep_on_error=True):
    """安全删除文件或目录"""
    if not os.path.exists(path):
        return

    try:
        if os.path.isdir(path):
            shutil.rmtree(path)
            msg = '删除失败的临时目录' if keep_on_error else '成功删除'
        else:
            os.remove(path)
            msg = '删除失败的临时文件' if keep_on_error else '成功删除'
        print(f'--------------------------------------------->> {msg}: {path}')
    except Exception as e:
        print(f'--------------------------------------------->> 删除文件失败: {str(e)}')


if __name__ == "__main__":
    main()
