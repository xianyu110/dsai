# 使用 Ubuntu 基础镜像避免 Debian GPG 问题
FROM ubuntu:22.04

# 设置工作目录
WORKDIR /app

# 设置环境变量
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    TZ=Asia/Shanghai \
    DEBIAN_FRONTEND=noninteractive

# 安装 Python 和系统依赖
RUN rm -f /etc/apt/apt.conf.d/docker-clean && \
    echo 'APT::Update::Post-Invoke-Success { "true"; };' > /etc/apt/apt.conf.d/99no-post-invoke && \
    echo 'Acquire::AllowInsecureRepositories "true";' > /etc/apt/apt.conf.d/99allow-insecure && \
    echo 'APT::Get::AllowUnauthenticated "true";' >> /etc/apt/apt.conf.d/99allow-insecure && \
    chmod 644 /etc/apt/trusted.gpg.d/*.gpg 2>/dev/null || true && \
    sed -i '/backports/d' /etc/apt/sources.list && \
    apt-get update || apt-get update --allow-insecure-repositories && \
    apt-get install -y --no-install-recommends --allow-unauthenticated \
    python3.9 \
    python3-pip \
    python3.9-dev \
    gcc \
    g++ \
    curl \
    tzdata \
    && ln -sf /usr/bin/python3.9 /usr/bin/python \
    && ln -sf /usr/bin/python3.9 /usr/bin/python3 \
    && ln -sf /usr/bin/pip3 /usr/bin/pip \
    && rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

# 复制依赖文件
COPY requirements.txt .

# 安装Python依赖
RUN pip install --no-cache-dir -r requirements.txt

# 复制项目文件
COPY . .

# 创建非root用户运行应用（安全最佳实践）
RUN useradd -m -u 1000 trader && \
    chown -R trader:trader /app

USER trader

# 暴露端口
EXPOSE 8888

# 健康检查
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8888/api/status || exit 1

# 启动应用
CMD ["python", "web_ui.py"]
