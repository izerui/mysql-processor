# GitHub Actions Docker 构建配置说明

## 配置步骤

### 1. 设置 Docker Hub 凭据

在 GitHub 仓库中设置以下 Secrets：

1. 进入仓库的 `Settings` -> `Secrets and variables` -> `Actions`
2. 点击 `New repository secret` 添加以下变量：

- **DOCKER_USERNAME**: 你的 Docker Hub 用户名（例如：`izerui`）
- **DOCKER_PASSWORD**: 你的 Docker Hub 密码或访问令牌

### 2. 触发条件

工作流会在以下情况下自动触发：

- **推送到 main/master 分支**
- **创建 Pull Request 到 main/master 分支**
- **推送版本标签**（如 `v1.0.0`）

### 3. 构建结果

构建完成后，镜像将推送到：

- `izerui/mysql-processor:latest`（最新版本）
- `izerui/mysql-processor:{commit-sha}`（基于提交哈希的版本）

## 本地测试

### 手动构建测试
```bash
# 构建镜像
docker build -f Dockerfile -t mysql-processor .

# 本地测试
docker run --rm -it mysql-processor

# 推送到仓库（需要登录）
docker login
docker tag mysql-processor izerui/mysql-processor:latest
docker push izerui/mysql-processor:latest
```

### 使用 GitHub CLI 设置 Secrets
```bash
# 安装 GitHub CLI 后执行
gh secret set DOCKER_USERNAME --body "your-docker-username"
gh secret set DOCKER_PASSWORD --body "your-docker-password"
```

## 工作流文件说明

- **`.github/workflows/docker-build-push.yml`**: 主要的构建和推送工作流
- **`.github/workflows/docker-build.yml`**: 高级版本，支持多架构和语义化标签

## 故障排除

### 构建失败常见问题

1. **权限错误**: 检查 DOCKER_USERNAME 和 DOCKER_PASSWORD 是否正确
2. **网络问题**: 确保 GitHub Actions 可以访问 Docker Hub
3. **构建缓存**: 清理构建缓存或增加超时时间

### 查看构建日志

1. 进入 GitHub 仓库的 `Actions` 标签页
2. 点击最新的工作流运行
3. 查看详细的构建日志

## 自定义配置

### 修改镜像名称
编辑 `.github/workflows/docker-build-push.yml` 中的 `tags` 部分：

```yaml
tags: |
  your-username/mysql-processor:latest
  your-username/mysql-processor:${{ github.sha }}
```

### 添加版本标签
在推送到 main 分支时自动添加版本标签：

```yaml
on:
  push:
    tags: [ 'v*' ]
```

构建结果将包括：
- `izerui/mysql-processor:latest`
- `izerui/mysql-processor:1.0.0` (基于标签)