# Docker 部署指南

本指南将帮助你从 GitHub 拉取项目并使用 Docker 快速部署。

## 🚀 快速开始

### 方式一：一键部署脚本（推荐）

```bash
# 下载并运行一键部署脚本
curl -fsSL https://raw.githubusercontent.com/xianyu110/dsai/main/deploy_from_github.sh | bash
```

### 方式二：手动部署

#### 1️⃣ 安装 Docker

**macOS:**
```bash
brew install --cask docker
# 或从官网下载: https://www.docker.com/products/docker-desktop
```

**Ubuntu/Debian:**
```bash
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER
newgrp docker
```

**CentOS/RHEL:**
```bash
sudo yum install -y docker
sudo systemctl start docker
sudo systemctl enable docker
```

#### 2️⃣ 克隆项目

```bash
# 克隆仓库
git clone https://github.com/xianyu110/dsai.git
cd dsai
```

#### 3️⃣ 配置环境变量

```bash
# 复制环境变量模板
cp .env.example .env

# 编辑配置文件
nano .env  # 或使用 vim .env
```

**必填配置项:**
```bash
# AI 模型配置
AI_MODEL=deepseek
DEEPSEEK_API_KEY=your_deepseek_api_key

# 交易所配置
EXCHANGE_TYPE=okx
OKX_API_KEY=your_okx_api_key
OKX_SECRET=your_okx_secret
OKX_PASSWORD=your_okx_password

# 代理配置（如果需要）
HTTP_PROXY=http://127.0.0.1:7890
HTTPS_PROXY=http://127.0.0.1:7890
```

#### 4️⃣ 启动容器

```bash
# 构建并启动
docker-compose up -d

# 查看日志
docker-compose logs -f
```

#### 5️⃣ 访问应用

打开浏览器访问: **http://localhost:8888**

## 📋 常用命令

### 容器管理

```bash
# 启动容器
docker-compose up -d

# 停止容器
docker-compose down

# 重启容器
docker-compose restart

# 查看运行状态
docker-compose ps

# 查看实时日志
docker-compose logs -f

# 查看最近100行日志
docker-compose logs --tail=100
```

### 更新部署

```bash
# 拉取最新代码
git pull origin main

# 重新构建并启动
docker-compose up -d --build

# 清理旧镜像
docker image prune -f
```

### 数据管理

```bash
# 备份数据
tar -czf backup-$(date +%Y%m%d).tar.gz data/ logs/ .env

# 恢复数据
tar -xzf backup-20241022.tar.gz

# 查看容器内文件
docker-compose exec trading-bot ls -la /app
```

### 调试命令

```bash
# 进入容器
docker-compose exec trading-bot bash

# 查看容器资源使用
docker stats ai-trading-bot

# 查看容器详细信息
docker inspect ai-trading-bot

# 查看网络连接
docker network inspect dsai_trading-network
```

## 🔧 高级配置

### 自定义端口

编辑 `docker-compose.yml`:
```yaml
ports:
  - "5000:8888"  # 将本地5000端口映射到容器8888端口
```

### 资源限制

编辑 `docker-compose.yml`:
```yaml
deploy:
  resources:
    limits:
      cpus: '2.0'      # 最多使用2个CPU核心
      memory: 1024M    # 最多使用1GB内存
    reservations:
      cpus: '1.0'      # 保留1个CPU核心
      memory: 512M     # 保留512MB内存
```

### 使用外部数据库

```yaml
services:
  trading-bot:
    environment:
      - DATABASE_URL=postgresql://user:pass@db:5432/trading
    depends_on:
      - db

  db:
    image: postgres:15-alpine
    environment:
      - POSTGRES_USER=user
      - POSTGRES_PASSWORD=pass
      - POSTGRES_DB=trading
    volumes:
      - postgres_data:/var/lib/postgresql/data

volumes:
  postgres_data:
```

## 🌐 VPS/云服务器部署

### 准备工作

1. **购买 VPS**（推荐配置）
   - CPU: 2核
   - 内存: 2GB
   - 存储: 20GB SSD
   - 网络: 不限流量

2. **SSH 连接到服务器**
   ```bash
   ssh root@your-server-ip
   ```

### 部署步骤

```bash
# 1. 更新系统
apt update && apt upgrade -y

# 2. 安装 Docker 和 Docker Compose
curl -fsSL https://get.docker.com | sh

# 3. 安装 Git
apt install -y git

# 4. 克隆项目
git clone https://github.com/xianyu110/dsai.git
cd dsai

# 5. 配置环境变量
cp .env.example .env
nano .env

# 6. 启动服务
docker-compose up -d

# 7. 配置防火墙（如果有）
ufw allow 8888/tcp
ufw reload
```

### 使用域名访问

```bash
# 1. 安装 Nginx
apt install -y nginx

# 2. 配置反向代理
cat > /etc/nginx/sites-available/trading-bot << 'EOF'
server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://127.0.0.1:8888;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
EOF

# 3. 启用配置
ln -s /etc/nginx/sites-available/trading-bot /etc/nginx/sites-enabled/
nginx -t
systemctl reload nginx

# 4. 配置 HTTPS (可选)
apt install -y certbot python3-certbot-nginx
certbot --nginx -d your-domain.com
```

## 🔒 安全建议

### 1. 使用环境变量

**❌ 不要这样做:**
```yaml
environment:
  - OKX_API_KEY=hardcoded_key  # 不要硬编码密钥
```

**✅ 应该这样做:**
```yaml
environment:
  - OKX_API_KEY=${OKX_API_KEY}  # 从 .env 文件读取
```

### 2. 限制网络访问

```yaml
services:
  trading-bot:
    ports:
      - "127.0.0.1:8888:8888"  # 只允许本地访问
```

### 3. 定期更新

```bash
# 设置每周自动更新
crontab -e

# 添加以下行（每周日凌晨2点更新）
0 2 * * 0 cd /path/to/dsai && git pull && docker-compose up -d --build
```

### 4. 备份策略

```bash
# 创建备份脚本
cat > backup.sh << 'EOF'
#!/bin/bash
BACKUP_DIR="/backup/trading-bot"
DATE=$(date +%Y%m%d_%H%M%S)

mkdir -p $BACKUP_DIR
tar -czf $BACKUP_DIR/backup_$DATE.tar.gz data/ logs/ .env
find $BACKUP_DIR -name "backup_*.tar.gz" -mtime +7 -delete
EOF

chmod +x backup.sh

# 设置每天备份
crontab -e
0 3 * * * /path/to/dsai/backup.sh
```

## 🐛 故障排查

### 容器无法启动

```bash
# 查看详细错误日志
docker-compose logs trading-bot

# 检查配置文件
docker-compose config

# 检查端口占用
lsof -i :8888
```

### 网络连接问题

```bash
# 测试容器网络
docker-compose exec trading-bot ping -c 3 google.com

# 检查代理设置
docker-compose exec trading-bot env | grep PROXY

# 测试 API 连接
docker-compose exec trading-bot curl -I https://api.okx.com
```

### 内存不足

```bash
# 查看资源使用
docker stats ai-trading-bot

# 增加 swap（如果需要）
fallocate -l 2G /swapfile
chmod 600 /swapfile
mkswap /swapfile
swapon /swapfile
echo '/swapfile none swap sw 0 0' >> /etc/fstab
```

### 日志文件过大

```bash
# 清理日志
docker-compose down
rm -rf logs/*
docker-compose up -d

# 或配置日志轮转（已在 docker-compose.yml 中配置）
logging:
  options:
    max-size: "10m"
    max-file: "3"
```

## 📊 监控和告警

### 使用 Docker 自带监控

```bash
# 实时监控
docker stats ai-trading-bot

# 导出监控数据
docker stats --no-stream --format "table {{.Container}}\t{{.CPUPerc}}\t{{.MemUsage}}" > stats.txt
```

### 健康检查

```bash
# 查看健康状态
docker inspect ai-trading-bot | grep -A 10 Health

# 手动健康检查
curl http://localhost:8888/api/status
```

## 🔄 CI/CD 自动部署

### GitHub Actions 示例

创建 `.github/workflows/deploy.yml`:

```yaml
name: Deploy to VPS

on:
  push:
    branches: [ main ]

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - name: Deploy via SSH
        uses: appleboy/ssh-action@master
        with:
          host: ${{ secrets.VPS_HOST }}
          username: ${{ secrets.VPS_USER }}
          key: ${{ secrets.VPS_SSH_KEY }}
          script: |
            cd /path/to/dsai
            git pull origin main
            docker-compose up -d --build
```

## 📚 参考资源

- [Docker 官方文档](https://docs.docker.com/)
- [Docker Compose 文档](https://docs.docker.com/compose/)
- [项目 GitHub 仓库](https://github.com/xianyu110/dsai)
- [问题反馈](https://github.com/xianyu110/dsai/issues)

## ⚠️ 免责声明

本软件仅供学习和研究使用，使用本软件进行交易需要您自己承担风险。请确保遵守当地法律法规。

---

**技术支持**: 如有问题，请提交 [GitHub Issue](https://github.com/xianyu110/dsai/issues)
