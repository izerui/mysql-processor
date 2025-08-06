#!/usr/bin/env python3
"""MySQL Processor - 数据库备份导出导入工具"""

import os
import sys
import time
from pathlib import Path
from configparser import ConfigParser

from dump import MyDump
from restore import MyRestore
from base import Mysql
from logger_config import logger



# 导入MySQL下载器
try:
    from mysql_downloader import MySQLDownloader
except ImportError:
    from mysql_downloader import MySQLDownloader


def ensure_mysql_installed():
    """确保MySQL工具已安装"""
    downloader = MySQLDownloader()

    if not downloader.is_mysql_installed():
        logger.info("🔍 MySQL工具未找到，正在自动下载...")
        if not downloader.setup_mysql_tools():
            logger.error("❌ MySQL工具下载失败，请手动安装或检查网络连接")
            sys.exit(1)
        logger.info("✅ MySQL工具下载完成")

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
    logger.info(f"📍 使用 mysqldump: {mysqldump_path}")

    config = ConfigParser()
    config_path = Path(__file__).parent.parent / 'config.ini'
    config.read(config_path)

    # 读取是否删除导出文件的配置
    delete_after_import = config.getboolean('global', 'delete_after_import', fallback=True)

    source = Mysql(config.get('source', 'db_host'), config.get('source', 'db_port'), config.get('source', 'db_user'),
                   config.get('source', 'db_pass'))
    target = Mysql(config.get('target', 'db_host'), config.get('target', 'db_port'), config.get('target', 'db_user'),
                   config.get('target', 'db_pass'))

    databases = config.get('global', 'databases').split(',')
    tables = config.get('global', 'tables').split(',')
    dump_folder = Path(__file__).parent.parent / 'dumps'

    # 清理历史文件和目录
    if dump_folder.exists():
        import shutil
        shutil.rmtree(dump_folder)
        logger.info(f"🧹 已清理历史导出目录: {dump_folder}")

    dump_folder.mkdir(exist_ok=True)

    # 启动文件监控
    try:
        from monitor import start_monitor
        start_monitor(str(dump_folder), 2)
    except ImportError:
        logger.warning("监控模块未找到，跳过文件监控")

    # 使用线程池并发处理数据库导出导入
    import concurrent.futures

    def process_single_database(db, tables=None):
        """处理单个数据库的导出和导入"""
        sql_file = f'{dump_folder}/{db}.sql'

        try:
            # 导出数据库
            exporter = MyDump(source)
            exporter.export_db(db, sql_file, tables)

            # 导入数据库（使用新的分步导入方法）
            MyRestore(target).restore_db(database=db, dump_folder=str(dump_folder))

            # 根据配置决定是否清理SQL文件和数据库目录
            if delete_after_import:
                # 删除数据库结构文件
                structure_file = dump_folder / f"{db}.sql"
                _safe_remove(str(structure_file), keep_on_error=False)

                # 删除数据库目录
                db_folder = dump_folder / db
                if db_folder.exists():
                    import shutil
                    shutil.rmtree(db_folder)
                    logger.info(f'🗑️ 已删除数据库结构文件和目录: {db}')
            else:
                logger.info(f'💾 保留导出文件和目录: {db}')
            return {'database': db, 'status': 'success', 'error': None}

        except Exception as e:
            logger.error(f'❌ 处理数据库 {db} 失败: {str(e)}')
            # _safe_remove(sql_file)
            return {'database': db, 'status': 'failed', 'error': str(e)}

    # 使用线程池并发处理
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as pool:
        futures = []
        for db in databases:
            future = pool.submit(process_single_database, db, tables)  # 默认tables=None
            futures.append(future)

        # 等待所有任务完成
        for future in concurrent.futures.as_completed(futures):
            result = future.result()
            if result['status'] == 'failed':
                logger.error(f'❌ 数据库 {result["database"]} 处理失败: {result["error"]}')

    # 程序结束前停止监控
    try:
        from monitor import stop_monitor
        stop_monitor()
    except ImportError:
        pass

    # 无限等待，防止Pod重启
    logger.info("💤 程序执行完成，进入休眠状态...")

    try:
        while True:
            time.sleep(3600)  # 每小时检查一次
    except KeyboardInterrupt:
        logger.info("收到退出信号，程序结束")
        sys.exit(0)




def _safe_remove(path, keep_on_error=True):
    """安全删除文件"""
    if not os.path.exists(path):
        return
    try:
        os.remove(path)
    except Exception as e:
        logger.error(f'❌ 删除文件失败: {str(e)}')


if __name__ == "__main__":
    main()
