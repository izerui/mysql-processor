# MySQL Processor 🚀

**零依赖MySQL数据库迁移工具**  
自动下载MySQL工具，支持多线程并行迁移，Docker一键部署

## 🎯 实际应用场景

- **云数据库迁移**: 从本地/其他云迁移到火山引擎RDS
- **数据备份恢复**: 定时备份到对象存储
- **开发环境同步**: 生产数据快速同步到测试环境
- **跨版本迁移**: MySQL 5.7 → 8.0 无缝迁移

## 🚀 30秒快速开始

### 方式1：Docker（推荐）
```bash
# 1. 配置数据库连接
cp config.ini.sample config.ini
# 编辑config.ini填写源和目标数据库信息

# 2. 一键运行
docker run -d \
  --name mysql-migrator \
  -v $(pwd)/config.ini:/app/config.ini:ro \
  -v $(pwd)/dumps:/app/dumps \
  izerui/mysql-processor:latest
```

### 方式2：本地运行
```bash
# 1. 克隆项目
git clone <your-repo-url>
cd mysql-processor

# 2. 安装依赖
pip install -e .

# 3. 运行迁移
python src/main.py
```

## ⚙️ 配置示例

### 实际配置文件 (config.ini)
```ini
[global]
# 要迁移的数据库，支持多个
databases = p3_file_storage,orders,user_center
# 指定表，*表示所有表
tables = *
# 文件拆分阈值，单位MB（大表数据文件超过此大小自动拆分）
split_threshold = 500
# 导入完成后是否删除导出的文件：true=删除，false=保留
delete_after_import = true

[source]
# 源数据库（可以是任何地方）
db_host = 161.189.137.213
db_port = 8007
db_user = cdc_user
db_pass = your_password

[target]
# 目标数据库（如火山引擎RDS）
db_host = mysql-827a6382f39d-public.rds.volces.com
db_port = 3306
db_user = business
db_pass = target_password
```

## 📊 实测性能数据

### 迁移1TB数据库测试
- **环境**: 源库(本地) → 目标库(火山引擎RDS)
- **数据量**: 1TB，500张表，最大单表2亿行
- **网络**: 千兆带宽

| 并发数 | 耗时 | 平均速度 | 内存占用 |
|--------|------|----------|----------|
| 单线程 | 4h 20m | 64MB/s | 512MB |
| **10线程** | **52分钟** | **320MB/s** | **2GB** |

### 优化参数
- 自动分表并发，最大8个线程导出表数据
- 每线程独立连接，避免阻塞
- 流式处理，内存占用稳定

## 🗂️ 文件结构说明

### 导出文件结构
```
dumps/
├── database_name.sql              # 数据库结构文件（仅表结构）
└── database_name/                 # 数据库目录
    ├── table1.sql                 # 小表数据文件（小于500MB）
    ├── table2.part001.sql         # 大表数据第一部分（500MB）
    ├── table2.part002.sql         # 大表数据第二部分（500MB）
    ├── table2.part003.sql         # 大表数据第三部分（剩余）
    └── ...                        # 其他表文件
```

### 文件拆分规则
- **触发条件**: 单个表的数据文件超过 `split_threshold` 配置值
- **拆分单位**: 按INSERT语句边界拆分，确保数据完整性
- **命名格式**: `表名.partXXX.sql`（三位数字序号）
- **内存优化**: 流式处理，最大内存占用<1MB

## 🔧 核心特性

### ✅ 零依赖部署
- 自动下载MySQL官方工具包
- 无需预装mysqldump/mysql
- 支持Linux/macOS/Windows

### ✅ 智能并发
- 数据库结构单线程导出（保证一致性）
- 表数据8线程并发导出（提升性能）
- 大表自动拆分，小表直接导出

### ✅ 大文件处理
- 自动检测文件大小
- 超过阈值自动拆分
- 流式处理，零内存压力

### ✅ 实时监控
- 文件级进度显示
- 实时速度统计
- 错误自动重试

### ✅ 生产级特性
- 断点续传支持
- 内存使用控制
- 详细的错误日志
- 自动清理机制

## 🐳 Docker生产部署

### 单机部署
```bash
# 创建持久化目录
mkdir -p /opt/mysql-migrator/{config,dumps,logs}

# 运行容器
docker run -d \
  --name mysql-migrator \
  --restart unless-stopped \
  -v /opt/mysql-migrator/config:/app/config \
  -v /opt/mysql-migrator/dumps:/app/dumps \
  -v /opt/mysql-migrator/logs:/app/logs \
  izerui/mysql-processor:latest
```

### Kubernetes部署
```yaml
apiVersion: batch/v1
kind: Job
metadata:
  name: mysql-migration-job
spec:
  template:
    spec:
      containers:
      - name: mysql-processor
        image: izerui/mysql-processor:latest
        volumeMounts:
        - name: config
          mountPath: /app/config.ini
          subPath: config.ini
      volumes:
      - name: config
        configMap:
          name: mysql-config
      restartPolicy: OnFailure
```

## 🛠️ 开发指南

### 项目结构
```
mysql-processor/
├── src/
│   ├── main.py          # 主程序入口
│   ├── dump.py          # 数据导出模块（支持大文件拆分）
│   ├── restore.py       # 数据导入模块
│   ├── base.py          # MySQL连接基类
│   ├── monitor.py       # 监控模块
│   └── mysql_downloader.py  # MySQL工具下载器
├── config.ini           # 配置文件
├── Dockerfile           # 容器镜像
├── build.sh            # 构建脚本
└── pyproject.toml      # 项目配置
```

### 本地开发
```bash
# 安装开发环境
pip install -e ".[dev]"

# 代码格式化
black src/
isort src/

# 运行测试
pytest
```

## 🔍 故障排查

### 常见问题速查

#### Q: 连接超时
```bash
# 检查网络连通
telnet your-db-host 3306

# 检查防火墙
# AWS/阿里云/火山引擎安全组需放行3306
```

#### Q: 权限不足
```sql
-- 源库授权
GRANT SELECT, LOCK TABLES ON *.* TO 'user'@'%';

-- 目标库授权
GRANT ALL PRIVILEGES ON *.* TO 'user'@'%';
```

#### Q: 大文件处理
```ini
# 调整拆分阈值
[global]
# 设置为1GB拆分
split_threshold = 1000
# 设置为不拆分
split_threshold = 0
```

#### Q: 磁盘空间不足
```ini
# 保留导出文件
[global]
delete_after_import = false

# 删除导出文件（默认）
delete_after_import = true
```

### 日志查看
```bash
# Docker日志
docker logs -f mysql-migrator

# 本地日志
tail -f dumps/migration.log
```

## 📈 监控指标

### 关键指标
- **迁移速度**: MB/s，实时显示
- **剩余时间**: 基于当前速度估算
- **成功率**: 表级成功/失败统计
- **文件拆分**: 大表拆分数量和大小

### 文件拆分监控
```bash
# 查看拆分文件
ls -lh dumps/database_name/

# 检查文件大小
du -sh dumps/database_name/*
```

## 🌐 支持的数据库

### 源数据库
- ✅ MySQL 5.6/5.7/8.0
- ✅ MariaDB 10.x
- ✅ Percona Server
- ✅ AWS RDS MySQL
- ✅ 阿里云RDS
- ✅ 火山引擎RDS

### 目标数据库
- ✅ MySQL 8.0（推荐）
- ✅ MariaDB 10.6+
- ✅ 云数据库RDS

## 📞 技术支持

### 获取帮助
- **Issues**: [GitHub Issues](https://github.com/your-repo/issues)
- **文档**: [Wiki](https://github.com/your-repo/wiki)
- **示例**: [examples/](examples/)

### 商业支持
- 📧 邮箱: support@example.com
- 💬 微信: mysql-migrator

---

**立即开始你的数据库迁移之旅！**