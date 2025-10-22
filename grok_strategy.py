# -*- coding: utf-8 -*-
"""
Grok AI 交易策略 - Simulated Trading
基于 Grok AI 的市场分析和交易决策
模拟盘模式，安全测试
"""
import os
import sys
import time
import json
import ccxt
import pandas as pd
from datetime import datetime
from dotenv import load_dotenv
from openai import OpenAI

# 设置控制台输出编码为UTF-8
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

load_dotenv()

# Grok API 配置
GROK_API_BASE = os.getenv('RELAY_API_BASE_URL', 'https://apipro.maynor1024.live/v1')
GROK_API_KEY = os.getenv('RELAY_API_KEY')

grok_client = OpenAI(
    api_key=GROK_API_KEY,
    base_url=GROK_API_BASE
)

# 交易所配置（仅用于获取市场数据）
EXCHANGE_TYPE = os.getenv('EXCHANGE_TYPE', 'okx').lower()
proxies = {}
if os.getenv('HTTP_PROXY'):
    proxies = {
        'http': os.getenv('HTTP_PROXY'),
        'https': os.getenv('HTTPS_PROXY', os.getenv('HTTP_PROXY')),
    }

if EXCHANGE_TYPE == 'okx':
    exchange = ccxt.okx({
        'options': {'defaultType': 'swap'},
        'apiKey': os.getenv('OKX_API_KEY'),
        'secret': os.getenv('OKX_SECRET'),
        'password': os.getenv('OKX_PASSWORD'),
        'proxies': proxies,
        'enableRateLimit': True,
    })
else:
    exchange = ccxt.binance({
        'options': {'defaultType': 'future'},
        'apiKey': os.getenv('BINANCE_API_KEY'),
        'secret': os.getenv('BINANCE_SECRET'),
        'proxies': proxies,
        'enableRateLimit': True,
    })

# Grok 策略配置
GROK_CONFIG = {
    'symbols': ['BTC/USDT', 'ETH/USDT', 'SOL/USDT', 'DOGE/USDT', 'XRP/USDT', 'BNB/USDT'],
    'amount_usd': 200,  # 每次交易金额
    'leverage': 10,     # 杠杆倍数
    'stop_loss_pct': 0.05,  # 止损 5%
    'take_profit_pct': 0.10,  # 止盈 10%
    'test_mode': True,  # 🧪 模拟盘模式（安全测试）
    'auto_trade': True,  # 自动交易
    'initial_balance': 10000,  # 模拟初始资金 10000 USDT
}

# 全局持仓记录
positions = {}
last_signals = {}  # 记录最后信号
simulated_balance = GROK_CONFIG['initial_balance']  # 模拟账户余额
trade_history = []  # 交易历史记录


def get_grok_trading_signal(symbol):
    """获取 Grok AI 的交易信号"""
    try:
        # 获取市场数据
        ticker = exchange.fetch_ticker(symbol)
        current_price = ticker['last']

        # 获取最近的K线数据
        ohlcv = exchange.fetch_ohlcv(symbol, '1h', limit=24)
        df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')

        # 计算技术指标
        df['sma_7'] = df['close'].rolling(window=7).mean()
        df['sma_25'] = df['close'].rolling(window=25).mean()
        price_change_24h = ((current_price - df['close'].iloc[0]) / df['close'].iloc[0]) * 100

        # 构建给 Grok 的提示词
        market_summary = f"""
你是一个专业的加密货币交易员，请分析以下市场数据并给出交易建议。

市场数据 ({symbol}):
- 当前价格: ${current_price:.2f}
- 24小时涨跌: {price_change_24h:+.2f}%
- 24小时最高: ${ticker['high']:.2f}
- 24小时最低: ${ticker['low']:.2f}
- 7周期均线: ${df['sma_7'].iloc[-1]:.2f}
- 25周期均线: ${df['sma_25'].iloc[-1]:.2f}
- 成交量: {ticker['quoteVolume']:.0f} USDT

趋势分析:
- 价格{'高于' if current_price > df['sma_7'].iloc[-1] else '低于'}短期均线
- 价格{'高于' if current_price > df['sma_25'].iloc[-1] else '低于'}长期均线
- 短期均线{'高于' if df['sma_7'].iloc[-1] > df['sma_25'].iloc[-1] else '低于'}长期均线

请基于以上数据，给出 LONG（做多）、SHORT（做空）或 HOLD（观望）的建议。
        """

        response = grok_client.chat.completions.create(
            model='grok-2-1212',  # 使用 Grok 2 模型
            messages=[
                {"role": "system", "content": "你是一个专业的加密货币交易AI，精通技术分析和市场趋势判断。请只回复 JSON 格式: {\"action\": \"LONG/SHORT/HOLD\", \"confidence\": 0.8, \"reason\": \"原因\"}"},
                {"role": "user", "content": market_summary}
            ],
            temperature=0.7,
            max_tokens=500
        )

        result = response.choices[0].message.content.strip()

        # 尝试解析 JSON
        try:
            signal = json.loads(result)
            return signal
        except:
            # 如果无法解析 JSON，尝试从文本中提取
            if 'LONG' in result.upper():
                return {"action": "LONG", "confidence": 0.7, "reason": result}
            elif 'SHORT' in result.upper():
                return {"action": "SHORT", "confidence": 0.7, "reason": result}
            else:
                return {"action": "HOLD", "confidence": 0.5, "reason": result}

    except Exception as e:
        print(f"❌ 获取 Grok 信号失败: {e}")
        return {"action": "HOLD", "confidence": 0, "reason": str(e)}


def execute_trade(symbol, action):
    """执行交易（模拟盘）"""
    global simulated_balance

    try:
        if action == 'HOLD':
            print(f"⏸️  {symbol}: 观望，不交易")
            return

        # 获取当前价格
        ticker = exchange.fetch_ticker(symbol)
        current_price = ticker['last']

        # 计算交易数量
        amount = GROK_CONFIG['amount_usd'] / current_price

        # 平掉现有持仓（如果有）
        if symbol in positions:
            close_position(symbol)

        # 模拟盘开仓
        print(f"🧪 [模拟盘] {symbol} {action} 开仓")
        print(f"   价格: ${current_price:.2f}")
        print(f"   数量: {amount:.4f}")
        print(f"   保证金: ${GROK_CONFIG['amount_usd']} (杠杆{GROK_CONFIG['leverage']}x)")
        print(f"   模拟余额: ${simulated_balance:.2f}")

        # 扣除保证金
        simulated_balance -= GROK_CONFIG['amount_usd']

        # 记录持仓
        positions[symbol] = {
            'side': action,
            'entry_price': current_price,
            'amount': amount,
            'margin': GROK_CONFIG['amount_usd'],
            'timestamp': datetime.now().isoformat(),
            'stop_loss': current_price * (1 - GROK_CONFIG['stop_loss_pct']) if action == 'LONG' else current_price * (1 + GROK_CONFIG['stop_loss_pct']),
            'take_profit': current_price * (1 + GROK_CONFIG['take_profit_pct']) if action == 'LONG' else current_price * (1 - GROK_CONFIG['take_profit_pct']),
        }

        # 记录交易历史
        trade_history.append({
            'timestamp': datetime.now().isoformat(),
            'symbol': symbol,
            'action': 'OPEN',
            'side': action,
            'price': current_price,
            'amount': amount,
            'margin': GROK_CONFIG['amount_usd']
        })

    except Exception as e:
        print(f"❌ 交易执行失败: {e}")


def close_position(symbol):
    """平仓（模拟盘）"""
    global simulated_balance

    try:
        if symbol not in positions:
            return

        pos = positions[symbol]
        ticker = exchange.fetch_ticker(symbol)
        current_price = ticker['last']

        # 计算盈亏
        if pos['side'] == 'LONG':
            price_change_pct = (current_price - pos['entry_price']) / pos['entry_price']
        else:
            price_change_pct = (pos['entry_price'] - current_price) / pos['entry_price']

        # 考虑杠杆的盈亏
        pnl_pct = price_change_pct * GROK_CONFIG['leverage'] * 100
        pnl_amount = pos['margin'] * price_change_pct * GROK_CONFIG['leverage']

        # 归还保证金和盈亏
        simulated_balance += pos['margin'] + pnl_amount

        print(f"🧪 [模拟盘] {symbol} 平仓")
        print(f"   开仓价: ${pos['entry_price']:.2f} -> 平仓价: ${current_price:.2f}")
        print(f"   盈亏: {pnl_pct:+.2f}% (${pnl_amount:+.2f})")
        print(f"   模拟余额: ${simulated_balance:.2f}")

        # 记录交易历史
        trade_history.append({
            'timestamp': datetime.now().isoformat(),
            'symbol': symbol,
            'action': 'CLOSE',
            'side': pos['side'],
            'entry_price': pos['entry_price'],
            'exit_price': current_price,
            'pnl_pct': pnl_pct,
            'pnl_amount': pnl_amount,
            'balance': simulated_balance
        })

        # 删除持仓记录
        del positions[symbol]

    except Exception as e:
        print(f"❌ 平仓失败: {e}")


def check_stop_loss_take_profit():
    """检查止损止盈"""
    for symbol, pos in list(positions.items()):
        try:
            ticker = exchange.fetch_ticker(symbol)
            current_price = ticker['last']

            # 检查止损
            if pos['side'] == 'LONG' and current_price <= pos['stop_loss']:
                print(f"🛑 {symbol} 触发止损: ${current_price:.2f} <= ${pos['stop_loss']:.2f}")
                close_position(symbol)
            elif pos['side'] == 'SHORT' and current_price >= pos['stop_loss']:
                print(f"🛑 {symbol} 触发止损: ${current_price:.2f} >= ${pos['stop_loss']:.2f}")
                close_position(symbol)

            # 检查止盈
            elif pos['side'] == 'LONG' and current_price >= pos['take_profit']:
                print(f"🎯 {symbol} 触发止盈: ${current_price:.2f} >= ${pos['take_profit']:.2f}")
                close_position(symbol)
            elif pos['side'] == 'SHORT' and current_price <= pos['take_profit']:
                print(f"🎯 {symbol} 触发止盈: ${current_price:.2f} <= ${pos['take_profit']:.2f}")
                close_position(symbol)

        except Exception as e:
            print(f"❌ 检查止损止盈失败 ({symbol}): {e}")


def run_grok_strategy():
    """运行 Grok AI 策略"""
    global simulated_balance

    print("=" * 60)
    print("🤖 Grok AI 交易策略 [模拟盘]")
    print(f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"💰 模拟余额: ${simulated_balance:.2f} USDT")
    print(f"📊 总交易次数: {len(trade_history)}")
    print("=" * 60)

    # 检查止损止盈
    check_stop_loss_take_profit()

    # 遍历所有交易对
    for symbol in GROK_CONFIG['symbols']:
        print(f"\n📊 分析 {symbol}...")

        # 获取 Grok 的信号
        grok_signal = get_grok_trading_signal(symbol)
        print(f"   Grok 信号: {grok_signal['action']} (置信度: {grok_signal['confidence']:.2f})")
        print(f"   理由: {grok_signal['reason'][:100]}...")

        # 检查信号是否变化
        if symbol in last_signals:
            if last_signals[symbol] == grok_signal['action']:
                print(f"   ⏭️  信号未变化，跳过")
                continue

        # 记录信号
        last_signals[symbol] = grok_signal['action']

        # 执行交易
        if GROK_CONFIG['auto_trade'] and grok_signal['confidence'] >= 0.6:
            execute_trade(symbol, grok_signal['action'])
        else:
            print(f"   ⚠️  置信度不足或未启用自动交易，跳过")

        time.sleep(2)  # 避免API限流

    # 打印模拟盘统计
    print(f"\n" + "=" * 60)
    print(f"📊 模拟盘统计")
    print(f"💰 当前余额: ${simulated_balance:.2f} USDT")
    print(f"📈 总盈亏: ${simulated_balance - GROK_CONFIG['initial_balance']:+.2f} ({(simulated_balance / GROK_CONFIG['initial_balance'] - 1) * 100:+.2f}%)")
    print(f"📦 当前持仓: {len(positions)}")

    # 打印当前持仓详情
    if positions:
        print(f"\n持仓详情:")
        total_unrealized_pnl = 0
        for symbol, pos in positions.items():
            ticker = exchange.fetch_ticker(symbol)
            current_price = ticker['last']
            if pos['side'] == 'LONG':
                price_change = (current_price - pos['entry_price']) / pos['entry_price']
            else:
                price_change = (pos['entry_price'] - current_price) / pos['entry_price']

            unrealized_pnl = pos['margin'] * price_change * GROK_CONFIG['leverage']
            total_unrealized_pnl += unrealized_pnl

            print(f"   {symbol}: {pos['side']} @ ${pos['entry_price']:.2f} -> ${current_price:.2f}")
            print(f"      未实现盈亏: ${unrealized_pnl:+.2f} ({price_change * GROK_CONFIG['leverage'] * 100:+.2f}%)")

        print(f"\n💵 总未实现盈亏: ${total_unrealized_pnl:+.2f}")
        print(f"💼 账户总价值: ${simulated_balance + sum(pos['margin'] for pos in positions.values()) + total_unrealized_pnl:.2f}")

    print("\n" + "=" * 60)


if __name__ == "__main__":
    print("""
    ╔══════════════════════════════════════════════════════════╗
    ║         Grok AI 交易策略 [模拟盘] Simulated Trading    ║
    ║                                                          ║
    ║  策略特点: 基于 Grok AI 的市场分析和技术指标           ║
    ║  分析维度: 价格趋势、均线系统、成交量                   ║
    ║  决策模型: Grok-2-1212 AI 模型                          ║
    ║                                                          ║
    ║  🧪 模拟盘模式: 安全测试，不会真实交易                  ║
    ║  💰 初始资金: $10,000 USDT                              ║
    ║  📊 杠杆倍数: 10x                                       ║
    ╚══════════════════════════════════════════════════════════╝
    """)

    try:
        while True:
            run_grok_strategy()
            print(f"\n⏰ 等待 5 分钟后再次运行...")
            time.sleep(300)  # 每5分钟运行一次
    except KeyboardInterrupt:
        print("\n\n👋 策略已停止")
        print(f"\n📊 最终统计:")
        print(f"   初始资金: ${GROK_CONFIG['initial_balance']:.2f}")
        print(f"   最终余额: ${simulated_balance:.2f}")
        print(f"   总盈亏: ${simulated_balance - GROK_CONFIG['initial_balance']:+.2f} ({(simulated_balance / GROK_CONFIG['initial_balance'] - 1) * 100:+.2f}%)")
        print(f"   交易次数: {len(trade_history)}")
