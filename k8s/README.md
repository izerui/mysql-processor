# Kubernetes 部署指南 - platform-yunji命名空间

## 🚀 部署方式选择

### 方式1：手动触发（推荐）
使用Job方式，手动触发备份任务

### 方式2：定时任务（可选）
使用CronJob方式，定时自动执行

## 手动触发部署（Job方式）

### 1. 配置数据库连接
编辑 `config.yaml` 文件，修改数据库连接信息：
```bash
# 修改config.yaml中的数据库配置
kubectl apply -f k8s/config.yaml -n platform-yunji
```

### 2. 创建命名空间（如果不存在）
```bash
kubectl create namespace platform-yunji
```

### 3. 手动触发备份
```bash
# 应用配置和存储
kubectl apply -f k8s/config.yaml -n platform-yunji
kubectl apply -f k8s/job.yaml -n platform-yunji

# 或者使用一键脚本
cd k8s/
./run-backup.sh
```

### 4. 手动命令方式
```bash
# 查看任务状态
kubectl get jobs -n platform-yunji
kubectl get pods -n platform-yunji --selector=job-name=mysql-processor-job

# 查看日志
kubectl logs -f -n platform-yunji -l job-name=mysql-processor-job
```

## 定时任务部署（可选）

### 使用CronJob
```bash
# 创建定时任务（每天凌晨2点执行）
kubectl apply -f k8s/config.yaml -n platform-yunji
kubectl apply -f k8s/cronjob.yaml -n platform-yunji

# 查看CronJob状态
kubectl get cronjob -n platform-yunji mysql-processor
```

## 配置说明

### 命名空间
- **命名空间**: `platform-yunji`
- **创建命令**: `kubectl create namespace platform-yunji`

### 任务触发
- **手动触发**: 使用 `kubectl apply -f k8s/job.yaml -n platform-yunji`
- **任务名称**: `mysql-processor-job`
- **并发策略**: 每次触发创建新的Job实例

### 存储配置
- **存储大小**: 默认10Gi，可在PVC中调整
- **存储类**: 使用SSD存储类 `ssd`
- **PVC名称**: `mysql-processor-pvc`
- **挂载路径**:
  - `/app/dumps` - 备份文件存储
  - `/app/mysql` - MySQL工具和数据存储

### 资源限制
- **内存请求**: 512Mi
- **内存限制**: 2Gi
- **CPU请求**: 250m
- **CPU限制**: 1000m

## 自定义配置

### 修改数据库配置
```bash
# 编辑配置
kubectl edit configmap mysql-processor-config -n platform-yunji

# 重新应用配置
kubectl apply -f k8s/config.yaml -n platform-yunji
```

### 调整存储大小
```bash
# 扩展PVC存储（需要先删除旧PVC）
kubectl delete pvc mysql-processor-pvc -n platform-yunji
# 修改job.yaml或cronjob.yaml中的storage大小后重新应用
kubectl apply -f k8s/job.yaml -n platform-yunji
```

### 更新镜像版本
```bash
kubectl set image job/mysql-processor-job mysql-processor=izerui/mysql-processor:v1.1.0 -n platform-yunji
```

## 监控和日志

### 查看任务执行
```bash
# 查看当前任务
kubectl get jobs -n platform-yunji

# 查看Pod状态
kubectl get pods -n platform-yunji

# 查看详细日志
kubectl logs -n platform-yunji -l app=mysql-processor --tail=100
```

### 查看存储文件
```bash
# 进入运行中的Pod查看备份文件
kubectl exec -it -n platform-yunji $(kubectl get pods -n platform-yunji --selector=job-name=mysql-processor-job --sort-by=.metadata.creationTimestamp -o jsonpath='{.items[0].metadata.name}') -- ls -la /app/dumps/

# 查看MySQL工具目录
kubectl exec -it -n platform-yunji $(kubectl get pods -n platform-yunji --selector=job-name=mysql-processor-job --sort-by=.metadata.creationTimestamp -o jsonpath='{.items[0].metadata.name}') -- ls -la /app/mysql/
```

## 故障排除

### 常见问题

#### 1. 命名空间不存在
```bash
# 创建命名空间
kubectl create namespace platform-yunji
```

#### 2. 权限问题
```bash
# 检查用户权限
kubectl auth can-i create jobs -n platform-yunji
kubectl auth can-i create configmaps -n platform-yunji
```

#### 3. 存储类问题
```bash
# 检查存储类是否可用
kubectl get storageclass -n platform-yunji
# 如果没有ssd存储类，可以修改为集群中可用的SSD存储类
```

#### 4. 数据库连接失败
```bash
# 检查配置是否正确加载
kubectl get configmap mysql-processor-config -o yaml -n platform-yunji

# 测试连接（临时Pod）
kubectl run mysql-test -n platform-yunji --image=mysql:8.0 --rm -it --restart=Never -- mysql -h<source-host> -u<user> -p<password>
```

# 清理资源
```bash
# 删除所有资源
kubectl delete -f k8s/ -n platform-yunji

# 清理特定资源
kubectl delete job mysql-processor-job -n platform-yunji
kubectl delete pvc mysql-processor-pvc -n platform-yunji
kubectl delete configmap mysql-processor-config -n platform-yunji
```

# 或者单独删除
kubectl delete job mysql-processor-job -n platform-yunji
kubectl delete pvc mysql-processor-pvc -n platform-yunji
kubectl delete configmap mysql-processor-config -n platform-yunji

# 删除命名空间（谨慎操作）
kubectl delete namespace platform-yunji
```

## 📁 文件结构
```
k8s/
├── config.yaml          # ConfigMap配置文件
├── job.yaml            # Job配置文件（手动触发）
├── cronjob.yaml        # CronJob配置文件（可选定时任务）
├── run-backup.sh       # 一键运行脚本
└── README.md           # 部署说明文档
```
