#!/bin/bash
# ============================================
# AI交易机器人快速部署脚本
# ============================================

set -e  # 遇到错误立即退出

echo "🚀 开始部署AI交易机器人..."
echo ""

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 检查Docker是否安装
echo "📦 检查Docker环境..."
if ! command -v docker &> /dev/null; then
    echo -e "${RED}❌ Docker未安装，请先安装Docker${NC}"
    echo "安装命令: curl -fsSL https://get.docker.com | sh"
    exit 1
fi

if ! command -v docker-compose &> /dev/null; then
    echo -e "${RED}❌ Docker Compose未安装${NC}"
    exit 1
fi

echo -e "${GREEN}✅ Docker环境检查通过${NC}"
echo ""

# 检查.env文件
echo "🔑 检查环境变量配置..."
if [ ! -f ".env" ]; then
    echo -e "${YELLOW}⚠️  未找到.env文件${NC}"
    echo "正在复制 .env.example 为 .env"
    cp .env.example .env
    echo -e "${YELLOW}请编辑 .env 文件，填写真实的API密钥${NC}"
    echo "编辑命令: nano .env"
    echo ""
    read -p "是否现在编辑 .env 文件? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        ${EDITOR:-nano} .env
    else
        echo -e "${RED}请手动编辑 .env 文件后重新运行此脚本${NC}"
        exit 1
    fi
fi

# 设置.env文件权限
chmod 600 .env
echo -e "${GREEN}✅ 环境变量配置完成${NC}"
echo ""

# 创建必要目录
echo "📁 创建数据目录..."
mkdir -p logs data
echo -e "${GREEN}✅ 数据目录创建完成${NC}"
echo ""

# 停止旧容器（如果存在）
echo "🛑 停止旧容器..."
docker-compose down 2>/dev/null || true
echo ""

# 构建镜像
echo "🔨 构建Docker镜像..."
docker-compose build --no-cache
echo -e "${GREEN}✅ 镜像构建完成${NC}"
echo ""

# 启动容器
echo "🚀 启动容器..."
docker-compose up -d
echo ""

# 等待服务启动
echo "⏳ 等待服务启动..."
sleep 5

# 检查容器状态
echo "🔍 检查容器状态..."
if docker ps | grep -q "ai-trading-bot"; then
    echo -e "${GREEN}✅ 容器启动成功${NC}"
else
    echo -e "${RED}❌ 容器启动失败${NC}"
    echo "查看日志: docker-compose logs"
    exit 1
fi
echo ""

# 显示容器信息
echo "📊 容器信息:"
docker-compose ps
echo ""

# 测试API
echo "🔍 测试API连接..."
sleep 3
if curl -s -f http://localhost:8888/api/status > /dev/null; then
    echo -e "${GREEN}✅ API测试成功${NC}"
else
    echo -e "${YELLOW}⚠️  API暂时无法访问，可能还在启动中${NC}"
fi
echo ""

# 获取服务器IP
SERVER_IP=$(curl -s ifconfig.me 2>/dev/null || echo "your-server-ip")

# 部署完成
echo "=========================================="
echo -e "${GREEN}🎉 部署完成！${NC}"
echo "=========================================="
echo ""
echo "📡 访问地址:"
echo "   本地: http://localhost:8888"
echo "   远程: http://${SERVER_IP}:8888"
echo ""
echo "📝 常用命令:"
echo "   查看日志: docker-compose logs -f"
echo "   停止服务: docker-compose down"
echo "   重启服务: docker-compose restart"
echo "   进入容器: docker exec -it ai-trading-bot bash"
echo ""
echo "📖 详细文档: README_DEPLOY.md"
echo ""
echo "⚠️  安全提醒:"
echo "   1. 请确保API密钥权限正确（禁用提现）"
echo "   2. 在交易所设置IP白名单"
echo "   3. 配置防火墙限制访问"
echo "   4. 定期备份数据和配置"
echo ""
echo -e "${YELLOW}🔒 建议配置防火墙:${NC}"
echo "   sudo ufw allow 8888/tcp"
echo "   sudo ufw enable"
echo ""

# 显示实时日志（可选）
read -p "是否查看实时日志? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    docker-compose logs -f
fi
