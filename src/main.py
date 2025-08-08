#!/usr/bin/env python3
"""MySQL Processor - 数据库备份导出导入工具 - 重构版"""

import os
import sys
import time
from configparser import ConfigParser
from pathlib import Path
from typing import List, Dict, Any, Optional

from base import Mysql
from dump import MyDump
from logger_config import logger
from restore import MyRestore

from mysql_downloader import MySQLDownloader

def ensure_mysql_installed() -> str:
    """确保MySQL工具已安装，返回mysqldump路径"""
    logger.info("🔍 检查MySQL工具...")

    downloader = MySQLDownloader()

    if not downloader.is_mysql_installed():
        logger.info("📥 MySQL工具未找到，正在自动下载...")
        if not downloader.setup_mysql_tools():
            logger.error("MySQL工具下载失败，请手动安装或检查网络连接")
            sys.exit(1)
        logger.info("✅ MySQL工具下载完成")

    mysqldump_path = str(downloader.get_mysqldump_path())
    mysql_dir = downloader.mysql_dir

    # 设置环境变量
    mysql_bin_path = str(mysql_dir / 'bin')
    if 'PATH' not in os.environ:
        os.environ['PATH'] = mysql_bin_path
    elif mysql_bin_path not in os.environ['PATH']:
        os.environ['PATH'] = f"{mysql_bin_path}:{os.environ['PATH']}"

    logger.info(f"📍 使用mysqldump路径: {mysqldump_path}")
    return mysqldump_path


def load_config() -> Dict[str, Any]:
    """加载配置文件"""
    config = ConfigParser()
    config_path = Path(__file__).parent.parent / 'config.ini'

    if not config_path.exists():
        logger.error(f"配置文件不存在: {config_path}")
        sys.exit(1)
    config.read(config_path)

    # 解析配置
    databases = [db.strip() for db in config.get('global', 'databases', fallback='').split(',') if db.strip()]

    if not databases:
        logger.error("配置文件中未指定数据库")
        sys.exit(1)

    return {
        'databases': databases,
        'delete_after_import': config.getboolean('global', 'delete_after_import', fallback=True),
        'export_threads': config.getint('global', 'export_threads', fallback=8),
        'import_threads': config.getint('global', 'import_threads', fallback=8),
        'split_threshold_mb': config.getint('global', 'split_threshold', fallback=200),
        'commit_frequency': config.getint('global', 'commit_frequency', fallback=100),
        'do_export': config.getboolean('global', 'do_export', fallback=True),
        'source': {
            'host': config.get('source', 'db_host'),
            'port': config.get('source', 'db_port'),
            'user': config.get('source', 'db_user'),
            'password': config.get('source', 'db_pass')
        },
        'target': {
            'host': config.get('target', 'db_host'),
            'port': config.get('target', 'db_port'),
            'user': config.get('target', 'db_user'),
            'password': config.get('target', 'db_pass')
        }
    }


def cleanup_dump_folder(dump_folder: Path) -> None:
    """清理历史导出目录"""
    if dump_folder.exists():
        import shutil
        # 只删除目录内容，不删除目录本身（云盘挂载路径）
        for item in dump_folder.iterdir():
            if item.is_file():
                item.unlink()
            elif item.is_dir():
                shutil.rmtree(item)
        logger.cleanup(str(dump_folder))


def process_single_database(db: str,
                            source: Dict[str, str], target: Dict[str, str],
                            dump_folder, delete_after_import: bool,
                            export_threads: int = 8, import_threads: int = 8, split_threshold_mb: int = 500, commit_frequency: int = 50, do_export: bool = True) -> Dict[str, Any]:
    """处理单个数据库的完整流程"""
    result = {
        'database': db,
        'status': 'success',
        'error': None,
        'export_duration': 0,
        'import_duration': 0,
        'tables_exported': 0,
        'tables_imported': 0,
        'total_export_size_mb': 0
    }

    try:
        sql_file = dump_folder / f"{db}.sql"

        # 创建MySQL连接对象
        source_mysql = Mysql(source['host'], source['port'], source['user'], source['password'])
        target_mysql = Mysql(target['host'], target['port'], target['user'], target['password'])

        # 导出阶段
        export_start = time.time()

        if do_export:
            exporter = MyDump(source_mysql, split_threshold_mb, export_threads, commit_frequency)
            export_success = exporter.export_db(db, str(sql_file))

            result['export_duration'] = time.time() - export_start

            if not export_success:
                result['status'] = 'failed'
                result['error'] = '导出失败'
                return result
        else:
            logger.info(f"跳过导出")
            result['export_duration'] = 0

        # 导入阶段
        import_start = time.time()

        importer = MyRestore(target_mysql, import_threads)
        import_success = importer.restore_db(db, str(dump_folder))

        result['import_duration'] = time.time() - import_start

        if not import_success:
            result['status'] = 'failed'
            result['error'] = '导入失败'
            return result

        # 计算导出文件总大小
        total_size = 0
        if sql_file.exists():
            total_size += sql_file.stat().st_size

        db_folder = dump_folder / db
        if db_folder.exists():
            for file_path in db_folder.rglob('*.sql'):
                total_size += file_path.stat().st_size

        result['total_export_size_mb'] = total_size / 1024 / 1024

        # 清理阶段 - 只有导入成功后才根据配置决定是否删除
        if result['status'] == 'success' and delete_after_import:
            # 删除数据库结构文件
            if sql_file.exists():
                sql_file.unlink()

            # 删除数据库目录
            if db_folder.exists():
                import shutil
                shutil.rmtree(db_folder)

            logger.info(f"已清理导出文件: {db}")
        elif result['status'] == 'success' and not delete_after_import:
            logger.info(f"保留导出文件: {db}")
        else:
            logger.warning(f"导入失败，保留导出文件用于调试: {db}")

        return result

    except Exception as e:
        result['status'] = 'failed'
        result['error'] = str(e)
        return result


def main():
    """主函数：执行MySQL数据库备份导出导入流程"""
    start_time = time.time()

    # 确保MySQL已安装
    ensure_mysql_installed()

    # 加载配置
    config = load_config()

    # 记录系统启动信息
    logger.log_system_start(config['databases'])

    # 设置导出目录
    dump_folder = Path(__file__).parent.parent / 'dumps'
    # 清理历史导出目录,如果配置不导出则不清理
    if config['do_export']:
        cleanup_dump_folder(dump_folder)
        dump_folder.mkdir(exist_ok=True)

    # 处理所有数据库
    results = []

    for idx, db in enumerate(config['databases'], 1):

        result = process_single_database(
            db,
            config['source'],
            config['target'],
            dump_folder,
            config['delete_after_import'],
            config['export_threads'],
            config['import_threads'],
            config['split_threshold_mb'],
            config['commit_frequency'],
            config['do_export']
        )

        results.append(result)

        # 显示当前数据库处理结果
        if result['status'] == 'success':
            logger.success(
                f"数据库 [{db}] 处理完成 - 导出耗时: {result['export_duration']:.1f}s, "
                f"导入耗时: {result['import_duration']:.1f}s, "
                f"总耗时: {result['export_duration'] + result['import_duration']:.1f}s, "
                f"处理文件: {result['total_export_size_mb']:.1f}MB"
            )
        else:
            logger.error(f"数据库 {db} 处理失败: {result['error']}")

    # 显示最终汇总
    total_duration = time.time() - start_time
    logger.log_summary(results, total_duration)

    # 程序结束
    logger.info("💤 程序执行完成，进入休眠状态...")

    try:
        while True:
            time.sleep(3600)  # 每小时检查一次
    except KeyboardInterrupt:
        logger.info("收到退出信号，程序结束")
        sys.exit(0)


if __name__ == "__main__":
    main()
