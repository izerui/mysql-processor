#!/bin/bash
# MySQL Processor 手动备份脚本 - platform-yunji命名空间

set -e

# 命名空间
NAMESPACE="platform-yunji"

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}🚀 MySQL Processor 手动备份脚本${NC}"
echo -e "${GREEN}命名空间: $NAMESPACE${NC}"
echo "================================"

# 检查kubectl是否安装
if ! command -v kubectl &> /dev/null; then
    echo -e "${RED}❌ kubectl 未安装，请先安装kubectl${NC}"
    exit 1
fi

# 检查集群连接
if ! kubectl cluster-info &> /dev/null; then
    echo -e "${RED}❌ 无法连接到Kubernetes集群${NC}"
    exit 1
fi

# 检查命名空间是否存在
if ! kubectl get namespace $NAMESPACE &> /dev/null; then
    echo -e "${YELLOW}⚠️  命名空间 $NAMESPACE 不存在，正在创建...${NC}"
    kubectl create namespace $NAMESPACE
fi

# 应用配置和存储（如果不存在）
echo -e "${YELLOW}📋 检查配置...${NC}"
kubectl apply -f config.yaml -n $NAMESPACE
kubectl apply -f job.yaml -n $NAMESPACE

# 获取最新的Job名称
JOB_NAME="mysql-processor-job"
echo -e "${YELLOW}⏳ 等待任务启动...${NC}"

# 等待Job创建
sleep 3

# 获取Pod名称
POD_NAME=$(kubectl get pods -n $NAMESPACE --selector=job-name=$JOB_NAME --sort-by=.metadata.creationTimestamp -o jsonpath='{.items[-1].metadata.name}')

if [ -z "$POD_NAME" ]; then
    echo -e "${RED}❌ 无法找到运行的Pod${NC}"
    exit 1
fi

echo -e "${GREEN}✅ 任务已启动，Pod: $POD_NAME${NC}"

# 显示Pod状态
echo -e "${YELLOW}📊 Pod状态:${NC}"
kubectl get pod $POD_NAME -n $NAMESPACE

# 实时查看日志
echo -e "${YELLOW}📄 实时日志:${NC}"
kubectl logs -f $POD_NAME -n $NAMESPACE

# 检查任务完成状态
echo -e "${YELLOW}🔍 检查任务状态...${NC}"
kubectl wait --for=condition=complete job/$JOB_NAME -n $NAMESPACE --timeout=300s

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✅ 备份任务执行成功！${NC}"

    # 显示备份文件
    echo -e "${YELLOW}📁 备份文件:${NC}"
    kubectl exec -n $NAMESPACE $POD_NAME -- ls -la /app/dumps/
else
    echo -e "${RED}❌ 备份任务执行失败${NC}"
    kubectl describe pod -n $NAMESPACE $POD_NAME
    exit 1
fi

echo -e "${GREEN}🎉 备份完成！${NC}"
echo -e "${YELLOW}💡 提示: 使用 'kubectl delete job $JOB_NAME -n $NAMESPACE' 清理完成的任务${NC}"
