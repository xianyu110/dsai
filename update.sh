#!/bin/bash
# ============================================
# AI交易机器人更新脚本
# ============================================

set -e

echo "🔄 开始更新AI交易机器人..."
echo ""

# 颜色定义
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# 备份当前配置
echo "💾 备份当前配置..."
timestamp=$(date +%Y%m%d_%H%M%S)
mkdir -p backups
cp .env backups/.env.${timestamp}
tar -czf backups/data-${timestamp}.tar.gz logs/ data/ 2>/dev/null || true
echo -e "${GREEN}✅ 配置已备份到 backups/${NC}"
echo ""

# 拉取最新代码
echo "📥 拉取最新代码..."
if [ -d ".git" ]; then
    git pull
    echo -e "${GREEN}✅ 代码更新完成${NC}"
else
    echo -e "${YELLOW}⚠️  不是Git仓库，跳过代码拉取${NC}"
fi
echo ""

# 停止服务
echo "🛑 停止旧服务..."
docker-compose down
echo ""

# 重新构建镜像
echo "🔨 重新构建镜像..."
docker-compose build
echo ""

# 启动服务
echo "🚀 启动新服务..."
docker-compose up -d
echo ""

# 等待启动
echo "⏳ 等待服务启动..."
sleep 5

# 检查状态
if docker ps | grep -q "ai-trading-bot"; then
    echo -e "${GREEN}✅ 更新成功！${NC}"
    echo ""
    echo "查看日志: docker-compose logs -f"
else
    echo -e "${RED}❌ 启动失败，正在恢复...${NC}"
    cp backups/.env.${timestamp} .env
    docker-compose up -d
fi

# 清理旧备份（保留最近5个）
find backups -name "*.tar.gz" -type f | sort -r | tail -n +6 | xargs rm -f 2>/dev/null || true
find backups -name ".env.*" -type f | sort -r | tail -n +6 | xargs rm -f 2>/dev/null || true
