#!/bin/bash

# VPS部署脚本 - 部署到 /opt/ai_tradeauto
# 使用方法: ./deploy_to_vps.sh [VPS_IP]

set -e

# 配置变量
VPS_IP=${1:-"45.207.201.101"}
VPS_USER="root"
DEPLOY_PATH="/opt/ai_tradeauto"
LOCAL_PATH="."

echo "🚀 开始部署AI交易机器人到VPS"
echo "======================================"
echo "VPS地址: ${VPS_USER}@${VPS_IP}"
echo "部署路径: ${DEPLOY_PATH}"
echo "======================================"

# 1. 检查本地文件
echo ""
echo "📋 1. 检查本地文件..."
if [ ! -f ".env" ]; then
    echo "❌ 错误: 未找到 .env 文件"
    echo "请先复制 .env.example 为 .env 并填写配置"
    exit 1
fi

if [ ! -f "docker-compose.yml" ]; then
    echo "❌ 错误: 未找到 docker-compose.yml"
    exit 1
fi

echo "✅ 本地文件检查完成"

# 2. 连接VPS并检查环境
echo ""
echo "🔗 2. 检查VPS环境..."
ssh ${VPS_USER}@${VPS_IP} << 'EOF'
    echo "检查Docker..."
    if ! command -v docker &> /dev/null; then
        echo "⚠️  未安装Docker，开始安装..."
        curl -fsSL https://get.docker.com | sh
        systemctl start docker
        systemctl enable docker
    fi
    echo "✅ Docker已安装: $(docker --version)"

    echo "检查Docker Compose..."
    if ! command -v docker-compose &> /dev/null; then
        echo "⚠️  未安装Docker Compose，开始安装..."
        curl -L "https://github.com/docker/compose/releases/download/1.29.2/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
        chmod +x /usr/local/bin/docker-compose
    fi
    echo "✅ Docker Compose已安装: $(docker-compose --version)"
EOF

# 3. 创建部署目录
echo ""
echo "📁 3. 创建部署目录..."
ssh ${VPS_USER}@${VPS_IP} "mkdir -p ${DEPLOY_PATH}/{logs,data}"

# 4. 上传文件
echo ""
echo "📤 4. 上传项目文件..."
rsync -avz --progress \
    --exclude='__pycache__' \
    --exclude='*.pyc' \
    --exclude='.git' \
    --exclude='node_modules' \
    --exclude='logs/*' \
    --exclude='data/*' \
    ${LOCAL_PATH}/ ${VPS_USER}@${VPS_IP}:${DEPLOY_PATH}/

echo "✅ 文件上传完成"

# 5. 部署Docker容器
echo ""
echo "🐳 5. 部署Docker容器..."
ssh ${VPS_USER}@${VPS_IP} << EOF
    cd ${DEPLOY_PATH}

    # 停止旧容器
    echo "停止旧容器..."
    docker-compose down 2>/dev/null || true

    # 构建新镜像
    echo "构建Docker镜像..."
    docker-compose build

    # 启动容器
    echo "启动容器..."
    docker-compose up -d

    # 等待容器启动
    echo "等待服务启动..."
    sleep 5

    # 显示状态
    echo ""
    echo "======================================"
    echo "📊 容器状态:"
    docker-compose ps

    echo ""
    echo "📋 最近日志:"
    docker-compose logs --tail=20
EOF

# 6. 健康检查
echo ""
echo "🏥 6. 健康检查..."
sleep 3
if ssh ${VPS_USER}@${VPS_IP} "curl -f http://localhost:8888/api/status" &> /dev/null; then
    echo "✅ 服务健康检查通过"
else
    echo "⚠️  健康检查失败，请查看日志"
fi

# 7. 完成
echo ""
echo "======================================"
echo "🎉 部署完成！"
echo "======================================"
echo "访问地址: http://${VPS_IP}:8888"
echo ""
echo "常用命令:"
echo "  查看日志: ssh ${VPS_USER}@${VPS_IP} 'cd ${DEPLOY_PATH} && docker-compose logs -f'"
echo "  重启服务: ssh ${VPS_USER}@${VPS_IP} 'cd ${DEPLOY_PATH} && docker-compose restart'"
echo "  停止服务: ssh ${VPS_USER}@${VPS_IP} 'cd ${DEPLOY_PATH} && docker-compose down'"
echo "  查看状态: ssh ${VPS_USER}@${VPS_IP} 'cd ${DEPLOY_PATH} && docker-compose ps'"
echo "======================================"
