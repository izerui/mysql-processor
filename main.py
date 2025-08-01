# -*- coding: utf-8 -*-
import os
import shutil
import subprocess
from configparser import ConfigParser

from dump import MyDump, MyImport, Mysql

def check_mydumper_tools():
    """检测 mydumper 和 myloader 是否可用"""
    print("正在检查 mydumper 和 myloader 工具...")
    
    # 检查 mydumper
    if subprocess.run(['which', 'mydumper'], capture_output=True).returncode != 0:
        print("✗ mydumper 未找到")
        print("请安装 mydumper:")
        print("  macOS: brew install mydumper")
        print("  Ubuntu/Debian: sudo apt install mydumper")
        print("  CentOS/RHEL: sudo yum install mydumper")
        print("  或使用: ./install_mydumper.sh")
        return False
    
    # 检查 myloader
    if subprocess.run(['which', 'myloader'], capture_output=True).returncode != 0:
        print("✗ myloader 未找到")
        print("请安装 myloader (通常与 mydumper 一起安装)")
        return False
    
    # 获取版本信息
    try:
        mydumper_result = subprocess.run(['mydumper', '--version'], capture_output=True, text=True)
        myloader_result = subprocess.run(['myloader', '--version'], capture_output=True, text=True)
        
        if mydumper_result.returncode == 0:
            print(f"✓ mydumper 可用: {mydumper_result.stdout.strip()}")
        if myloader_result.returncode == 0:
            print(f"✓ myloader 可用: {myloader_result.stdout.strip()}")
    except Exception:
        print("✓ mydumper 和 myloader 已安装")
    
    return True

def check_config():
    """检查配置文件"""
    print("正在检查配置文件...")
    
    if not os.path.exists('config.ini'):
        print("✗ config.ini 文件未找到")
        print("请根据 config.ini.sample 创建 config.ini 文件")
        return False
    
    try:
        config = ConfigParser()
        config.read('config.ini')
        
        # 检查必需配置
        required_sections = ['global', 'source', 'target']
        for section in required_sections:
            if not config.has_section(section):
                print(f"✗ 配置文件缺少 [{section}] 部分")
                return False
        
        # 检查必需参数
        required_global = ['databases']
        required_source = ['db_host', 'db_port', 'db_user', 'db_pass']
        required_target = ['db_host', 'db_port', 'db_user', 'db_pass']
        
        for param in required_global:
            if not config.has_option('global', param):
                print(f"✗ 配置文件缺少 global.{param} 参数")
                return False
        
        for param in required_source:
            if not config.has_option('source', param):
                print(f"✗ 配置文件缺少 source.{param} 参数")
                return False
        
        for param in required_target:
            if not config.has_option('target', param):
                print(f"✗ 配置文件缺少 target.{param} 参数")
                return False
        
        # 检查数据库配置
        databases = config.get('global', 'databases').strip()
        if not databases:
            print("✗ 数据库列表为空")
            return False
        
        print("✓ 配置文件检查通过")
        return True
        
    except Exception as e:
        print(f"✗ 配置文件格式错误: {e}")
        return False

if __name__ == "__main__":
    # 运行前检查
    print("=========================================== 开始运行前检查")
    
    if not check_mydumper_tools():
        print("=========================================== 检查失败，程序终止")
        exit(1)
    
    if not check_config():
        print("=========================================== 检查失败，程序终止")
        exit(1)
    
    print("=========================================== 所有检查通过，开始执行")
    print()
    
    # 加载配置并开始执行
    config = ConfigParser()
    config.read('config.ini')
    source = Mysql(config.get('source', 'db_host'), config.get('source', 'db_port'), config.get('source', 'db_user'),
                   config.get('source', 'db_pass'))
    target = Mysql(config.get('target', 'db_host'), config.get('target', 'db_port'), config.get('target', 'db_user'),
                   config.get('target', 'db_pass'))
    
    # mydumper/myloader 配置参数
    export_threads = config.getint('global', 'export_threads', fallback=4)
    import_threads = config.get('global', 'import_threads', fallback=4)

    databases = config.get('global', 'databases').split(',')
    dump_folder = 'dumps'
    
    # 清理旧的导出目录
    if os.path.exists(dump_folder):
        shutil.rmtree(dump_folder)
    os.makedirs(dump_folder)

    # 导出所有数据库
    print(f'---------------------------------------------> 从{source.db_host}导出数据库: {", ".join(databases)}')
    mydump = MyDump(source)
    mydump.export_dbs(databases, dump_folder, threads=export_threads)
    print(f'---------------------------------------------> 成功从{source.db_host}导出数据库')

    #
    # GRANT SESSION_VARIABLES_ADMIN ON *.* TO admin@'%';
    # GRANT SYSTEM_VARIABLES_ADMIN ON *.* TO admin@'%';
    
    # 导入到目标数据库
    print(f'---------------------------------------------> 导入到{target.db_host}')
    myimport = MyImport(target)
    myimport.import_dump(dump_folder, threads=import_threads)
    print(f'---------------------------------------------> 成功导入到{target.db_host}')

    # 清理导出目录
    print(f'--------------------------------------------->> 删除临时导出目录: {dump_folder}')
    shutil.rmtree(dump_folder)