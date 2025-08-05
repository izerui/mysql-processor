#!/usr/bin/env python3
"""
MyDumper 自动安装器
支持 macOS (brew) 和 Rocky Linux 9 (RPM) 平台
"""

import os
import platform
import subprocess
import shutil
from pathlib import Path
from typing import Optional


class MyDumperDownloader:
    """MyDumper 自动安装器"""

    def __init__(self, project_root: Optional[str] = None):
        """
        初始化安装器
        Args:
            project_root: 项目根目录路径，如果为None则自动检测
        """
        self.project_root = Path(project_root) if project_root else Path(__file__).parent.parent
        self.mydumper_dir = self.project_root / "mydumper"

    def get_platform(self) -> str:
        """获取当前平台标识"""
        system = platform.system().lower()
        if system == 'darwin':
            return 'darwin'
        elif system == 'linux':
            # 检查是否为 Rocky Linux 9
            try:
                with open('/etc/os-release', 'r') as f:
                    content = f.read()
                    if 'rocky' in content.lower() and '9' in content:
                        return 'rocky9'
                    elif 'rhel' in content.lower() and '9' in content:
                        return 'rocky9'
            except:
                pass
            return 'linux'
        return system

    def is_mydumper_installed(self) -> bool:
        """检查 mydumper 是否已安装"""
        # 检查系统路径
        mydumper_path = shutil.which('mydumper')
        myloader_path = shutil.which('myloader')

        if mydumper_path and myloader_path:
            # 创建符号链接到项目目录
            if not self.mydumper_dir.exists():
                self.mydumper_dir.mkdir()

            mydumper_link = self.mydumper_dir / 'mydumper'
            myloader_link = self.mydumper_dir / 'myloader'

            if not mydumper_link.exists():
                os.symlink(mydumper_path, mydumper_link)
            if not myloader_link.exists():
                os.symlink(myloader_path, myloader_link)

            return True

        # 检查项目目录
        mydumper_path = self.mydumper_dir / 'mydumper'
        myloader_path = self.mydumper_dir / 'myloader'

        return mydumper_path.exists() and myloader_path.exists()

    def install_via_brew(self) -> bool:
        """通过 brew 安装 mydumper"""
        try:
            print("正在通过 brew 安装 mydumper...")
            result = subprocess.run(['brew', 'install', 'mydumper'],
                                  capture_output=True, text=True)
            if result.returncode == 0:
                print("✅ brew 安装成功")
                return True
            else:
                print(f"❌ brew 安装失败: {result.stderr}")
                return False
        except FileNotFoundError:
            print("❌ 未找到 brew 命令，请先安装 Homebrew")
            return False

    def install_via_rpm(self) -> bool:
        """通过 RPM 安装 mydumper"""
        try:
            rpm_url = "https://github.com/mydumper/mydumper/releases/download/v0.19.4-7/mydumper-0.19.4-7.el9.x86_64.rpm"
            rpm_path = self.project_root / "temp" / "mydumper.rpm"

            # 创建临时目录
            rpm_path.parent.mkdir(exist_ok=True)

            # 下载 RPM
            print("正在下载 mydumper RPM...")
            import requests
            response = requests.get(rpm_url, stream=True)
            response.raise_for_status()

            with open(rpm_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)

            # 安装 RPM
            print("正在安装 RPM...")
            result = subprocess.run(['sudo', 'rpm', '-i', str(rpm_path)],
                                  capture_output=True, text=True)
            if result.returncode == 0:
                print("✅ RPM 安装成功")
                rpm_path.unlink()  # 清理下载的文件
                return True
            else:
                print(f"❌ RPM 安装失败: {result.stderr}")
                return False

        except Exception as e:
            print(f"❌ RPM 安装失败: {str(e)}")
            return False

    def setup_mydumper_tools(self) -> bool:
        """设置 MyDumper 工具环境"""
        platform_name = self.get_platform()

        if platform_name == 'darwin':
            return self.install_via_brew()
        elif platform_name == 'rocky9':
            return self.install_via_rpm()
        else:
            print(f"❌ 不支持的平台: {platform_name}")
            print("支持的系统：macOS (brew) 和 Rocky Linux 9 (RPM)")
            return False

    def get_mydumper_path(self) -> Optional[str]:
        """获取 mydumper 的完整路径"""
        # 优先使用系统安装的版本
        system_path = shutil.which('mydumper')
        if system_path:
            return system_path

        # 回退到项目目录
        if self.is_mydumper_installed():
            return str(self.mydumper_dir / 'mydumper')
        return None

    def get_myloader_path(self) -> Optional[str]:
        """获取 myloader 的完整路径"""
        # 优先使用系统安装的版本
        system_path = shutil.which('myloader')
        if system_path:
            return system_path

        # 回退到项目目录
        if self.is_mydumper_installed():
            return str(self.mydumper_dir / 'myloader')
        return None

    def get_mydumper_dir(self) -> Optional[Path]:
        """获取 MyDumper 目录路径"""
        return self.mydumper_dir if self.mydumper_dir.exists() else None


def main():
    """主函数 - 用于测试"""
    downloader = MyDumperDownloader()

    if downloader.is_mydumper_installed():
        print("✅ MyDumper 已经安装")
        print(f"mydumper: {downloader.get_mydumper_path()}")
        print(f"myloader: {downloader.get_myloader_path()}")
    else:
        print("正在安装 MyDumper...")
        if downloader.setup_mydumper_tools():
            print("✅ 安装成功！")
        else:
            print("❌ 安装失败！")
            exit(1)


if __name__ == "__main__":
    main()
