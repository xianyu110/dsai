#!/bin/bash

# AI交易机器人启动脚本
# 一键启动Web界面,支持热重载

echo "🚀 正在启动AI交易机器人..."
echo ""

# 检查Python版本
if ! command -v python3 &> /dev/null; then
    echo "❌ 错误: 未找到python3"
    exit 1
fi

echo "✓ Python版本: $(python3 --version)"

# 检查依赖
echo "✓ 检查依赖包..."
python3 -c "import ccxt, openai, pandas, schedule, dotenv, flask, anthropic" 2>/dev/null
if [ $? -ne 0 ]; then
    echo "⚠️  缺少依赖,正在安装..."
    pip3 install -r requirements.txt
fi

# 检查.env文件
if [ ! -f .env ]; then
    echo "⚠️  未找到.env配置文件"
    echo "📝 请复制.env.example为.env并填入API密钥"
    exit 1
fi

echo "✓ 配置文件已加载"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🌐 Web界面地址: http://localhost:8888"
echo "🔄 热重载已启用 - 修改代码自动重启"
echo "⏹️  按 Ctrl+C 停止服务"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# 启动Web界面
python3 web_ui.py
