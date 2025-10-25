#!/bin/bash

# AI交易系统启动脚本
# 解决Docker部署后自动交易没有在后台自动运行的问题

set -e

echo "🚀 启动AI交易系统..."
echo "📅 时间: $(date '+%Y-%m-%d %H:%M:%S')"
echo "🔧 环境: Docker容器"
echo "=================================="

# 等待网络就绪
echo "⏳ 等待网络连接..."
sleep 2

# 检查必要的Python模块
echo "🔍 检查依赖模块..."
python -c "import ccxt, pandas, numpy, schedule; print('✅ 依赖检查通过')" || {
    echo "❌ 依赖模块缺失，尝试重新安装..."
    pip install -r requirements.txt --quiet
}

# 启动Web界面（后台运行）
echo "🌐 启动Web界面..."
python web_ui.py &
WEB_PID=$!
echo "✅ Web界面已启动 (PID: $WEB_PID)"

# 等待Web界面完全启动
echo "⏳ 等待Web界面就绪..."
sleep 10

# 检查Web界面是否正常运行
if curl -f http://localhost:8888/api/status > /dev/null 2>&1; then
    echo "✅ Web界面运行正常"
else
    echo "⚠️  Web界面可能还在启动中，继续启动策略..."
fi

# 启动DeepSeek策略（标记为auto_start的策略）
echo "🤖 启动DeepSeek自动交易策略..."
if [ -f "deepseek.py" ]; then
    python deepseek.py &
    DEEPSEEK_PID=$!
    echo "✅ DeepSeek策略已启动 (PID: $DEEPSEEK_PID)"
else
    echo "❌ DeepSeek策略文件不存在"
fi

# 启动其他可用策略（如果存在）
# 检查并启动QwenMax策略
if [ -f "qwenmax_strategy.py" ]; then
    echo "🤖 启动QwenMax策略..."
    python qwenmax_strategy.py &
    QWENMAX_PID=$!
    echo "✅ QwenMax策略已启动 (PID: $QWENMAX_PID)"
fi

# 检查并启动Grok策略
if [ -f "grok_strategy.py" ]; then
    echo "🤖 启动Grok策略..."
    python grok_strategy.py &
    GROK_PID=$!
    echo "✅ Grok策略已启动 (PID: $GROK_PID)"
fi

# 检查并启动反向GPT-5策略
if [ -f "reverse_gpt5.py" ]; then
    echo "🤖 启动反向GPT-5策略..."
    python reverse_gpt5.py &
    REVERSE_GPT5_PID=$!
    echo "✅ 反向GPT-5策略已启动 (PID: $REVERSE_GPT5_PID)"
fi

echo "=================================="
echo "✅ AI交易系统启动完成！"
echo "📡 Web界面访问: http://localhost:8888"
echo "📊 系统状态监控: Web界面 -> 策略管理页面"
echo "=================================="

# 创建进程状态文件
echo "WEB_PID=$WEB_PID" > /tmp/trading_pids.conf
echo "DEEPSEEK_PID=$DEEPSEEK_PID" >> /tmp/trading_pids.conf
[ ! -z "$QWENMAX_PID" ] && echo "QWENMAX_PID=$QWENMAX_PID" >> /tmp/trading_pids.conf
[ ! -z "$GROK_PID" ] && echo "GROK_PID=$GROK_PID" >> /tmp/trading_pids.conf
[ ! -z "$REVERSE_GPT5_PID" ] && echo "REVERSE_GPT5_PID=$REVERSE_GPT5_PID" >> /tmp/trading_pids.conf

# 监控进程状态，确保服务持续运行
echo "🔍 开始监控服务状态..."
while true; do
    # 检查Web界面
    if ! kill -0 $WEB_PID 2>/dev/null; then
        echo "❌ Web界面进程异常退出，重启中..."
        python web_ui.py &
        WEB_PID=$!
        echo "WEB_PID=$WEB_PID" > /tmp/trading_pids.conf
    fi

    # 检查DeepSeek策略
    if ! kill -0 $DEEPSEEK_PID 2>/dev/null; then
        echo "❌ DeepSeek策略进程异常退出，重启中..."
        python deepseek.py &
        DEEPSEEK_PID=$!
        echo "WEB_PID=$WEB_PID" > /tmp/trading_pids.conf
        echo "DEEPSEEK_PID=$DEEPSEEK_PID" >> /tmp/trading_pids.conf
    fi

    # 每60秒检查一次
    sleep 60
done
