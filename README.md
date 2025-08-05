# mysql-processor
MySQL数据库备份导出导入工具，支持实时进度显示和Web界面操作

## 功能特性
- ✅ 使用mysqldump进行数据库备份
- ✅ 支持实时进度显示（需要安装pv工具）
- ✅ 跨平台支持（macOS/Linux/Windows）
- ✅ 自动检测pv工具并优雅降级
- ✅ 自动下载MySQL官方版本（8.0.43）
- ✅ **Web界面操作** - 通过浏览器进行数据库导出导入
- ✅ **实时WebSocket通信** - 实时显示进度和日志
- ✅ **批量操作** - 支持多个数据库同时导出
- ✅ **指定表导出** - 支持只导出特定表

## 快速开始

### 方式1：Web界面（推荐）
```bash
# 启动Web服务器
python run_web.py

# 或使用完整命令
python web_server.py

# 指定主机和端口
python web_server.py --host 0.0.0.0 --port 8080
```
启动后访问 `http://localhost:8000`

### 方式2：命令行工具

#### 1. 自动安装MySQL官方版本
```bash
# 自动下载并安装MySQL官方版本（支持Linux/macOS/Windows）
python setup_mysql.py

# 验证安装
python -c "from src.mysql_downloader import MySQLDownloader; print(MySQLDownloader().get_mysqldump_path())"
```

#### 2. 安装pv工具（可选但推荐）
pv工具可以提供实时进度显示，让导出过程更直观。

##### 自动安装
```bash
# 一键安装pv工具
./install-pv.sh
```

##### 手动安装
```bash
# macOS
brew install pv

# Ubuntu/Debian
sudo apt-get install pv

# CentOS/RHEL
sudo yum install pv

# Fedora
sudo dnf install pv
```

#### 3. 使用UV运行项目

##### 安装UV
```bash
# macOS/Linux
curl -LsSf https://astral.sh/uv/install.sh | sh

# Windows
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"

# Linux (Ubuntu/Debian)
sudo apt update && sudo apt install -y curl
curl -LsSf https://astral.sh/uv/install.sh | sh
```

##### 运行项目
```bash
# 克隆项目
git clone <your-repo-url>
cd mysql-processor

# 创建虚拟环境并安装依赖
uv venv
source .venv/bin/activate  # Linux/macOS
# 或 .venv\Scripts\activate  # Windows

# 安装项目
uv pip install -e .

# 配置
cp config.ini.sample config.ini
# 编辑config.ini文件，填入你的数据库配置

# 运行
uv run mysql-processor
```

## 使用说明

### Web界面使用指南

#### 启动Web服务器
```bash
# 安装Python依赖
pip install flask flask-socketio python-socketio

# 启动服务器
python run_web.py
```

#### 导出数据库
1. 打开浏览器访问 `http://localhost:8000`
2. 填写数据库连接信息：
   - 主机：localhost
   - 端口：3306
   - 用户名：root
   - 密码：your_password
3. 填写数据库名：`mydb`（多个用逗号分隔：`db1,db2`）
4. 选择输出文件：`/path/to/backup.sql`
5. （可选）指定表：`users,orders`（只导出指定表）
6. 点击"开始导出"

#### 导入数据库
1. 在导入表单中填写：
   - 数据库连接信息（同上）
   - SQL文件路径：`/path/to/backup.sql`
   - （可选）目标数据库：`mydb`（留空则使用SQL文件中的数据库名）
2. 点击"开始导入"

#### Web界面特性
- **实时进度显示**：进度条、文件大小、实时日志
- **状态指示器**：绿色（运行中）、灰色（完成）、红色（错误）
- **批量操作**：支持多个数据库同时导出
- **指定表导出**：支持只导出特定表
- **实时通信**：WebSocket实时推送进度和日志

### 命令行使用

#### 自动下载MySQL官方版本
项目会自动根据当前平台下载对应的MySQL官方版本：

- **Linux**: mysql-8.0.43-linux-glibc2.28-x86_64.tar.xz
- **macOS**: mysql-8.0.43-macos15-arm64.tar.gz
- **Windows**: mysql-8.0.43-winx64.zip

下载后的MySQL工具会保存在项目根目录的 `mysql/` 文件夹中。

#### 进度显示
当安装了pv工具时，导出过程会显示实时进度条：
```
🚀 开始导出数据库: mydb
📁 导出文件: dumps/mydb.sql
📊 使用pv显示实时进度...
```

如果未安装pv工具，会显示：
```
⏳ 正在导出，请稍候...
```

#### 传统方式运行（不使用UV）

##### 1. 在根目录下创建 config.ini:
类似:
```ini
[global]
databases=bboss,billing,cloud_finance,cloud_sale,crm,customer_supply
# 请先确认目标库参数值范围,然后进行相应的调优:
# mysql>show variables like 'max_allowed_packet';
# mysql>show variables like 'net_buffer_length';
import_max_allowed_packet=134217728
import_net_buffer_length=16384

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

##### 2. 目标mysql授权
```
GRANT SESSION_VARIABLES_ADMIN ON *.* TO admin@'%';
GRANT SYSTEM_VARIABLES_ADMIN ON *.* TO admin@'%';
```

##### 3. 然后运行:
```python
# 先安装依赖
pip install requests tqdm

# 安装MySQL官方版本
python setup_mysql.py

# 运行主程序
python main.py
```

建议:
> 在进行同步之前，最好把目标库的binlog先关闭, windows 下请修改区域与语言设置，选中统一使用unicode编码

## 开发命令（使用UV）

```bash
# 安装开发依赖
uv pip install -e ".[dev]"

# 格式化代码
uv run black src/
uv run isort src/

# 代码检查
uv run flake8 src/

# 运行测试
uv run pytest

# 构建wheel包
uv build
```

## API接口（Web模式）

### 导出接口
- **POST /api/export**
- **Content-Type**: application/json
- **参数**:
  ```json
  {
    "host": "localhost",
    "port": 3306,
    "user": "root",
    "password": "password",
    "databases": ["mydb"],
    "tables": ["users", "orders"],
    "output_file": "/path/to/backup.sql"
  }
  ```

### 导入接口
- **POST /api/import**
- **Content-Type**: application/json
- **参数**:
  ```json
  {
    "host": "localhost",
    "port": 3306,
    "user": "root",
    "password": "password",
    "input_file": "/path/to/backup.sql",
    "target_database": "mydb"
  }
  ```

### WebSocket事件
- **task_progress**: 任务进度更新
- **connected**: WebSocket连接成功
- **disconnect**: WebSocket断开连接

## 故障排除

### 常见问题

#### Web界面问题
1. **端口被占用**
   ```bash
   # 查看端口使用情况
   lsof -i :8000
   # 使用其他端口启动
   python run_web.py --port 8080
   ```

2. **WebSocket连接失败**
   - 检查防火墙设置
   - 确保浏览器支持WebSocket
   - 尝试刷新页面

#### 通用问题
1. **权限问题**
   - 确保MySQL用户有足够权限
   - 确保文件路径有读写权限

2. **pv未安装**
   - 运行 `./install-pv.sh` 安装
   - 或手动安装 pv 工具

3. **MySQL连接问题**
   - 检查MySQL服务是否运行
   - 确认用户名密码正确
   - 检查防火墙设置

### 日志查看
- **Web界面**：所有操作日志都会实时显示在网页上
- **命令行**：查看控制台输出
- **文件日志**：检查dumps目录下的日志文件

## 项目结构
```
mysql-processor/
├── src/                    # 主要代码
│   ├── mysql_downloader.py # MySQL自动下载器
│   ├── base.py            # 基础工具类
│   ├── dump.py            # mysqldump导出类
│   ├── import_.py         # 数据导入类
│   ├── web_server.py      # Web服务器主文件
│   └── templates/         # Web页面模板
├── tests/                  # 测试文件
├── mysql-client/           # MySQL客户端工具
├── dumps/                  # 导出文件目录
├── mysql/                  # 自动下载的MySQL官方版本
├── install-pv.sh          # pv工具安装脚本
├── export.sh              # 导出脚本（支持pv）
├── setup_mysql.py         # MySQL安装脚本
├── main.py                # 入口脚本
├── run_web.py            # Web服务器快捷启动脚本
├── web_server.py         # Web服务器启动脚本
├── config.ini.sample      # 配置示例
├── pyproject.toml         # UV项目配置
└── README.md              # 项目文档
```

## 注意事项
- 自动下载功能需要网络连接
- 下载文件较大（约200-400MB），请确保有足够的磁盘空间
- Windows用户可能需要管理员权限运行
- 如果下载失败，可以手动下载对应平台的MySQL版本并解压到 `mysql/` 目录
- Web界面需要浏览器支持WebSocket（现代浏览器都支持）