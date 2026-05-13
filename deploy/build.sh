#!/bin/bash
set -e

IMAGE_NAME="xianyu-bot"
IMAGE_TAG="latest"
EXPORT_DIR="./export"

echo "=== 步骤 1: 构建 Docker 镜像 ==="
docker build -t ${IMAGE_NAME}:${IMAGE_TAG} .

echo "=== 步骤 2: 导出镜像为 tar 文件 ==="
mkdir -p ${EXPORT_DIR}
docker save -o ${EXPORT_DIR}/${IMAGE_NAME}-${IMAGE_TAG}.tar ${IMAGE_NAME}:${IMAGE_TAG}

echo "=== 步骤 3: 压缩镜像文件 ==="
cd ${EXPORT_DIR}
tar -czf ${IMAGE_NAME}-${IMAGE_TAG}.tar.gz ${IMAGE_NAME}-${IMAGE_TAG}.tar
rm ${IMAGE_NAME}-${IMAGE_TAG}.tar

echo "=== 完成 ==="
echo "导出的镜像文件：${EXPORT_DIR}/${IMAGE_NAME}-${IMAGE_TAG}.tar.gz"
ls -lh ${EXPORT_DIR}/
