# -*- coding: utf-8 -*-
"""
反向跟单策略 - GPT-5 Inverse Trader
基于 GPT-5 的交易决策进行反向操作
GPT-5 做多 -> 我们做空
GPT-5 做空 -> 我们做多
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

# GPT-5 API 配置（用于获取其交易信号）
GPT5_API_BASE = os.getenv('RELAY_API_BASE_URL', 'https://apipro.maynor1024.live/v1')
GPT5_API_KEY = os.getenv('RELAY_API_KEY')

gpt5_client = OpenAI(
    api_key=GPT5_API_KEY,
    base_url=GPT5_API_BASE
)

# 交易所配置
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

# 反向跟单配置
REVERSE_CONFIG = {
    'symbols': ['BTC/USDT', 'ETH/USDT', 'SOL/USDT', 'DOGE/USDT', 'XRP/USDT', 'BNB/USDT'],
    'amount_usd': 200,  # 每次交易金额
    'leverage': 10,     # 杠杆倍数
    'stop_loss_pct': 0.05,  # 止损 5%
    'take_profit_pct': 0.10,  # 止盈 10%
    'test_mode': False,  # 实盘模式
    'auto_trade': True,  # 自动交易
}

# 全局持仓记录
positions = {}
gpt5_last_signals = {}  # 记录 GPT-5 的最后信号


def get_gpt5_trading_signal(symbol):
    """获取 GPT-5 的交易信号"""
    try:
        # 获取市场数据
        ticker = exchange.fetch_ticker(symbol)
        current_price = ticker['last']

        # 获取最近的K线数据
        ohlcv = exchange.fetch_ohlcv(symbol, '1h', limit=24)
        df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')

        # 构建给 GPT-5 的提示词
        market_summary = f"""
当前市场数据 ({symbol}):
当前价格: ${current_price:.2f}
24小时最高: ${ticker['high']:.2f}
24小时最低: ${ticker['low']:.2f}
24小时涨跌幅: {ticker['percentage']:.2f}%
24小时成交量: {ticker['quoteVolume']:.0f} USDT

最近24小时价格走势:
{df[['timestamp', 'close']].tail(12).to_string(index=False)}

请分析市场并给出交易建议。
        """

        response = gpt5_client.chat.completions.create(
            model='gpt-4',  # 使用中转API的GPT-4
            messages=[
                {"role": "system", "content": "你是一个加密货币交易专家。请分析市场数据并给出 LONG（做多）、SHORT（做空）或 HOLD（观望）的建议。只回复 JSON 格式: {\"action\": \"LONG/SHORT/HOLD\", \"confidence\": 0.8, \"reason\": \"原因\"}"},
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
        print(f"❌ 获取 GPT-5 信号失败: {e}")
        return {"action": "HOLD", "confidence": 0, "reason": str(e)}


def reverse_signal(gpt5_signal):
    """反向信号转换"""
    action = gpt5_signal.get('action', 'HOLD').upper()

    if action == 'LONG':
        return 'SHORT'  # GPT-5 做多，我们做空
    elif action == 'SHORT':
        return 'LONG'   # GPT-5 做空，我们做多
    else:
        return 'HOLD'   # GPT-5 观望，我们也观望


def execute_reverse_trade(symbol, reverse_action):
    """执行反向交易"""
    try:
        if reverse_action == 'HOLD':
            print(f"⏸️  {symbol}: 观望，不交易")
            return

        # 获取当前价格
        ticker = exchange.fetch_ticker(symbol)
        current_price = ticker['last']

        # 计算交易数量
        amount = REVERSE_CONFIG['amount_usd'] / current_price

        # 设置杠杆
        try:
            exchange.set_leverage(REVERSE_CONFIG['leverage'], symbol)
        except Exception as e:
            print(f"⚠️  设置杠杆失败 (可能已设置): {e}")

        # 平掉现有持仓（如果有）
        if symbol in positions:
            close_position(symbol)

        # 开仓
        side = 'sell' if reverse_action == 'SHORT' else 'buy'

        if not REVERSE_CONFIG['test_mode']:
            order = exchange.create_market_order(
                symbol=symbol,
                side=side,
                amount=amount,
            )
            print(f"✅ {symbol} {reverse_action} 开仓成功!")
            print(f"   价格: ${current_price:.2f}")
            print(f"   数量: {amount:.4f}")
            print(f"   订单ID: {order['id']}")

            # 记录持仓
            positions[symbol] = {
                'side': reverse_action,
                'entry_price': current_price,
                'amount': amount,
                'order_id': order['id'],
                'timestamp': datetime.now().isoformat(),
                'stop_loss': current_price * (1 - REVERSE_CONFIG['stop_loss_pct']) if reverse_action == 'LONG' else current_price * (1 + REVERSE_CONFIG['stop_loss_pct']),
                'take_profit': current_price * (1 + REVERSE_CONFIG['take_profit_pct']) if reverse_action == 'LONG' else current_price * (1 - REVERSE_CONFIG['take_profit_pct']),
            }
        else:
            print(f"🧪 [测试模式] {symbol} {reverse_action}")
            print(f"   价格: ${current_price:.2f}, 数量: {amount:.4f}")

    except Exception as e:
        print(f"❌ 交易执行失败: {e}")


def close_position(symbol):
    """平仓"""
    try:
        if symbol not in positions:
            return

        pos = positions[symbol]
        ticker = exchange.fetch_ticker(symbol)
        current_price = ticker['last']

        # 计算盈亏
        if pos['side'] == 'LONG':
            pnl_pct = (current_price - pos['entry_price']) / pos['entry_price'] * 100
        else:
            pnl_pct = (pos['entry_price'] - current_price) / pos['entry_price'] * 100

        # 平仓
        side = 'sell' if pos['side'] == 'LONG' else 'buy'

        if not REVERSE_CONFIG['test_mode']:
            order = exchange.create_market_order(
                symbol=symbol,
                side=side,
                amount=pos['amount'],
            )
            print(f"🔴 {symbol} 平仓: {pnl_pct:+.2f}%")
        else:
            print(f"🧪 [测试模式] {symbol} 平仓: {pnl_pct:+.2f}%")

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


def run_reverse_strategy():
    """运行反向跟单策略"""
    print("=" * 60)
    print("🔄 GPT-5 反向跟单策略启动")
    print(f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    # 检查止损止盈
    check_stop_loss_take_profit()

    # 遍历所有交易对
    for symbol in REVERSE_CONFIG['symbols']:
        print(f"\n📊 分析 {symbol}...")

        # 获取 GPT-5 的信号
        gpt5_signal = get_gpt5_trading_signal(symbol)
        print(f"   GPT-5 信号: {gpt5_signal['action']} (置信度: {gpt5_signal['confidence']:.2f})")
        print(f"   理由: {gpt5_signal['reason'][:100]}...")

        # 转换为反向信号
        reverse_action = reverse_signal(gpt5_signal)
        print(f"   🔄 反向操作: {reverse_action}")

        # 检查信号是否变化
        if symbol in gpt5_last_signals:
            if gpt5_last_signals[symbol] == gpt5_signal['action']:
                print(f"   ⏭️  信号未变化，跳过")
                continue

        # 记录信号
        gpt5_last_signals[symbol] = gpt5_signal['action']

        # 执行交易
        if REVERSE_CONFIG['auto_trade'] and gpt5_signal['confidence'] >= 0.6:
            execute_reverse_trade(symbol, reverse_action)
        else:
            print(f"   ⚠️  置信度不足或未启用自动交易，跳过")

        time.sleep(2)  # 避免API限流

    # 打印当前持仓
    print(f"\n📦 当前持仓: {len(positions)}")
    for symbol, pos in positions.items():
        ticker = exchange.fetch_ticker(symbol)
        current_price = ticker['last']
        if pos['side'] == 'LONG':
            pnl_pct = (current_price - pos['entry_price']) / pos['entry_price'] * 100
        else:
            pnl_pct = (pos['entry_price'] - current_price) / pos['entry_price'] * 100
        print(f"   {symbol}: {pos['side']} @ ${pos['entry_price']:.2f} -> ${current_price:.2f} ({pnl_pct:+.2f}%)")

    print("\n" + "=" * 60)


if __name__ == "__main__":
    print("""
    ╔══════════════════════════════════════════════════════════╗
    ║         GPT-5 反向跟单策略 Reverse Copy Trading         ║
    ║                                                          ║
    ║  策略逻辑: GPT-5 做多 → 我们做空                       ║
    ║           GPT-5 做空 → 我们做多                       ║
    ║           GPT-5 观望 → 我们观望                       ║
    ║                                                          ║
    ║  ⚠️  风险提示: 反向跟单存在高风险，请谨慎使用！         ║
    ╚══════════════════════════════════════════════════════════╝
    """)

    try:
        while True:
            run_reverse_strategy()
            print(f"\n⏰ 等待 5 分钟后再次运行...")
            time.sleep(300)  # 每5分钟运行一次
    except KeyboardInterrupt:
        print("\n\n👋 策略已停止")
