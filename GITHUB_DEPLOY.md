# 从GitHub拉取并部署 - 完整指南

## 📋 目录

- [方法一：一键自动部署（推荐）](#方法一一键自动部署推荐)
- [方法二：手动分步部署](#方法二手动分步部署)
- [方法三：本地打包后上传](#方法三本地打包后上传)
- [常见问题排查](#常见问题排查)

---

## 方法一：一键自动部署（推荐）

### 适用场景
- VPS已安装Git和Docker
- 网络可以访问GitHub
- 想要最快速度部署

### 部署步骤

#### 1. SSH连接到VPS

```bash
ssh root@45.207.201.101
```

#### 2. 运行一键部署脚本

```bash
# 下载并运行部署脚本
curl -fsSL https://raw.githubusercontent.com/xianyu110/dsai/main/deploy.sh -o deploy.sh
chmod +x deploy.sh
./deploy.sh
```

或者手动克隆后部署：

```bash
# 克隆项目
cd /opt
git clone https://github.com/xianyu110/dsai.git ai_tradeauto
cd ai_tradeauto

# 配置环境变量
cp .env.example .env
nano .env  # 填写API密钥

# 一键部署
./deploy.sh
```

#### 3. 访问Web界面

```
http://45.207.201.101:8888
```

---

## 方法二：手动分步部署

### 前置要求

- Ubuntu 16.04+ / Debian 8+ / CentOS 7+
- Root权限或sudo权限
- 至少512MB内存
- 至少1GB磁盘空间

### Step 1: 安装Git

```bash
# Ubuntu/Debian
apt-get update
apt-get install -y git

# CentOS/RHEL
yum install -y git
```

### Step 2: 安装Docker

```bash
# 使用官方安装脚本
curl -fsSL https://get.docker.com | sh

# 启动Docker服务
systemctl start docker
systemctl enable docker

# 验证安装
docker --version
```

### Step 3: 安装Docker Compose

```bash
# 下载Docker Compose
curl -L "https://github.com/docker/compose/releases/download/1.29.2/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose

# 添加执行权限
chmod +x /usr/local/bin/docker-compose

# 验证安装
docker-compose --version
```

### Step 4: 克隆项目

```bash
# 创建部署目录
mkdir -p /opt
cd /opt

# 克隆GitHub仓库
git clone https://github.com/xianyu110/dsai.git ai_tradeauto

# 进入项目目录
cd ai_tradeauto
```

### Step 5: 配置环境变量

```bash
# 复制环境变量模板
cp .env.example .env

# 编辑配置文件
nano .env
```

**必填配置项**：

```bash
# AI模型配置
AI_MODEL=deepseek
USE_RELAY_API=true
RELAY_API_BASE_URL=https://apipro.maynor1024.live/v1
RELAY_API_KEY=你的中转API密钥

# 交易所配置
EXCHANGE_TYPE=okx

# OKX API（必填）
OKX_API_KEY=你的OKX_API_KEY
OKX_SECRET=你的OKX_SECRET
OKX_PASSWORD=你的OKX_PASSWORD

# 代理配置（如果需要）
HTTP_PROXY=
HTTPS_PROXY=
```

**保存并退出**：
- 按 `Ctrl + O` 保存
- 按 `Enter` 确认
- 按 `Ctrl + X` 退出

### Step 6: 选择Dockerfile版本构建

```bash
# 查看可用版本
ls -la Dockerfile*

# 标准版（推荐）
docker-compose build

# 如果构建失败，尝试简化版
./docker-build.sh 2

# 或最小版（适合老系统）
./docker-build.sh 3
```

### Step 7: 启动服务

```bash
# 启动容器（后台运行）
docker-compose up -d

# 查看日志
docker-compose logs -f
```

### Step 8: 验证部署

```bash
# 检查容器状态
docker-compose ps

# 测试API
curl http://localhost:8888/api/status

# 查看实时日志
docker-compose logs -f
```

### Step 9: 配置防火墙

```bash
# Ubuntu/Debian (ufw)
ufw allow 8888/tcp
ufw reload

# CentOS/RHEL (firewalld)
firewall-cmd --permanent --add-port=8888/tcp
firewall-cmd --reload

# 直接使用iptables
iptables -A INPUT -p tcp --dport 8888 -j ACCEPT
service iptables save  # CentOS 6
```

### Step 10: 访问Web界面

浏览器打开：
```
http://你的VPS_IP:8888
```

例如：
```
http://45.207.201.101:8888
```

---

## 方法三：本地打包后上传

### 适用场景
- VPS网络访问GitHub不稳定
- 想要离线部署
- 需要在多台服务器部署

### 在本地执行

#### 1. 克隆项目到本地

```bash
cd ~/Downloads
git clone https://github.com/xianyu110/dsai.git
cd dsai
```

#### 2. 配置.env文件

```bash
cp .env.example .env
nano .env  # 填写配置
```

#### 3. 打包

```bash
./package.sh
```

会生成类似 `ai-trading-bot_20251021_202339.tar.gz` 的文件。

#### 4. 上传到VPS

```bash
scp ai-trading-bot_*.tar.gz root@45.207.201.101:/tmp/
```

### 在VPS上执行

#### 1. SSH到VPS

```bash
ssh root@45.207.201.101
```

#### 2. 解压并部署

```bash
# 进入临时目录
cd /tmp

# 解压
tar -xzf ai-trading-bot_*.tar.gz

# 移动到部署目录
mv ai-trading-bot /opt/ai_tradeauto
cd /opt/ai_tradeauto

# 查看部署说明
cat DEPLOY_README.txt
```

#### 3. 安装Docker（如果未安装）

```bash
# 安装Docker
curl -fsSL https://get.docker.com | sh
systemctl start docker
systemctl enable docker

# 安装Docker Compose
curl -L "https://github.com/docker/compose/releases/download/1.29.2/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
chmod +x /usr/local/bin/docker-compose
```

#### 4. 启动服务

```bash
# 检查配置（如果需要修改）
cat .env

# 构建镜像
docker-compose build

# 启动容器
docker-compose up -d

# 查看日志
docker-compose logs -f
```

---

## 📊 部署后管理

### 常用命令

```bash
# 查看服务状态
cd /opt/ai_tradeauto
docker-compose ps

# 查看实时日志
docker-compose logs -f

# 查看最近100行日志
docker-compose logs --tail=100

# 重启服务
docker-compose restart

# 停止服务
docker-compose down

# 完全停止并删除容器
docker-compose down -v
```

### 更新代码

```bash
cd /opt/ai_tradeauto

# 拉取最新代码
git pull origin main

# 重新构建并启动
docker-compose down
docker-compose build
docker-compose up -d

# 查看日志确认
docker-compose logs -f
```

### 备份数据

```bash
cd /opt/ai_tradeauto

# 备份配置和数据
tar -czf backup-$(date +%Y%m%d).tar.gz .env logs/ data/

# 下载到本地
scp root@45.207.201.101:/opt/ai_tradeauto/backup-*.tar.gz ./
```

### 恢复数据

```bash
# 解压备份
tar -xzf backup-20251021.tar.gz

# 重启服务
docker-compose restart
```

---

## 🔧 常见问题排查

### 问题1: Git克隆失败

**现象**：
```
fatal: unable to access 'https://github.com/...': Failed to connect
```

**解决方案**：

```bash
# 方案A: 使用代理
export http_proxy=http://your_proxy:port
export https_proxy=http://your_proxy:port
git clone https://github.com/xianyu110/dsai.git

# 方案B: 使用SSH方式克隆
git clone git@github.com:xianyu110/dsai.git

# 方案C: 使用镜像站
git clone https://gitee.com/mirrors/dsai.git  # 如果有镜像

# 方案D: 本地打包上传（见方法三）
```

### 问题2: Docker构建失败

**现象**：
```
E: Sub-process returned an error code
ERROR: Service 'trading-bot' failed to build
```

**解决方案**：

```bash
# 方案A: 使用简化版Dockerfile
./docker-build.sh 2

# 方案B: 使用最小版Dockerfile
./docker-build.sh 3

# 方案C: 清理Docker缓存后重试
docker system prune -a
docker-compose build --no-cache

# 方案D: 检查系统版本，升级系统
cat /etc/os-release
apt-get update && apt-get upgrade  # Ubuntu/Debian
```

### 问题3: 端口8888无法访问

**现象**：
浏览器无法打开 `http://VPS_IP:8888`

**解决方案**：

```bash
# 1. 检查容器是否运行
docker-compose ps

# 2. 检查端口是否监听
netstat -tlnp | grep 8888

# 3. 检查防火墙
# Ubuntu/Debian
ufw status
ufw allow 8888/tcp

# CentOS/RHEL
firewall-cmd --list-ports
firewall-cmd --permanent --add-port=8888/tcp
firewall-cmd --reload

# 4. 检查云服务商安全组
# 需要在阿里云/腾讯云/AWS控制台开放8888端口

# 5. 查看容器日志
docker-compose logs
```

### 问题4: 容器启动后立即退出

**现象**：
```
docker-compose ps
# 显示 Exit 1 或 Exit 0
```

**解决方案**：

```bash
# 1. 查看详细日志
docker-compose logs

# 2. 检查.env配置
cat .env
# 确保所有必填项都已配置

# 3. 检查配置文件语法
python3 -c "from dotenv import load_dotenv; load_dotenv()"

# 4. 手动运行容器查看错误
docker run -it --rm --env-file .env ai-trading-bot:latest python web_ui.py
```

### 问题5: 内存不足

**现象**：
```
Cannot allocate memory
```

**解决方案**：

```bash
# 1. 查看内存使用
free -h

# 2. 添加Swap空间
dd if=/dev/zero of=/swapfile bs=1M count=2048
chmod 600 /swapfile
mkswap /swapfile
swapon /swapfile

# 3. 永久生效
echo '/swapfile none swap sw 0 0' >> /etc/fstab

# 4. 验证
free -h
```

### 问题6: API连接失败

**现象**：
日志显示 API 连接超时或认证失败

**解决方案**：

```bash
# 1. 检查API密钥配置
cat .env | grep -E "OKX|RELAY"

# 2. 测试网络连接
curl https://www.okx.com
curl https://apipro.maynor1024.live

# 3. 如果需要代理，配置HTTP_PROXY
nano .env
# 添加：
# HTTP_PROXY=http://proxy_ip:port
# HTTPS_PROXY=http://proxy_ip:port

# 4. 重启容器
docker-compose restart
```

---

## 🔐 安全建议

### 1. 保护.env文件

```bash
# 设置严格权限
chmod 600 .env

# 确保不被Git追踪
echo ".env" >> .gitignore
```

### 2. 使用非Root用户（可选）

```bash
# 创建专用用户
useradd -m -s /bin/bash trader
usermod -aG docker trader

# 修改文件所有权
chown -R trader:trader /opt/ai_tradeauto

# 切换用户
su - trader
cd /opt/ai_tradeauto
docker-compose up -d
```

### 3. 配置SSL证书（可选）

```bash
# 安装Nginx
apt-get install -y nginx certbot python3-certbot-nginx

# 配置反向代理
nano /etc/nginx/sites-available/trading-bot

# 添加配置：
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
ln -s /etc/nginx/sites-available/trading-bot /etc/nginx/sites-enabled/
nginx -t
systemctl restart nginx

# 申请SSL证书
certbot --nginx -d your-domain.com
```

### 4. 定期备份

```bash
# 添加定时任务
crontab -e

# 每天凌晨3点备份
0 3 * * * cd /opt/ai_tradeauto && tar -czf /backup/trading-bot-$(date +\%Y\%m\%d).tar.gz .env logs/ data/
```

---

## 📞 获取帮助

- **GitHub Issues**: https://github.com/xianyu110/dsai/issues
- **查看日志**: `docker-compose logs -f`
- **检查状态**: `docker-compose ps`

---

## 📝 快速命令参考

```bash
# 查看服务状态
docker-compose ps

# 启动服务
docker-compose up -d

# 停止服务
docker-compose down

# 重启服务
docker-compose restart

# 查看日志
docker-compose logs -f

# 更新代码
git pull && docker-compose down && docker-compose build && docker-compose up -d

# 进入容器
docker-compose exec trading-bot bash

# 备份数据
tar -czf backup.tar.gz .env logs/ data/

# 清理Docker
docker system prune -a
```

---

**部署完成后访问**: `http://你的VPS_IP:8888`

**祝部署顺利！** 🚀
