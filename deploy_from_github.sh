#!/bin/bash

#############################################
# AI 交易机器人 - 一键部署脚本
# 从 GitHub 拉取并使用 Docker 部署
#############################################

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 配置
REPO_URL="https://github.com/xianyu110/dsai.git"
PROJECT_DIR="$HOME/trading-bot"
DOCKER_PORT="8888"

# 打印带颜色的消息
print_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

print_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

# 检查命令是否存在
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# 检查并安装 Docker
install_docker() {
    print_info "检查 Docker 安装状态..."

    if command_exists docker; then
        print_success "Docker 已安装: $(docker --version)"
        return 0
    fi

    print_warning "Docker 未安装，开始安装..."

    # 检测操作系统
    if [[ "$OSTYPE" == "darwin"* ]]; then
        # macOS
        print_info "检测到 macOS 系统"
        if command_exists brew; then
            print_info "使用 Homebrew 安装 Docker Desktop..."
            brew install --cask docker
        else
            print_error "未找到 Homebrew，请手动安装 Docker Desktop:"
            print_error "https://www.docker.com/products/docker-desktop"
            exit 1
        fi
    elif [[ -f /etc/debian_version ]]; then
        # Debian/Ubuntu
        print_info "检测到 Debian/Ubuntu 系统"
        curl -fsSL https://get.docker.com | sh
        sudo usermod -aG docker $USER
        print_warning "请重新登录以使 Docker 组权限生效"
    elif [[ -f /etc/redhat-release ]]; then
        # RHEL/CentOS
        print_info "检测到 RHEL/CentOS 系统"
        sudo yum install -y yum-utils
        sudo yum-config-manager --add-repo https://download.docker.com/linux/centos/docker-ce.repo
        sudo yum install -y docker-ce docker-ce-cli containerd.io
        sudo systemctl start docker
        sudo systemctl enable docker
        sudo usermod -aG docker $USER
        print_warning "请重新登录以使 Docker 组权限生效"
    else
        print_error "不支持的操作系统，请手动安装 Docker"
        exit 1
    fi

    print_success "Docker 安装完成"
}

# 检查并安装 Git
install_git() {
    print_info "检查 Git 安装状态..."

    if command_exists git; then
        print_success "Git 已安装: $(git --version)"
        return 0
    fi

    print_warning "Git 未安装，开始安装..."

    if [[ "$OSTYPE" == "darwin"* ]]; then
        brew install git
    elif [[ -f /etc/debian_version ]]; then
        sudo apt-get update
        sudo apt-get install -y git
    elif [[ -f /etc/redhat-release ]]; then
        sudo yum install -y git
    else
        print_error "不支持的操作系统，请手动安装 Git"
        exit 1
    fi

    print_success "Git 安装完成"
}

# 克隆或更新项目
clone_or_update_project() {
    if [ -d "$PROJECT_DIR" ]; then
        print_info "项目目录已存在，拉取最新代码..."
        cd "$PROJECT_DIR"
        git pull origin main
        print_success "代码更新完成"
    else
        print_info "克隆项目仓库..."
        git clone "$REPO_URL" "$PROJECT_DIR"
        cd "$PROJECT_DIR"
        print_success "项目克隆完成"
    fi
}

# 配置环境变量
configure_env() {
    print_info "配置环境变量..."

    if [ -f ".env" ]; then
        print_warning ".env 文件已存在，是否覆盖？[y/N]"
        read -r response
        if [[ ! "$response" =~ ^[Yy]$ ]]; then
            print_info "保留现有配置"
            return 0
        fi
    fi

    cp .env.example .env

    print_info "请配置以下必填项（直接回车跳过）："

    # AI 模型配置
    echo ""
    print_info "=== AI 模型配置 ==="
    read -p "DeepSeek API Key: " deepseek_key
    if [ -n "$deepseek_key" ]; then
        sed -i.bak "s/DEEPSEEK_API_KEY=.*/DEEPSEEK_API_KEY=$deepseek_key/" .env
    fi

    # 交易所配置
    echo ""
    print_info "=== 交易所配置 ==="
    read -p "OKX API Key: " okx_key
    if [ -n "$okx_key" ]; then
        sed -i.bak "s/OKX_API_KEY=.*/OKX_API_KEY=$okx_key/" .env
    fi

    read -p "OKX Secret: " okx_secret
    if [ -n "$okx_secret" ]; then
        sed -i.bak "s/OKX_SECRET=.*/OKX_SECRET=$okx_secret/" .env
    fi

    read -p "OKX Password: " okx_password
    if [ -n "$okx_password" ]; then
        sed -i.bak "s/OKX_PASSWORD=.*/OKX_PASSWORD=$okx_password/" .env
    fi

    # 代理配置
    echo ""
    print_info "=== 代理配置（可选）==="
    read -p "HTTP Proxy (例如: http://127.0.0.1:7890): " http_proxy
    if [ -n "$http_proxy" ]; then
        sed -i.bak "s|HTTP_PROXY=.*|HTTP_PROXY=$http_proxy|" .env
        sed -i.bak "s|HTTPS_PROXY=.*|HTTPS_PROXY=$http_proxy|" .env
    fi

    rm -f .env.bak

    print_success "环境变量配置完成"
}

# 启动 Docker 容器
start_docker() {
    print_info "启动 Docker 容器..."

    # 检查端口占用
    if lsof -Pi :$DOCKER_PORT -sTCP:LISTEN -t >/dev/null 2>&1; then
        print_error "端口 $DOCKER_PORT 已被占用，请修改 docker-compose.yml 中的端口配置"
        exit 1
    fi

    # 启动容器
    docker-compose up -d --build

    print_success "容器启动成功"
}

# 等待服务就绪
wait_for_service() {
    print_info "等待服务启动..."

    max_attempts=30
    attempt=0

    while [ $attempt -lt $max_attempts ]; do
        if curl -s http://localhost:$DOCKER_PORT/api/status >/dev/null 2>&1; then
            print_success "服务已就绪"
            return 0
        fi

        attempt=$((attempt + 1))
        echo -n "."
        sleep 2
    done

    echo ""
    print_warning "服务启动超时，请检查日志: docker-compose logs -f"
    return 1
}

# 显示部署信息
show_info() {
    echo ""
    echo "=========================================="
    print_success "🎉 部署完成！"
    echo "=========================================="
    echo ""
    echo "📁 项目目录: $PROJECT_DIR"
    echo "🌐 访问地址: http://localhost:$DOCKER_PORT"
    echo ""
    echo "常用命令:"
    echo "  查看日志: cd $PROJECT_DIR && docker-compose logs -f"
    echo "  停止服务: cd $PROJECT_DIR && docker-compose down"
    echo "  重启服务: cd $PROJECT_DIR && docker-compose restart"
    echo "  更新部署: cd $PROJECT_DIR && git pull && docker-compose up -d --build"
    echo ""
    echo "📖 完整文档: $PROJECT_DIR/DOCKER_DEPLOY.md"
    echo ""
    print_warning "⚠️  首次使用请确保已在 .env 文件中配置好 API 密钥"
    echo ""
}

# 主函数
main() {
    echo ""
    echo "=========================================="
    echo "  AI 交易机器人 - 一键部署脚本"
    echo "=========================================="
    echo ""

    # 安装依赖
    install_git
    install_docker

    # 克隆项目
    clone_or_update_project

    # 配置环境
    configure_env

    # 启动服务
    start_docker

    # 等待服务
    wait_for_service

    # 显示信息
    show_info

    # 询问是否打开浏览器
    if [[ "$OSTYPE" == "darwin"* ]]; then
        print_info "是否打开浏览器访问？[Y/n]"
        read -r response
        if [[ ! "$response" =~ ^[Nn]$ ]]; then
            open "http://localhost:$DOCKER_PORT"
        fi
    fi
}

# 错误处理
trap 'print_error "部署过程中发生错误，请检查上述输出"; exit 1' ERR

# 运行主函数
main
