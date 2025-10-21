# 🐳 Docker + VPS 部署指南

完整的AI交易机器人Docker部署方案，适用于VPS服务器。

## 📋 目录

- [前置要求](#前置要求)
- [快速开始](#快速开始)
- [安全配置](#安全配置)
- [部署步骤](#部署步骤)
- [运维管理](#运维管理)
- [监控告警](#监控告警)
- [故障排查](#故障排查)

---

## 前置要求

### 1. VPS服务器
推荐配置：
- **CPU**: 1核及以上
- **内存**: 1GB及以上
- **存储**: 10GB及以上
- **系统**: Ubuntu 20.04/22.04 或 CentOS 7/8

推荐服务商（按价格排序）：
- [Vultr](https://www.vultr.com/) - $3.5/月起
- [DigitalOcean](https://www.digitalocean.com/) - $4/月起
- [Linode](https://www.linode.com/) - $5/月起
- 阿里云/腾讯云 - ¥30/月起

### 2. 安装Docker
```bash
# Ubuntu/Debian
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
sudo usermod -aG docker $USER

# 重新登录或执行
newgrp docker

# 验证安装
docker --version
docker-compose --version
```

---

## 快速开始

### 1. 克隆代码到服务器
```bash
# SSH登录到VPS
ssh root@your-server-ip

# 克隆仓库（或上传代码）
git clone <你的仓库地址> /opt/trading-bot
cd /opt/trading-bot

# 如果使用压缩包上传
scp -r ./ds root@your-server-ip:/opt/trading-bot
```

### 2. 配置环境变量
```bash
# 复制环境变量模板
cp .env.example .env

# 编辑环境变量（务必填写真实密钥）
nano .env
```

**⚠️ 重要：务必修改以下配置**
```bash
# AI模型配置
AI_MODEL=deepseek
RELAY_API_KEY=your_relay_api_key_here

# 交易所配置（选择OKX或Binance）
EXCHANGE_TYPE=okx

# OKX API密钥（从OKX后台获取）
OKX_API_KEY=your_okx_api_key
OKX_SECRET=your_okx_secret
OKX_PASSWORD=your_okx_password

# 如果使用Binance
# BINANCE_API_KEY=your_binance_api_key
# BINANCE_SECRET=your_binance_secret
```

### 3. 启动服务
```bash
# 构建并启动容器
docker-compose up -d

# 查看日志
docker-compose logs -f
```

### 4. 访问Web界面
```
http://your-server-ip:8888
```

---

## 安全配置

### 🔒 交易所API安全设置

#### OKX API设置
1. 登录 [OKX API管理](https://www.okx.com/account/my-api)
2. 创建API密钥，**权限设置**：
   - ✅ **读取** (Read)
   - ✅ **交易** (Trade)
   - ❌ **提现** (Withdraw) - **禁用**
3. **IP白名单**：添加你的VPS IP地址
4. 记录：API Key、Secret Key、Passphrase

#### Binance API设置
1. 登录 [Binance API管理](https://www.binance.com/en/my/settings/api-management)
2. 创建API密钥，**权限设置**：
   - ✅ Enable Reading
   - ✅ Enable Spot & Margin Trading
   - ❌ Enable Withdrawals - **禁用**
3. **IP访问限制**：仅允许你的VPS IP

### 🛡️ 服务器安全

#### 1. 配置防火墙
```bash
# Ubuntu UFW防火墙
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow ssh
sudo ufw allow 8888/tcp
sudo ufw enable

# CentOS Firewalld
sudo firewall-cmd --permanent --add-port=8888/tcp
sudo firewall-cmd --permanent --add-service=ssh
sudo firewall-cmd --reload
```

#### 2. 设置Nginx反向代理（可选，推荐）
```bash
# 安装Nginx
sudo apt install nginx

# 配置反向代理
sudo nano /etc/nginx/sites-available/trading-bot

# 添加配置
server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://localhost:8888;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}

# 启用配置
sudo ln -s /etc/nginx/sites-available/trading-bot /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx
```

#### 3. 配置SSL证书（推荐）
```bash
# 安装Certbot
sudo apt install certbot python3-certbot-nginx

# 获取免费SSL证书
sudo certbot --nginx -d your-domain.com

# 自动续期
sudo certbot renew --dry-run
```

### 🔐 环境变量加密

**不要将.env文件提交到Git！**
```bash
# 确认.gitignore包含
echo ".env" >> .gitignore

# 设置文件权限
chmod 600 .env

# 只允许owner读写
ls -la .env
# -rw------- 1 root root 1234 Jan 01 12:00 .env
```

---

## 部署步骤

### 完整部署流程

```bash
# 1. 登录VPS
ssh root@your-server-ip

# 2. 创建项目目录
mkdir -p /opt/trading-bot
cd /opt/trading-bot

# 3. 上传代码（方式1: Git）
git clone <你的私有仓库> .

# 或 方式2: SCP上传
# 在本地执行:
# scp -r ./ds/* root@your-server-ip:/opt/trading-bot/

# 4. 配置环境变量
cp .env.example .env
nano .env  # 填写真实API密钥

# 5. 创建必要目录
mkdir -p logs data

# 6. 构建镜像
docker-compose build

# 7. 启动服务
docker-compose up -d

# 8. 检查状态
docker-compose ps
docker-compose logs -f

# 9. 测试访问
curl http://localhost:8888/api/status
```

### 验证部署
```bash
# 检查容器运行状态
docker ps | grep trading-bot

# 查看实时日志
docker logs -f ai-trading-bot

# 检查健康状态
docker inspect --format='{{.State.Health.Status}}' ai-trading-bot
```

---

## 运维管理

### 常用命令

```bash
# 启动服务
docker-compose up -d

# 停止服务
docker-compose down

# 重启服务
docker-compose restart

# 查看日志
docker-compose logs -f

# 查看最近100行日志
docker-compose logs --tail=100

# 进入容器
docker exec -it ai-trading-bot bash

# 更新代码并重启
git pull
docker-compose down
docker-compose build
docker-compose up -d
```

### 数据备份

```bash
# 备份环境变量和数据
tar -czf backup-$(date +%Y%m%d).tar.gz .env logs/ data/

# 定期备份脚本
cat > /opt/backup.sh << 'EOF'
#!/bin/bash
cd /opt/trading-bot
tar -czf /opt/backups/trading-bot-$(date +%Y%m%d-%H%M%S).tar.gz .env logs/ data/
# 保留最近7天的备份
find /opt/backups -name "trading-bot-*.tar.gz" -mtime +7 -delete
EOF

chmod +x /opt/backup.sh

# 添加到定时任务（每天凌晨2点备份）
crontab -e
# 添加: 0 2 * * * /opt/backup.sh
```

### 日志管理

```bash
# 查看Docker日志
docker-compose logs --tail=100 -f

# 清理旧日志（Docker会自动管理，见docker-compose.yml）
docker-compose down
docker system prune -af --volumes

# 手动清理应用日志
rm -rf logs/*
```

### 资源监控

```bash
# 查看容器资源使用
docker stats ai-trading-bot

# 查看系统资源
htop
free -h
df -h
```

---

## 监控告警

### 1. 健康检查

Docker内置健康检查（已配置在docker-compose.yml）
```bash
# 查看健康状态
docker inspect --format='{{json .State.Health}}' ai-trading-bot | jq
```

### 2. 系统监控（可选）

#### 安装Prometheus + Grafana
```bash
# 创建监控stack
mkdir -p /opt/monitoring
cd /opt/monitoring

# docker-compose.monitoring.yml
cat > docker-compose.yml << 'EOF'
version: '3.8'
services:
  prometheus:
    image: prom/prometheus
    volumes:
      - ./prometheus.yml:/etc/prometheus/prometheus.yml
      - prometheus-data:/prometheus
    ports:
      - "9090:9090"

  grafana:
    image: grafana/grafana
    ports:
      - "3000:3000"
    volumes:
      - grafana-data:/var/lib/grafana

volumes:
  prometheus-data:
  grafana-data:
EOF

docker-compose up -d
```

### 3. 告警通知

#### Telegram Bot通知（推荐）
```python
# 在deepseek.py中添加
import requests

TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

def send_telegram_alert(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    requests.post(url, json={'chat_id': TELEGRAM_CHAT_ID, 'text': message})

# 在交易执行处添加
send_telegram_alert(f"🤖 交易提醒：{symbol} {action} {amount}张")
```

---

## 故障排查

### 常见问题

#### 1. 容器无法启动
```bash
# 查看详细日志
docker-compose logs

# 检查端口占用
sudo netstat -tulpn | grep 8888

# 强制重建
docker-compose down -v
docker-compose build --no-cache
docker-compose up -d
```

#### 2. API连接失败
```bash
# 检查网络连接
docker exec -it ai-trading-bot ping api.okx.com

# 检查环境变量
docker exec -it ai-trading-bot env | grep OKX

# 测试API连接
docker exec -it ai-trading-bot python -c "
import ccxt
exchange = ccxt.okx({'apiKey': 'xxx', 'secret': 'xxx', 'password': 'xxx'})
print(exchange.fetch_balance())
"
```

#### 3. 内存不足
```bash
# 查看内存使用
free -h

# 增加swap（如果内存<2G）
sudo fallocate -l 2G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
```

#### 4. 磁盘空间不足
```bash
# 清理Docker
docker system prune -af --volumes

# 清理日志
journalctl --vacuum-time=7d

# 查看目录占用
du -sh /*
```

### 日志调试

```bash
# 开启详细日志
docker-compose down
docker-compose up  # 不使用-d，前台运行查看日志

# Python调试模式
# 在web_ui.py中设置
app.run(debug=True)
```

---

## 性能优化

### 1. 资源限制优化
```yaml
# 在docker-compose.yml中调整
deploy:
  resources:
    limits:
      cpus: '2.0'      # 增加CPU
      memory: 1024M    # 增加内存
```

### 2. 数据库优化（如需持久化）
```bash
# 使用Redis缓存（可选）
docker run -d --name redis -p 6379:6379 redis:alpine
```

---

## 安全检查清单

- [ ] API密钥已正确配置
- [ ] API权限已限制（禁用提现）
- [ ] IP白名单已设置
- [ ] 防火墙已配置
- [ ] .env文件权限设置为600
- [ ] SSL证书已配置（如使用域名）
- [ ] 定期备份已设置
- [ ] 监控告警已配置
- [ ] 交易金额限制已设置

---

## 更新升级

```bash
# 拉取最新代码
cd /opt/trading-bot
git pull

# 重建并重启
docker-compose down
docker-compose build
docker-compose up -d

# 验证
docker-compose logs -f
```

---

## 完全卸载

```bash
# 停止并删除容器
cd /opt/trading-bot
docker-compose down -v

# 删除镜像
docker rmi ai-trading-bot_trading-bot

# 删除项目文件
cd /opt
rm -rf trading-bot

# 清理Docker（可选）
docker system prune -af --volumes
```

---

## 技术支持

- **问题反馈**: [GitHub Issues](你的仓库地址/issues)
- **文档**: [README.md](./README.md)
- **社区**: [Discord/Telegram](如果有)

---

## 许可证

本项目仅供学习使用，交易有风险，投资需谨慎！

**免责声明**：使用本软件进行交易造成的任何损失，开发者不承担责任。
