# mysql-processor
使用 mydumper/myloader 进行 MySQL 数据库备份导出、导入

## 安装 mydumper

### macOS (使用 Homebrew)
```bash
brew install mydumper
```

### Ubuntu/Debian
```bash
sudo apt update
sudo apt install mydumper
```

### CentOS/RHEL
```bash
sudo yum install epel-release
sudo yum install mydumper
```

### Windows
从 [mydumper releases](https://github.com/mydumper/mydumper/releases) 下载 Windows 版本，解压后将可执行文件添加到 PATH。

## 运行

1. 在根目录下创建 config.ini:
```ini
[global]
databases=bboss,billing,cloud_finance,cloud_sale,crm,customer_supply
# mydumper/myloader 线程配置
export_threads=4
import_threads=4

[source]
db_host=106.75.143.56
db_port=3306
db_user=***
db_pass=***

[target]
db_host=10.96.202.178
db_port=3306
db_user=***
db_pass=***
```

2. 目标mysql授权
```sql
GRANT SESSION_VARIABLES_ADMIN ON *.* TO admin@'%';
GRANT SYSTEM_VARIABLES_ADMIN ON *.* TO admin@'%';
```

3. 然后运行:
```bash
python main.py
```

## 注意事项

- mydumper 会创建多个文件，而不是单个 SQL 文件
- 导出目录会在导入完成后自动清理
- 可以根据服务器性能调整 export_threads 和 import_threads 参数
- 建议在进行大量数据同步时，先关闭目标库的 binlog 以提高性能

## 性能调优

- 对于大型数据库，可以增加线程数：export_threads=8, import_threads=8
- 确保 mydumper 和 myloader 版本一致
- 检查源和目标数据库的 max_allowed_packet 设置