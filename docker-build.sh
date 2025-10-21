#!/bin/bash

# Docker构建脚本 - 支持多种Dockerfile版本

echo "🐳 Docker构建选项"
echo "======================================"
echo "1. 标准版 (Dockerfile) - 包含完整依赖和安全配置"
echo "2. 简化版 (Dockerfile.simple) - 稳定的Debian基础"
echo "3. 最小版 (Dockerfile.minimal) - 最小依赖，适合老系统"
echo "======================================"
echo ""

# 如果有参数，直接使用
if [ -n "$1" ]; then
    choice=$1
else
    read -p "请选择版本 (1/2/3，默认1): " choice
    choice=${choice:-1}
fi

case $choice in
    1)
        DOCKERFILE="Dockerfile"
        echo "✅ 使用标准版 Dockerfile"
        ;;
    2)
        DOCKERFILE="Dockerfile.simple"
        echo "✅ 使用简化版 Dockerfile.simple"
        ;;
    3)
        DOCKERFILE="Dockerfile.minimal"
        echo "✅ 使用最小版 Dockerfile.minimal"
        ;;
    *)
        echo "❌ 无效选择，使用标准版"
        DOCKERFILE="Dockerfile"
        ;;
esac

echo ""
echo "🔨 开始构建..."
echo "======================================"

# 构建镜像
docker build -f ${DOCKERFILE} -t ai-trading-bot:latest .

if [ $? -eq 0 ]; then
    echo ""
    echo "======================================"
    echo "✅ 构建成功！"
    echo "======================================"
    echo ""
    echo "启动容器："
    echo "  docker-compose up -d"
    echo ""
    echo "或直接运行："
    echo "  docker run -d -p 8888:8888 --env-file .env ai-trading-bot:latest"
    echo "======================================"
else
    echo ""
    echo "======================================"
    echo "❌ 构建失败"
    echo "======================================"
    echo ""
    echo "建议尝试其他版本："
    echo "  ./docker-build.sh 2  # 简化版"
    echo "  ./docker-build.sh 3  # 最小版"
    echo "======================================"
    exit 1
fi
