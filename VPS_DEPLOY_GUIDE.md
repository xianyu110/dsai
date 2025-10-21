# VPS部署指南

## 方法一：自动部署脚本（推荐）

### 1. 在本地执行一键部署

```bash
cd /Users/chinamanor/Downloads/cursor编程/ds
./deploy_to_vps.sh 45.207.201.101
```

脚本会自动完成：
- ✅ 检查VPS环境（安装Docker/Docker Compose）
- ✅ 创建部署目录 `/opt/ai_tradeauto`
- ✅ 上传所有项目文件
- ✅ 构建并启动Docker容器
- ✅ 进行健康检查

---

## 方法二：手动部署步骤

### 1. 连接到VPS

```bash
ssh root@45.207.201.101
```

### 2. 安装Docker（如果未安装）

```bash
# 安装Docker
curl -fsSL https://get.docker.com | sh

# 启动Docker服务
systemctl start docker
systemctl enable docker

# 验证安装
docker --version
```

### 3. 安装Docker Compose（如果未安装）

```bash
# 下载Docker Compose
curl -L "https://github.com/docker/compose/releases/download/1.29.2/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose

# 添加执行权限
chmod +x /usr/local/bin/docker-compose

# 验证安装
docker-compose --version
```

### 4. 创建部署目录

```bash
mkdir -p /opt/ai_tradeauto
cd /opt/ai_tradeauto
```

### 5. 上传项目文件

在**本地电脑**执行：

```bash
cd /Users/chinamanor/Downloads/cursor编程/ds

# 使用rsync上传
rsync -avz --progress \
    --exclude='__pycache__' \
    --exclude='*.pyc' \
    --exclude='.git' \
    ./ root@45.207.201.101:/opt/ai_tradeauto/
```

或使用SCP：

```bash
scp -r * root@45.207.201.101:/opt/ai_tradeauto/
```

### 6. 在VPS上启动服务

```bash
ssh root@45.207.201.101

cd /opt/ai_tradeauto

# 检查.env文件是否存在并配置正确
cat .env

# 构建镜像
docker-compose build

# 启动容器
docker-compose up -d

# 查看状态
docker-compose ps

# 查看日志
docker-compose logs -f
```

### 7. 验证部署

```bash
# 检查服务状态
curl http://localhost:8888/api/status

# 或从本地访问
curl http://45.207.201.101:8888/api/status
```

---

## 常用管理命令

### 查看日志
```bash
ssh root@45.207.201.101 'cd /opt/ai_tradeauto && docker-compose logs -f'
```

### 重启服务
```bash
ssh root@45.207.201.101 'cd /opt/ai_tradeauto && docker-compose restart'
```

### 停止服务
```bash
ssh root@45.207.201.101 'cd /opt/ai_tradeauto && docker-compose down'
```

### 更新代码
```bash
# 1. 本地上传新代码
rsync -avz --progress --exclude='__pycache__' --exclude='.git' \
    /Users/chinamanor/Downloads/cursor编程/ds/ root@45.207.201.101:/opt/ai_tradeauto/

# 2. 重启容器
ssh root@45.207.201.101 'cd /opt/ai_tradeauto && docker-compose restart'
```

### 查看容器状态
```bash
ssh root@45.207.201.101 'cd /opt/ai_tradeauto && docker-compose ps'
```

### 进入容器
```bash
ssh root@45.207.201.101 'cd /opt/ai_tradeauto && docker-compose exec trading-bot bash'
```

---

## 防火墙配置

如果无法访问8888端口，需要开放防火墙：

```bash
# Ubuntu/Debian (ufw)
ufw allow 8888/tcp
ufw reload

# CentOS/RHEL (firewalld)
firewall-cmd --permanent --add-port=8888/tcp
firewall-cmd --reload

# 或直接使用iptables
iptables -A INPUT -p tcp --dport 8888 -j ACCEPT
```

---

## 访问Web界面

部署成功后，访问：
```
http://45.207.201.101:8888
```

---

## 故障排查

### 1. 容器无法启动
```bash
cd /opt/ai_tradeauto
docker-compose logs
```

### 2. 端口被占用
```bash
# 检查端口占用
netstat -tlnp | grep 8888

# 修改docker-compose.yml中的端口映射
# ports:
#   - "8889:8888"  # 改用8889端口
```

### 3. 内存不足
```bash
# 查看内存使用
free -h

# 增加swap
dd if=/dev/zero of=/swapfile bs=1M count=2048
chmod 600 /swapfile
mkswap /swapfile
swapon /swapfile
```

### 4. .env文件缺失
```bash
cd /opt/ai_tradeauto
cp .env.example .env
nano .env  # 编辑配置
```

---

## 自动重启配置

Docker Compose已配置 `restart: unless-stopped`，服务器重启后会自动启动。

验证：
```bash
# 重启VPS
reboot

# 重启后检查
docker-compose ps
```

---

## 备份数据

```bash
# 备份日志和数据
cd /opt/ai_tradeauto
tar -czf backup-$(date +%Y%m%d).tar.gz logs/ data/ .env

# 下载备份到本地
scp root@45.207.201.101:/opt/ai_tradeauto/backup-*.tar.gz ./
```
