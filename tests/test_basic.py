"""基础测试文件"""

import os
import tempfile
from pathlib import Path

import sys
from pathlib import Path

# 将src目录添加到Python路径
src_path = Path(__file__).parent / "src"
sys.path.insert(0, str(src_path))

from base import Mysql


def test_mysql_class():
    """测试Mysql类的初始化"""
    mysql = Mysql("localhost", 3306, "user", "password")
    assert mysql.db_host == "localhost"
    assert mysql.db_port == 3306
    assert mysql.db_user == "user"
    assert mysql.db_pass == "password"


def test_config_file_exists():
    """测试配置文件是否存在"""
    config_sample = Path("config.ini.sample")
    assert config_sample.exists()


def test_mysql_client_directory():
    """测试mysql-client目录是否存在"""
    client_dir = Path("mysql-client")
    assert client_dir.exists()
    assert client_dir.is_dir()


def test_dumps_directory():
    """测试dumps目录是否存在或可创建"""
    dumps_dir = Path("dumps")
    if not dumps_dir.exists():
        dumps_dir.mkdir(exist_ok=True)
    assert dumps_dir.exists()
    assert dumps_dir.is_dir()


def test_temp_file_creation():
    """测试临时文件创建功能"""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.sql', delete=False) as tmp:
        tmp.write("SELECT 1;")
        tmp_path = tmp.name

    try:
        assert os.path.exists(tmp_path)
        with open(tmp_path, 'r') as f:
            content = f.read()
            assert content == "SELECT 1;"
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
