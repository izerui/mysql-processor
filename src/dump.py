import os
import shutil

import threading
import time


from base import BaseShell, Mysql
from logger_config import logger


class MyDump(BaseShell):
    """
    使用mysqldump导出数据库备份，支持pv进度显示和文件大小监控
    """

    def __init__(self, mysql: Mysql):
        super().__init__()
        self.mysql = mysql
        self.use_pv = self._check_pv_available()

    def _check_pv_available(self):
        """检查pv工具是否可用"""
        return shutil.which('pv') is not None

    def _monitor_progress(self, dump_dir, interval=2, stop_event=None):
        """
        监控导出目录中所有文件的总大小和导出速度
        :param dump_dir: 导出的目录路径
        :param interval: 监控间隔时间（秒）
        :param stop_event: 用于通知监控线程停止的事件
        """
        last_total_size = 0
        last_check_time = time.time()
        no_change_count = 0
        max_no_change = 3  # 连续3次无变化认为导出完成
        max_wait_cycles = 300  # 最多等待300个周期（约10分钟），防止无限运行

        cycle_count = 0
        while cycle_count < max_wait_cycles:
            # 检查是否需要停止监控
            if stop_event and stop_event.is_set():
                logger.info("🛑 监控线程收到停止信号")
                break

            try:
                if os.path.exists(dump_dir):
                    total_size = 0
                    file_count = 0

                    # 计算目录中所有.sql文件的总大小
                    for file in os.listdir(dump_dir):
                        if file.endswith('.sql'):
                            file_path = os.path.join(dump_dir, file)
                            if os.path.exists(file_path):
                                total_size += os.path.getsize(file_path)
                                file_count += 1

                    total_size_mb = total_size / (1024 * 1024)
                    current_time = time.time()
                    time_elapsed = current_time - last_check_time

                    if total_size != last_total_size:
                        # 计算速度
                        size_diff = total_size - last_total_size
                        speed_mbps = (size_diff / (1024 * 1024)) / time_elapsed if time_elapsed > 0 else 0

                        if speed_mbps > 0:
                            logger.info("📊 导出进度: {} 个文件，总大小: {:.2f} MB，速度: {:.2f} MB/s".format(
                                file_count, total_size_mb, speed_mbps))
                        else:
                            logger.info("📊 导出进度: {} 个文件，总大小: {:.2f} MB".format(file_count, total_size_mb))

                        last_total_size = total_size
                        last_check_time = current_time
                        no_change_count = 0  # 重置计数器
                    else:
                        no_change_count += 1
                        if no_change_count >= max_no_change:
                            # 文件大小连续多次无变化，认为导出完成
                            if total_size > 0:
                                # 计算总耗时和平均速度
                                total_time = time.time() - last_check_time + (no_change_count * interval)
                                avg_speed = total_size_mb / total_time if total_time > 0 else 0
                                logger.info("✅ 导出完成: {} 个文件，总大小: {:.2f} MB，平均速度: {:.2f} MB/s".format(
                                    file_count, total_size_mb, avg_speed))
                            break
                else:
                    # 目录还不存在，等待创建
                    no_change_count += 1
                    if no_change_count >= max_no_change:
                        break
            except Exception as e:
                logger.error("监控进度时出错: {}".format(str(e)))
                break

            cycle_count += 1
            time.sleep(interval)

        if cycle_count >= max_wait_cycles:
            logger.warning("⚠️ 监控线程超时停止，可能导出过程异常")

    def export_dbs(self, databases, dump_file, tables=None):
        """
        使用mysqldump导出数据库到SQL文件
        :param databases: 数据库列表
        :param dump_file: 导出的SQL文件路径
        :param tables: 表名列表，默认为None导出所有表
        :return:
        """
        try:
            # 确保输出目录存在
            os.makedirs(os.path.dirname(dump_file), exist_ok=True)

            mysqldump_path = self._get_mysqldump_exe()

            # 构建mysqldump命令，使用完整路径
            if tables and tables != ['*']:
                # 指定表导出：只支持单个数据库
                if len(databases) > 1:
                    raise ValueError("指定表导出时只能选择一个数据库")
                database = databases[0]
                cmd = '{} -h {} -u {} -p{} --port={} --default-character-set=utf8 --set-gtid-purged=OFF --skip-routines --skip-triggers --skip-add-locks --disable-keys --skip-events --skip-set-charset --compact --add-drop-database --extended-insert --complete-insert --quick --skip-lock-tables --no-autocommit --compress --skip-tz-utc --max-allowed-packet=256M --net-buffer-length=65536 {} {}'.format(
                    mysqldump_path, self.mysql.db_host, self.mysql.db_user, "'{}'".format(self.mysql.db_pass),
                    self.mysql.db_port, database, " ".join(tables))
            else:
                # 完整数据库导出
                cmd = '{} -h {} -u {} -p{} --port={} --default-character-set=utf8 --set-gtid-purged=OFF --skip-routines --skip-triggers --skip-add-locks --disable-keys --skip-events --skip-set-charset --compact --add-drop-database --extended-insert --complete-insert --quick --skip-lock-tables --no-autocommit --compress --skip-tz-utc --max-allowed-packet=256M --net-buffer-length=65536 --databases {}'.format(
                    mysqldump_path, self.mysql.db_host, self.mysql.db_user, "'{}'".format(self.mysql.db_pass),
                    self.mysql.db_port, " ".join(databases))

            # 获取mysqldump的bin目录作为工作目录
            mysqldump_bin_dir = os.path.dirname(mysqldump_path)

            # 使用标准mysqldump命令（暂时移除pv）
            full_command = '{} > {}'.format(cmd, dump_file)
            logger.info("正在导出数据库...")

            # 启动进度监控线程，监控整个导出目录
            dump_dir = os.path.dirname(dump_file)
            stop_event = threading.Event()
            progress_thread = threading.Thread(
                target=self._monitor_progress,
                args=(dump_dir, 2, stop_event),
                daemon=True
            )
            progress_thread.start()

            try:
                # 使用BaseShell的_exe_command方法执行命令
                success, exit_code, output = self._exe_command(
                    full_command,
                    cwd=mysqldump_bin_dir
                )

                if not success:
                    stop_event.set()  # 通知监控线程停止
                    raise RuntimeError("mysqldump导出失败，exit code: {}".format(exit_code))

                # 等待监控线程完成（最多等待5秒）
                progress_thread.join(timeout=5)
                logger.info('✅ 命令执行成功')
                return True

            except Exception as e:
                # 确保在任何异常情况下都停止监控线程
                stop_event.set()
                if progress_thread.is_alive():
                    progress_thread.join(timeout=2)
                raise e

        except RuntimeError as e:
            raise e
        except Exception as e:
            raise RuntimeError("导出过程发生错误: {}".format(str(e)))
