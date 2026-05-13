# 手动执行完整离线部署方案
Claude Code触发了API速率限制，没关系，我直接给你**所有文件的完整可复制内容**和**逐行手动执行命令**，你不需要依赖任何自动编辑功能，10分钟就能完成整个流程。

## 第一步：替换所有部署文件（直接复制粘贴）
### 1. 替换根目录 `Dockerfile`（删除原有内容，粘贴以下）
```dockerfile
# 第一阶段：依赖构建层（仅在外网执行，所有联网操作在此完成）
FROM python:3.11-slim-bookworm AS builder

WORKDIR /app

# 复制离线依赖和需求文件
COPY offline-deps ./offline-deps
COPY requirements.txt .

# 【核心】纯离线安装所有依赖，不访问任何外部源
RUN pip install --no-index --find-links=./offline-deps -r requirements.txt && \
    rm -rf offline-deps requirements.txt

# 第二阶段：最终运行镜像（最小化体积，完全无联网依赖）
FROM python:3.11-slim-bookworm

WORKDIR /app

# 从构建层复制完整的Python环境（包含所有依赖）
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# 复制项目代码（仅必要文件）
COPY src ./src
COPY prompts ./prompts

# 创建数据和日志目录
RUN mkdir -p data logs

# 环境变量优化
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# 暴露WebSocket端口
EXPOSE 8000

# 启动命令
CMD ["python", "-m", "src.main"]
```

### 2. 创建/替换根目录 `.dockerignore`
```
# 开发工具和配置
.vscode/
.git/
.gitignore
*.log
.env
*.md
CLAUDE.md

# 临时文件和构建产物
__pycache__/
*.pyc
*.pyo
*.egg-info/
build/
dist/

# 离线依赖包（已在构建层安装，不需要打包进最终镜像）
offline-deps/
requirements.txt

# 部署脚本和导出文件
deploy/
export/
*.tar
*.tar.gz
```

### 3. 创建根目录 `.env.example`
```env
# 通义千问API配置
API_KEY=your_api_key_here
MODEL_NAME=qwen3.5-27b
MODEL_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1

# 闲鱼账号配置
COOKIES_STR=your_cookies_here

# 机器人核心配置
LOG_LEVEL=INFO
HEARTBEAT_INTERVAL=15
HEARTBEAT_TIMEOUT=5
TOKEN_REFRESH_INTERVAL=3600
TOKEN_RETRY_INTERVAL=300
MANUAL_MODE_TIMEOUT=3600
MESSAGE_EXPIRE_TIME=300000
TOGGLE_KEYWORDS=。
SIMULATE_HUMAN_TYPING=False

# 数据库配置
DB_PATH=data/chat_history.db
```

### 4. 替换 `deploy/build.sh`（删除原有内容，粘贴以下）
```bash
#!/bin/bash
set -euo pipefail

PROJECT_NAME="xianyu-bot"
IMAGE_NAME="xianyu-bot"
IMAGE_TAG="v1.0"
EXPORT_DIR="./export"

echo "=== 步骤1: 清理旧文件 ==="
cd ..
rm -rf offline-deps requirements.txt ${EXPORT_DIR}
mkdir -p ${EXPORT_DIR}

echo "=== 步骤2: 导出精确依赖列表 ==="
poetry export --format requirements.txt --output requirements.txt \
  --without-hashes --without-urls --no-dev

echo "=== 步骤3: 下载所有离线依赖包 ==="
pip download -r requirements.txt -d ./offline-deps \
  --platform linux_x86_64 \
  --python-version 3.11 \
  --only-binary=:all: \
  --no-cache-dir

echo "=== 步骤4: 构建Docker镜像 ==="
docker build -t ${IMAGE_NAME}:${IMAGE_TAG} .

echo "=== 步骤5: 在外网测试镜像运行 ==="
echo "正在测试镜像启动..."
docker run --rm -d --name test-${PROJECT_NAME} ${IMAGE_NAME}:${IMAGE_TAG}
sleep 5
if docker ps | grep -q test-${PROJECT_NAME}; then
    echo "✅ 镜像测试通过"
    docker stop test-${PROJECT_NAME}
else
    echo "❌ 镜像测试失败"
    docker logs test-${PROJECT_NAME}
    exit 1
fi

echo "=== 步骤6: 导出并压缩镜像 ==="
docker save -o ${EXPORT_DIR}/${IMAGE_NAME}-${IMAGE_TAG}.tar ${IMAGE_NAME}:${IMAGE_TAG}
cd ${EXPORT_DIR}
tar -czf ${IMAGE_NAME}-${IMAGE_TAG}.tar.gz ${IMAGE_NAME}-${IMAGE_TAG}.tar
rm ${IMAGE_NAME}-${IMAGE_TAG}.tar

echo "=== 计算MD5校验和 ==="
md5sum ${IMAGE_NAME}-${IMAGE_TAG}.tar.gz > ${IMAGE_NAME}-${IMAGE_TAG}.md5

echo ""
echo "========================================"
echo "✅ 构建完成！"
echo "镜像文件: ${EXPORT_DIR}/${IMAGE_NAME}-${IMAGE_TAG}.tar.gz"
echo "文件大小: $(du -h ${EXPORT_DIR}/${IMAGE_NAME}-${IMAGE_TAG}.tar.gz | cut -f1)"
echo "MD5校验: $(cat ${EXPORT_DIR}/${IMAGE_NAME}-${IMAGE_TAG}.md5)"
echo "========================================"
```

### 5. 替换 `deploy/deploy.sh`（删除原有内容，粘贴以下）
```bash
#!/bin/bash
set -euo pipefail

IMAGE_NAME="xianyu-bot"
IMAGE_TAG="v1.0"
CONTAINER_NAME="xianyu-bot"

echo "=== 步骤1: 验证文件完整性 ==="
if [ ! -f ${IMAGE_NAME}-${IMAGE_TAG}.tar.gz ]; then
    echo "❌ 错误：镜像文件不存在"
    exit 1
fi

if [ ! -f .env ]; then
    echo "❌ 错误：.env配置文件不存在"
    echo "请先复制.env.example为.env并填写正确配置"
    exit 1
fi

echo "=== 步骤2: 导入Docker镜像 ==="
echo "正在解压镜像..."
tar -xzf ${IMAGE_NAME}-${IMAGE_TAG}.tar.gz
echo "正在导入镜像..."
docker load -i ${IMAGE_NAME}-${IMAGE_TAG}.tar
rm -f ${IMAGE_NAME}-${IMAGE_TAG}.tar

echo "=== 步骤3: 清理旧容器 ==="
docker stop ${CONTAINER_NAME} 2>/dev/null || true
docker rm ${CONTAINER_NAME} 2>/dev/null || true

echo "=== 步骤4: 启动新容器 ==="
docker run -d \
  --name ${CONTAINER_NAME} \
  --restart=unless-stopped \
  -p 8000:8000 \
  -v $(pwd)/.env:/app/.env:ro \
  -v $(pwd)/data:/app/data \
  -v $(pwd)/logs:/app/logs \
  ${IMAGE_NAME}:${IMAGE_TAG}

echo ""
echo "========================================"
echo "✅ 部署完成！"
echo "容器状态:"
docker ps | grep ${CONTAINER_NAME}
echo ""
echo "查看实时日志: docker logs -f ${CONTAINER_NAME}"
echo "重启容器: docker restart ${CONTAINER_NAME}"
echo "停止容器: docker stop ${CONTAINER_NAME}"
echo "========================================"
```

### 6. 替换 `deploy/docker-compose.yml`（可选）
```yaml
version: '3.8'

services:
  xianyu-bot:
    image: xianyu-bot:v1.0
    container_name: xianyu-bot
    restart: unless-stopped
    ports:
      - "8000:8000"
    volumes:
      - ./.env:/app/.env:ro
      - ./data:/app/data
      - ./logs:/app/logs
    environment:
      - PYTHONUNBUFFERED=1
      - PYTHONDONTWRITEBYTECODE=1
```

## 第二步：外网手动执行构建流程
打开终端，逐行执行以下命令：
```bash
# 1. 进入项目根目录
cd /home/btroops/xianyu-bot

# 2. 清理现有环境，确保依赖纯净
poetry env remove python3.11 --all
rm -rf poetry.lock __pycache__ *.egg-info

# 3. 重新安装所有生产依赖
poetry install --no-root --no-dev --no-interaction

# 4. 【必须】验证项目能正常运行
poetry run python -m src.main
# 看到"连接注册完成"日志后按Ctrl+C停止

# 5. 进入deploy目录执行构建脚本
cd deploy
chmod +x build.sh deploy.sh
./build.sh
```

## 第三步：内网手动执行部署流程
1. 将 `deploy/export/xianyu-bot-v1.0.tar.gz` 和 `deploy/deploy.sh` 拷贝到内网服务器的 `/opt/xianyu-bot` 目录
2. 在内网服务器上执行：
```bash
# 1. 进入部署目录
cd /opt/xianyu-bot

# 2. 创建配置文件
cp .env.example .env
# 编辑.env文件，填入正确的API_KEY和COOKIES_STR
vim .env

# 3. 执行部署脚本
chmod +x deploy.sh
./deploy.sh
```

## 第四步：验证部署成功
```bash
# 查看容器运行状态
docker ps

# 查看实时日志
docker logs -f xianyu-bot

# 看到以下日志表示完全成功
# 2026-05-13 21:30:00 | INFO | 连接注册完成
# 2026-05-13 21:30:00 | INFO | 机器人已启动，等待消息...
```

