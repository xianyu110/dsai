#!/bin/bash

# AI交易机器人打包脚本
# 打包所有必要文件用于VPS部署

set -e

PROJECT_NAME="ai-trading-bot"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
PACKAGE_NAME="${PROJECT_NAME}_${TIMESTAMP}.tar.gz"
TEMP_DIR="/tmp/${PROJECT_NAME}_temp"
SOURCE_DIR=$(pwd)

echo "📦 开始打包AI交易机器人"
echo "======================================"

# 1. 创建临时目录
echo "1. 创建临时打包目录..."
rm -rf ${TEMP_DIR}
mkdir -p ${TEMP_DIR}/${PROJECT_NAME}

# 2. 复制文件
echo "2. 复制项目文件..."
rsync -av --progress \
    --exclude='__pycache__' \
    --exclude='*.pyc' \
    --exclude='*.pyo' \
    --exclude='.git' \
    --exclude='.gitignore' \
    --exclude='node_modules' \
    --exclude='logs/*' \
    --exclude='data/*' \
    --exclude='*.tar.gz' \
    --exclude='.DS_Store' \
    --exclude='*.log' \
    --exclude='.idea' \
    ${SOURCE_DIR}/ ${TEMP_DIR}/${PROJECT_NAME}/

# 3. 创建必要的目录
echo "3. 创建必要的目录..."
mkdir -p ${TEMP_DIR}/${PROJECT_NAME}/logs
mkdir -p ${TEMP_DIR}/${PROJECT_NAME}/data
touch ${TEMP_DIR}/${PROJECT_NAME}/logs/.gitkeep
touch ${TEMP_DIR}/${PROJECT_NAME}/data/.gitkeep

# 4. 检查.env文件
echo "4. 检查配置文件..."
if [ -f "${TEMP_DIR}/${PROJECT_NAME}/.env" ]; then
    echo "✅ 发现 .env 文件，已包含在打包中"
else
    echo "⚠️  未发现 .env 文件，只包含 .env.example"
    echo "   部署时需要手动创建 .env 文件"
fi

# 5. 创建部署说明
echo "5. 创建部署说明..."
cat > ${TEMP_DIR}/${PROJECT_NAME}/DEPLOY_README.txt << 'EOF'
==========================================
AI交易机器人 - VPS部署说明
==========================================

【部署步骤】

1. 上传到VPS
-----------
scp ai-trading-bot_*.tar.gz root@你的VPS_IP:/tmp/

2. SSH到VPS并解压
-----------------
ssh root@你的VPS_IP
cd /tmp
tar -xzf ai-trading-bot_*.tar.gz
mv ai-trading-bot /opt/ai_tradeauto
cd /opt/ai_tradeauto

3. 配置环境变量
--------------
# 如果没有.env文件，需要创建
cp .env.example .env
nano .env

# 必填配置：
OKX_API_KEY=你的API密钥
OKX_SECRET=你的SECRET
OKX_PASSWORD=你的密码
RELAY_API_KEY=你的中转API密钥

4. 安装Docker（如果未安装）
--------------------------
# 安装Docker
curl -fsSL https://get.docker.com | sh
systemctl start docker
systemctl enable docker

# 安装Docker Compose
curl -L "https://github.com/docker/compose/releases/download/1.29.2/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
chmod +x /usr/local/bin/docker-compose

5. 启动服务
----------
docker-compose build
docker-compose up -d
docker-compose logs -f

6. 访问Web界面
-------------
http://你的VPS_IP:8888

【常用命令】

查看日志:   docker-compose logs -f
重启服务:   docker-compose restart
停止服务:   docker-compose down
查看状态:   docker-compose ps

【防火墙配置】

Ubuntu/Debian:
  ufw allow 8888/tcp

CentOS/RHEL:
  firewall-cmd --permanent --add-port=8888/tcp
  firewall-cmd --reload

==========================================
EOF

# 6. 打包
echo "6. 创建压缩包..."
cd ${TEMP_DIR}
tar -czf ${PACKAGE_NAME} ${PROJECT_NAME}/

# 7. 移动到源目录
echo "7. 移动到项目目录..."
mv ${PACKAGE_NAME} ${SOURCE_DIR}/

# 8. 清理临时文件
echo "8. 清理临时文件..."
rm -rf ${TEMP_DIR}

# 9. 显示打包信息
echo ""
echo "======================================"
echo "✅ 打包完成！"
echo "======================================"
echo "📦 文件名: ${PACKAGE_NAME}"
echo "📏 文件大小: $(du -h ${SOURCE_DIR}/${PACKAGE_NAME} | cut -f1)"
echo "📍 位置: ${SOURCE_DIR}/${PACKAGE_NAME}"
echo ""
echo "包含的文件："
tar -tzf ${SOURCE_DIR}/${PACKAGE_NAME} | head -30
echo "..."
echo "共 $(tar -tzf ${SOURCE_DIR}/${PACKAGE_NAME} | wc -l) 个文件/目录"
echo ""
echo "======================================"
echo "📤 部署方法："
echo ""
echo "1️⃣  上传到VPS:"
echo "   scp ${PACKAGE_NAME} root@45.207.201.101:/tmp/"
echo ""
echo "2️⃣  SSH到VPS并解压:"
echo "   ssh root@45.207.201.101"
echo "   cd /tmp"
echo "   tar -xzf ${PACKAGE_NAME}"
echo "   mv ai-trading-bot /opt/ai_tradeauto"
echo "   cd /opt/ai_tradeauto"
echo ""
echo "3️⃣  配置并启动:"
echo "   nano .env  # 编辑配置文件"
echo "   docker-compose up -d"
echo ""
echo "4️⃣  访问Web界面:"
echo "   http://45.207.201.101:8888"
echo "======================================"
