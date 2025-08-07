#!/usr/bin/env python3
"""
MySQL 官方版本自动下载器
支持 Linux/macOS/Windows 平台
自动下载并解压 MySQL 8.0.43 到项目根目录
"""

import os
import platform
import requests
import tarfile
import zipfile
from pathlib import Path
from typing import Optional, Dict
import shutil
import sys
from tqdm import tqdm

from logger_config import logger


class MySQLDownloader:
    """MySQL 官方版本自动下载器"""

    # MySQL 8.0.43 官方下载地址
    DOWNLOAD_URLS = {
        'linux': 'https://serv999.com/proxy/mysql-8.0.43-linux-glibc2.28-x86_64.tar.xz',
        'darwin': 'https://cdn.mysql.com/Downloads/MySQL-8.0/mysql-8.0.43-macos15-arm64.tar.gz',
        'windows': 'https://cdn.mysql.com/Downloads/MySQL-8.0/mysql-8.0.43-winx64.zip'
    }

    # 平台映射
    PLATFORM_MAP = {
        'linux': 'linux',
        'linux2': 'linux',
        'darwin': 'darwin',
        'win32': 'windows',
        'cygwin': 'windows'
    }

    def __init__(self, project_root: Optional[str] = None):
        """
        初始化下载器

        Args:
            project_root: 项目根目录路径，如果为None则自动检测
        """
        self.project_root = Path(project_root) if project_root else Path(__file__).parent.parent
        self.mysql_dir = self.project_root / "mysql"
        self.temp_dir = self.project_root / "temp"

    def get_platform(self) -> str:
        """获取当前平台标识"""
        system = platform.system().lower()
        return self.PLATFORM_MAP.get(system, system)

    def get_download_url(self) -> str:
        """获取当前平台的下载URL"""
        current_platform = self.get_platform()
        if current_platform not in self.DOWNLOAD_URLS:
            raise ValueError(f"不支持的平台: {current_platform}")
        return self.DOWNLOAD_URLS[current_platform]

    def get_filename(self, url: str) -> str:
        """从URL中提取文件名"""
        return url.split('/')[-1]

    def download_file(self, url: str, destination: Path) -> bool:
        """
        下载文件并显示进度

        Args:
            url: 下载地址
            destination: 本地保存路径

        Returns:
            bool: 下载是否成功
        """
        try:
            logger.info(f"正在下载: {url}")

            # 创建临时目录
            self.temp_dir.mkdir(exist_ok=True)

            # 发送请求
            response = requests.get(url, stream=True, timeout=300)
            response.raise_for_status()

            # 获取文件大小
            total_size = int(response.headers.get('content-length', 0))

            # 下载文件
            with open(destination, 'wb') as file:
                if total_size > 0:
                    with tqdm(total=total_size, unit='B', unit_scale=True, desc="下载进度") as pbar:
                        for chunk in response.iter_content(chunk_size=8192):
                            if chunk:
                                file.write(chunk)
                                pbar.update(len(chunk))
                else:
                    for chunk in response.iter_content(chunk_size=8192):
                        if chunk:
                            file.write(chunk)

            logger.info(f"下载完成: {destination}")
            return True

        except Exception as e:
            logger.error(f"下载失败: {e}")
            if destination.exists():
                destination.unlink()
            return False

    def extract_archive(self, archive_path: Path, extract_to: Path) -> bool:
        """
        解压归档文件

        Args:
            archive_path: 归档文件路径
            extract_to: 解压目标目录

        Returns:
            bool: 解压是否成功
        """
        try:
            logger.info(f"正在解压: {archive_path}")

            # 确保目标目录存在
            extract_to.mkdir(exist_ok=True)

            if archive_path.suffix == '.zip':
                # Windows ZIP 文件
                with zipfile.ZipFile(archive_path, 'r') as zip_ref:
                    zip_ref.extractall(extract_to)

            elif archive_path.suffix == '.gz' and archive_path.name.endswith('.tar.gz'):
                # macOS tar.gz 文件
                with tarfile.open(archive_path, 'r:gz') as tar_ref:
                    tar_ref.extractall(extract_to)

            elif archive_path.suffix == '.xz' and archive_path.name.endswith('.tar.xz'):
                # Linux tar.xz 文件
                with tarfile.open(archive_path, 'r:xz') as tar_ref:
                    tar_ref.extractall(extract_to)

            else:
                raise ValueError(f"不支持的文件格式: {archive_path.suffix}")

            logger.info(f"解压完成: {extract_to}")
            return True

        except Exception as e:
            logger.error(f"解压失败: {e}")
            return False

    def find_mysql_bin_dir(self, extract_path: Path) -> Optional[Path]:
        """
        在解压后的目录中查找 MySQL bin 目录

        Args:
            extract_path: 解压后的目录

        Returns:
            Path: MySQL bin 目录路径，如果未找到返回None
        """
        # 查找包含 mysqldump 的目录
        for root, dirs, files in os.walk(extract_path):
            if 'mysqldump' in files or 'mysqldump.exe' in files:
                return Path(root)

        # 查找标准的 bin 目录
        bin_dirs = list(extract_path.rglob('bin'))
        for bin_dir in bin_dirs:
            if bin_dir.is_dir() and any(f.name.startswith('mysqldump') for f in bin_dir.iterdir()):
                return bin_dir

        return None

    def setup_mysql_tools(self) -> bool:
        """
        设置 MySQL 工具环境

        Returns:
            bool: 设置是否成功
        """
        try:
            # 获取下载信息
            url = self.get_download_url()
            filename = self.get_filename(url)
            archive_path = self.temp_dir / filename

            # 下载文件
            if not self.download_file(url, archive_path):
                return False

            # 解压文件
            if not self.extract_archive(archive_path, self.temp_dir):
                return False

            # 查找 MySQL 目录
            extracted_dirs = [d for d in self.temp_dir.iterdir() if d.is_dir() and 'mysql' in d.name.lower()]
            if not extracted_dirs:
                logger.error("未找到 MySQL 目录")
                return False

            mysql_extract_dir = extracted_dirs[0]
            mysql_bin_dir = self.find_mysql_bin_dir(mysql_extract_dir)

            if not mysql_bin_dir:
                logger.error("未找到 MySQL bin 目录")
                return False

            # 清理旧的 MySQL 目录内容（不删除目录本身）
            if self.mysql_dir.exists():
                for item in self.mysql_dir.iterdir():
                    if item.is_file():
                        item.unlink()
                    elif item.is_dir():
                        shutil.rmtree(item)
            else:
                self.mysql_dir.mkdir(exist_ok=True)

            # 将解压目录中的内容移动到 mysql 目录
            for item in mysql_extract_dir.iterdir():
                shutil.move(str(item), str(self.mysql_dir))

            # 清理临时文件
            archive_path.unlink(missing_ok=True)

            # 验证 mysqldump 是否可用
            mysqldump_path = None
            if self.get_platform() == 'windows':
                mysqldump_path = self.mysql_dir / 'bin' / 'mysqldump.exe'
            else:
                mysqldump_path = self.mysql_dir / 'bin' / 'mysqldump'

            if mysqldump_path and mysqldump_path.exists():
                logger.info(f"MySQL 工具已安装到: {self.mysql_dir}")
                logger.info(f"mysqldump 路径: {mysqldump_path}")
                return True
            else:
                logger.error("mysqldump 文件不存在")
                return False

        except Exception as e:
            logger.error(f"设置失败: {e}")
            return False

    def get_mysqldump_path(self) -> Optional[Path]:
        """
        获取 mysqldump 的完整路径

        Returns:
            Path: mysqldump 路径，如果未找到返回None
        """
        if self.get_platform() == 'windows':
            path = self.mysql_dir / 'bin' / 'mysqldump.exe'
        else:
            path = self.mysql_dir / 'bin' / 'mysqldump'

        return path if path.exists() else None

    def get_mysql_bin_dir(self) -> Optional[Path]:
        """
        获取 MySQL bin 目录路径

        Returns:
            Path: bin 目录路径，如果未找到返回None
        """
        bin_dir = self.mysql_dir / 'bin'
        return bin_dir if bin_dir.exists() and bin_dir.is_dir() else None

    def get_mysql_exe_path(self) -> Optional[Path]:
        """
        获取 mysql 可执行文件的完整路径

        Returns:
            Path: mysql 路径，如果未找到返回None
        """
        if self.get_platform() == 'windows':
            path = self.mysql_dir / 'bin' / 'mysql.exe'
        else:
            path = self.mysql_dir / 'bin' / 'mysql'

        return path if path.exists() else None

    def is_mysql_installed(self) -> bool:
        """检查 MySQL 是否已经安装"""
        return self.get_mysqldump_path() is not None


def main():
    """主函数 - 用于测试"""
    downloader = MySQLDownloader()

    if downloader.is_mysql_installed():
        print("MySQL 已经安装")
        print(f"mysqldump 路径: {downloader.get_mysqldump_path()}")
    else:
        print("正在安装 MySQL...")
        if downloader.setup_mysql_tools():
            print("安装成功！")
        else:
            print("安装失败！")
            sys.exit(1)


if __name__ == "__main__":
    main()
