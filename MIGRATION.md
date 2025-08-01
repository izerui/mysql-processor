# 从 mysqldump 迁移到 mydumper 指南

## 主要变化

### 1. 导出格式变化
- **旧版本**: 生成单个 .sql 文件
- **新版本**: 生成包含多个文件的目录结构

### 2. 配置参数变化
- **移除参数**:
  - `export_use_pump` (不再使用 mysqlpump)
  - `import_max_allowed_packet` (myloader 自动处理)
  - `import_net_buffer_length` (myloader 自动处理)

- **新增参数**:
  - `export_threads`: mydumper 导出线程数 (默认: 4)
  - `import_threads`: myloader 导入线程数 (默认: 4)

### 3. 配置文件更新

**旧版 config.ini**:
```ini
[global]
databases=platform_wx_mp
export_use_pump=false
import_max_allowed_packet=67108864
import_net_buffer_length=16384
```

**新版 config.ini**:
```ini
[global]
databases=platform_wx_mp
export_threads=4
import_threads=4
```

## 迁移步骤

### 1. 安装 mydumper
```bash
# macOS
brew install mydumper

# Ubuntu/Debian
sudo apt install mydumper

# CentOS/RHEL
sudo yum install mydumper

# 或使用提供的安装脚本
./install_mydumper.sh
```

### 2. 验证安装
```bash
python test_mydumper.py
```

### 3. 更新配置文件
- 备份旧的 config.ini
- 使用新的 config.ini.sample 作为模板
- 移除旧的参数，添加新的线程配置

### 4. 测试运行
```bash
python main.py
```

## 性能对比

| 工具 | 导出速度 | 导入速度 | 并行处理 | 内存使用 |
|------|----------|----------|----------|----------|
| mysqldump | 慢 | 慢 | 否 | 低 |
| mysqlpump | 中等 | 慢 | 部分 | 中等 |
| mydumper | 快 | 快 | 是 | 中等 |

## 常见问题

### Q: 为什么导出后没有 .sql 文件？
A: mydumper 会创建一个包含多个文件的目录，而不是单个 .sql 文件。

### Q: 如何调整性能？
A: 修改 config.ini 中的 export_threads 和 import_threads 参数。

### Q: 是否支持只导出特定表？
A: 支持，使用 tables.py 脚本可以导出特定表。

### Q: 如何查看导出进度？
A: mydumper 和 myloader 都提供详细的进度信息。