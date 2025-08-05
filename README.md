# MySQL Processor
MySQL数据库备份导出导入工具，支持高性能mydumper/myloader和传统mysqldump，实时进度显示

## 🚀 功能特性
- ✅ **高性能备份** - 使用mydumper/myloader，比mysqldump快3-5倍
- ✅ **并行处理** - 8线程并行导出/导入
- ✅ **零锁表** - `--sync-thread-lock-mode=NO_LOCK` 避免业务影响
- ✅ **智能分块** - 256MB分块，500万行/文件优化
- ✅ **实时压缩** - 节省50-70%存储空间
- ✅ **跨平台支持** - macOS/Linux/Windows
- ✅ **容器化部署** - Docker支持
- ✅ **UV包管理** - 现代化Python项目管理
- ✅ **批量操作** - 支持多个数据库同时处理

## 📋 快速开始

### 方法1：一键安装（推荐）
```bash
# 克隆项目
git clone <your-repo-url>
cd mysql-processor

# 一键安装和运行
./build.sh
```

### 方法2：使用UV（现代化）
```bash
# 安装UV
curl -LsSf https://astral.sh/uv/install.sh | sh

# 克隆并运行
git clone <your-repo-url>
cd mysql-processor
uv venv && source .venv/bin/activate
uv pip install -e .
./build.sh
```

### 方法3：传统方式
```bash
pip install -e .
./build.sh
```

### 方法4：Docker容器化
```bash
# Docker方式
docker build -t mysql-processor .
docker run -it \
  -v $(pwd)/config.ini:/app/config.ini \
  -v $(pwd)/dumps:/app/dumps \
  mysql-processor:latest
```

## 🐳 Docker 容器化部署

### 一键容器化
```bash
# 构建并运行
./build.sh

# 或者手动
docker build -t mysql-processor .
docker run -d \
  --name mysql-processor \
  -v $(pwd)/config.ini:/app/config.ini:ro \
  -v $(pwd)/dumps:/app/dumps \
  mysql-processor:latest
```

## ⚙️ 配置说明

### 1. 创建配置文件
```bash
cp config.ini.sample config.ini
```

### 2. 编辑配置
```ini
[global]
databases = your_database
import_max_allowed_packet = 268435456
import_net_buffer_length = 65536

[source]
db_host = source_host
db_port = 3306
db_user = source_user
db_pass = source_password

[target]
db_host = target_host
db_port = 3306
db_user = target_user
db_pass = target_password
```

### 3. 系统依赖安装（自动）
```bash
# macOS
brew install mydumper

# Rocky Linux 9
sudo dnf install https://github.com/mydumper/mydumper/releases/download/v0.19.4-7/mydumper-0.19.4-7.el9.x86_64.rpm

# Ubuntu/Debian
sudo apt install mydumper
```

## 🎯 使用示例

### 基础使用
```bash
# 运行完整备份
python src/main.py

# 指定数据库
echo "databases = db1,db2,db3" >> config.ini
python src/main.py
```

### Docker 容器内使用
```bash
# 进入容器
docker exec -it mysql-processor bash

# 运行备份
python src/main.py

# 查看结果
ls -la dumps/
```

## 📊 性能对比

| 工具 | 并行度 | 速度提升 | 锁表影响 | 压缩率 |
|------|--------|----------|----------|--------|
| mysqldump | 1x | 基准 | 有锁表 | 无 |
| mydumper | 8x | **3-5倍** | **零锁表** | **50-70%** |

### 优化参数
- **并行线程**: 8线程
- **分块大小**: 256MB
- **每文件行数**: 50万行
- **压缩**: 启用
- **无锁**: 避免业务影响

## 🛠️ 开发命令

### 使用UV开发
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
```

### 容器开发
```bash
# 构建开发镜像
docker build -t mysql-processor:dev .

# 开发模式运行
docker run -it \
  -v $(pwd)/src:/app/src \
  -v $(pwd)/config.ini:/app/config.ini \
  mysql-processor:dev bash
```

## 🔧 故障排除

### 常见问题

#### 1. mydumper 未安装
```bash
# 自动安装
./build.sh

# 手动安装
# macOS: brew install mydumper
# Rocky9: sudo dnf install mydumper-*.rpm
```

#### 2. Docker 网络问题
```bash
# 测试连接
docker run --rm mysql-processor python -c "
from src.base import Mysql
mysql = Mysql('host', 3306, 'user', 'pass')
print('连接成功')
"
```

#### 3. 权限问题
```bash
chmod +x build.sh
chmod 600 config.ini
```

## 📁 项目结构
```
mysql-processor/
├── src/                    # 核心代码
│   ├── main.py            # 主程序入口
│   ├── mydumper.py       # mydumper导出类
│   ├── myloader.py       # myloader导入类
│   ├── mydumper_downloader.py # mydumper安装器
│   └── base.py           # 基础工具类
├── dumps/                 # 备份文件目录
├── config.ini.sample      # 配置示例
├── Dockerfile            # 容器镜像配置
├── build.sh              # 一键构建脚本
├── pyproject.toml        # UV项目配置
├── README.md             # 项目文档
└── CONTAINER.md          # 容器化指南
```

## 🌐 支持平台
- **macOS**: Intel/Apple Silicon (brew install mydumper)
- **Linux**: Ubuntu/Debian/Rocky/CentOS
- **Windows**: WSL2 + Docker
- **容器**: Docker

## 📞 支持
- **GitHub Issues**: 报告bug和功能请求
- **文档**: 查看README.md中的容器化部分
- **示例**: 查看config.ini.sample

## 🚀 下一步
1. 配置 `config.ini`
2. 运行 `./build.sh`
3. 开始高性能备份！