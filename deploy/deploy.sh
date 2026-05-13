#!/bin/bash
set -e

IMAGE_NAME="xianyu-bot"
IMAGE_TAG="latest"
CONTAINER_NAME="xianyu-bot"
EXPORT_DIR="${1:-./export}"

echo "=== 步骤 1: 导入镜像 ==="
tar -xzf ${EXPORT_DIR}/${IMAGE_NAME}-${IMAGE_TAG}.tar.gz
docker load -i ${EXPORT_DIR}/${IMAGE_NAME}-${IMAGE_TAG}.tar
rm ${EXPORT_DIR}/${IMAGE_NAME}-${IMAGE_TAG}.tar.gz
rm ${EXPORT_DIR}/${IMAGE_NAME}-${IMAGE_TAG}.tar

echo "=== 步骤 2: 检查配置文件 ==="
if [ ! -f .env ]; then
    echo "错误：.env 文件不存在"
    echo "请从 .env.example 复制并填写配置：cp .env.example .env"
    exit 1
fi

echo "=== 步骤 3: 停止并删除旧容器（如有） ==="
docker stop ${CONTAINER_NAME} 2>/dev/null || true
docker rm ${CONTAINER_NAME} 2>/dev/null || true

echo "=== 步骤 4: 启动新容器 ==="
docker run -d \
    --name ${CONTAINER_NAME} \
    --restart unless-stopped \
    --network host \
    -v $(pwd)/.env:/app/.env:ro \
    -v $(pwd)/data:/app/data \
    ${IMAGE_NAME}:${IMAGE_TAG}

echo "=== 完成 ==="
echo "使用以下命令查看日志："
echo "  docker logs -f ${CONTAINER_NAME}"
