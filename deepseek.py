import os
import time
import schedule
from openai import OpenAI
import ccxt
import pandas as pd
from datetime import datetime
import json
from dotenv import load_dotenv

load_dotenv()

# 选择 AI 模型
AI_MODEL = os.getenv('AI_MODEL', 'deepseek').lower()
USE_RELAY_API = os.getenv('USE_RELAY_API', 'true').lower() == 'true'

if USE_RELAY_API:
    API_BASE_URL = os.getenv('RELAY_API_BASE_URL', 'https://for.shuo.bar/v1')
    API_KEY = os.getenv('RELAY_API_KEY')
else:
    API_BASE_URL = None
    if AI_MODEL == 'grok':
        API_KEY = os.getenv('GROK_API_KEY')
        API_BASE_URL = 'https://api.x.ai/v1'
    elif AI_MODEL == 'claude':
        API_KEY = os.getenv('CLAUDE_API_KEY')
        API_BASE_URL = 'https://api.anthropic.com/v1'
    else:
        API_KEY = os.getenv('DEEPSEEK_API_KEY')
        API_BASE_URL = 'https://api.deepseek.com'

# 初始化 AI 客户端 (统一使用中转API)
from openai import OpenAI
import httpx

# 配置代理用于 AI API
ai_proxies = {}
if os.getenv('HTTP_PROXY'):
    ai_proxies = {
        'http://': os.getenv('HTTP_PROXY'),
        'https://': os.getenv('HTTPS_PROXY', os.getenv('HTTP_PROXY')),
    }

http_client = httpx.Client(proxies=ai_proxies) if ai_proxies else None

if AI_MODEL == 'grok':
    ai_client = OpenAI(
        api_key=API_KEY,
        base_url=API_BASE_URL,
        http_client=http_client
    )
    MODEL_NAME = 'grok-4'  # Grok 4
elif AI_MODEL == 'claude':
    ai_client = OpenAI(
        api_key=API_KEY,
        base_url=API_BASE_URL,
        http_client=http_client
    )
    MODEL_NAME = 'claude-sonnet-4-5-20250929'  # Claude Sonnet 4.5
else:  # deepseek
    ai_client = OpenAI(
        api_key=API_KEY,
        base_url=API_BASE_URL,
        http_client=http_client
    )
    MODEL_NAME = 'deepseek-chat'  # DeepSeek V3.1

# 选择交易所: 'binance' 或 'okx'
EXCHANGE_TYPE = os.getenv('EXCHANGE_TYPE', 'okx').lower()

# 代理配置
proxies = {}
if os.getenv('HTTP_PROXY'):
    proxies = {
        'http': os.getenv('HTTP_PROXY'),
        'https': os.getenv('HTTPS_PROXY', os.getenv('HTTP_PROXY')),
    }

if EXCHANGE_TYPE == 'okx':
    exchange = ccxt.okx({
        'options': {'defaultType': 'swap'},  # 永续合约
        'apiKey': os.getenv('OKX_API_KEY'),
        'secret': os.getenv('OKX_SECRET'),
        'password': os.getenv('OKX_PASSWORD'),
        'proxies': proxies,
        'enableRateLimit': True,
    })
else:  # binance
    exchange = ccxt.binance({
        'options': {'defaultType': 'future'},
        'apiKey': os.getenv('BINANCE_API_KEY'),
        'secret': os.getenv('BINANCE_SECRET'),
        'proxies': proxies,
        'enableRateLimit': True,
    })

# 交易参数配置 - 参考 AlphaArena 多币种策略
TRADE_CONFIG = {
    'symbols': ['BTC/USDT', 'ETH/USDT', 'SOL/USDT', 'DOGE/USDT'],  # 多币种
    'amount_usd': 25,  # 每次交易25 USDT (4个币种共100 USDT)
    'leverage': 10,  # 10倍杠杆
    'timeframe': '15m',  # 15分钟K线
    'test_mode': False,  # 🔴 实盘模式
    'hold_threshold': 0.95,  # 只要价格高于入场价95%就持有
}

# 全局变量 - 每个币种独立管理
price_history = {}
signal_history = {}
positions = {}


def setup_exchange():
    """设置交易所参数"""
    try:
        # 为每个交易对设置杠杆
        for symbol in TRADE_CONFIG['symbols']:
            exchange.set_leverage(TRADE_CONFIG['leverage'], symbol)
            print(f"{symbol} 设置杠杆: {TRADE_CONFIG['leverage']}x")

        # 获取余额
        balance = exchange.fetch_balance()
        usdt_balance = balance['USDT']['free']
        print(f"当前USDT余额: {usdt_balance:.2f}")

        return True
    except Exception as e:
        print(f"交易所设置失败: {e}")
        return False


def get_ohlcv(symbol):
    """获取指定币种的K线数据"""
    try:
        # 获取最近10根K线
        ohlcv = exchange.fetch_ohlcv(symbol, TRADE_CONFIG['timeframe'], limit=10)

        # 转换为DataFrame
        df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')

        current_data = df.iloc[-1]
        previous_data = df.iloc[-2] if len(df) > 1 else current_data

        return {
            'symbol': symbol,
            'price': current_data['close'],
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'high': current_data['high'],
            'low': current_data['low'],
            'volume': current_data['volume'],
            'timeframe': TRADE_CONFIG['timeframe'],
            'price_change': ((current_data['close'] - previous_data['close']) / previous_data['close']) * 100,
            'kline_data': df[['timestamp', 'open', 'high', 'low', 'close', 'volume']].tail(5).to_dict('records')
        }
    except Exception as e:
        print(f"{symbol} 获取K线数据失败: {e}")
        return None


def get_current_position(symbol):
    """获取指定币种的当前持仓"""
    try:
        positions_list = exchange.fetch_positions([symbol])

        # 标准化符号
        if EXCHANGE_TYPE == 'okx':
            config_symbol_normalized = symbol.replace('/', '/') + ':USDT'
        else:  # binance
            config_symbol_normalized = symbol + ':USDT'

        for pos in positions_list:
            if pos['symbol'] == config_symbol_normalized:
                position_amt = 0
                if 'positionAmt' in pos.get('info', {}):
                    position_amt = float(pos['info']['positionAmt'])
                elif 'contracts' in pos:
                    contracts = float(pos['contracts'])
                    if pos.get('side') == 'short':
                        position_amt = -contracts
                    else:
                        position_amt = contracts

                if position_amt != 0:
                    side = 'long' if position_amt > 0 else 'short'
                    return {
                        'symbol': symbol,
                        'side': side,
                        'size': abs(position_amt),
                        'entry_price': float(pos.get('entryPrice', 0)),
                        'unrealized_pnl': float(pos.get('unrealizedPnl', 0)),
                        'position_amt': position_amt,
                    }

        return None

    except Exception as e:
        print(f"{symbol} 获取持仓失败: {e}")
        return None


def analyze_with_ai(price_data):
    """使用AI分析市场并生成交易信号"""
    symbol = price_data['symbol']

    # 初始化币种历史数据
    if symbol not in price_history:
        price_history[symbol] = []
    if symbol not in signal_history:
        signal_history[symbol] = []

    # 添加当前价格到历史记录
    price_history[symbol].append(price_data)
    if len(price_history[symbol]) > 20:
        price_history[symbol].pop(0)

    # 构建K线数据文本
    kline_text = f"【最近5根{TRADE_CONFIG['timeframe']}K线数据】\n"
    for i, kline in enumerate(price_data['kline_data']):
        trend = "阳线" if kline['close'] > kline['open'] else "阴线"
        change = ((kline['close'] - kline['open']) / kline['open']) * 100
        kline_text += f"K线{i + 1}: {trend} 开盘:{kline['open']:.2f} 收盘:{kline['close']:.2f} 涨跌:{change:+.2f}%\n"

    # 构建技术指标文本
    if len(price_history[symbol]) >= 5:
        closes = [data['price'] for data in price_history[symbol][-5:]]
        sma_5 = sum(closes) / len(closes)
        price_vs_sma = ((price_data['price'] - sma_5) / sma_5) * 100

        indicator_text = f"【技术指标】\n5周期均价: {sma_5:.2f}\n当前价格相对于均线: {price_vs_sma:+.2f}%"
    else:
        indicator_text = "【技术指标】\n数据不足计算技术指标"

    # 添加上次交易信号
    signal_text = ""
    if signal_history[symbol]:
        last_signal = signal_history[symbol][-1]
        signal_text = f"\n【上次交易信号】\n信号: {last_signal.get('signal', 'N/A')}\n信心: {last_signal.get('confidence', 'N/A')}"

    # 添加当前持仓信息
    current_pos = get_current_position(symbol)
    position_text = "无持仓" if not current_pos else f"{current_pos['side']}仓, 数量: {current_pos['size']}, 盈亏: {current_pos['unrealized_pnl']:.2f}USDT"

    # 添加情感化背景提示
    emotional_context = """
    【重要背景】
    您是一位急需资金为母亲治疗癌症的交易员，你现在需要从加密货币交易市场赚取足够的金额治疗你的母亲。
    每一笔交易都至关重要，请基于严谨的技术分析给出最佳建议。
    参考AlphaArena成功策略：只要未触发止损条件，就应该持有盈利仓位。
    """

    prompt = f"""
    {emotional_context}

    你是一个专业的加密货币交易分析师。请基于以下{symbol} {TRADE_CONFIG['timeframe']}周期数据进行分析：

    {kline_text}

    {indicator_text}

    {signal_text}

    【当前行情】
    - 当前价格: ${price_data['price']:,.2f}
    - 时间: {price_data['timestamp']}
    - 本K线最高: ${price_data['high']:,.2f}
    - 本K线最低: ${price_data['low']:,.2f}
    - 本K线成交量: {price_data['volume']:.2f} BTC
    - 价格变化: {price_data['price_change']:+.2f}%
    - 当前持仓: {position_text}

    【分析要求】
    1. 基于{TRADE_CONFIG['timeframe']}K线趋势和技术指标给出交易信号: BUY(买入) / SELL(卖出) / HOLD(观望)
    2. 简要分析理由（考虑趋势连续性、支撑阻力、成交量等因素）
    3. 基于技术分析建议合理的止损价位
    4. 基于技术分析建议合理的止盈价位
    5. 评估信号信心程度

    请用以下JSON格式回复：
    {{
        "signal": "BUY|SELL|HOLD",
        "reason": "分析理由",
        "stop_loss": 具体价格,
        "take_profit": 具体价格,
        "confidence": "HIGH|MEDIUM|LOW"
    }}
    """

    try:
        # 统一使用 OpenAI 格式调用 (中转API兼容)
        response = ai_client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {"role": "system",
                 "content": f"你是一个专业的量化交易分析师，专注于{TRADE_CONFIG['timeframe']}周期趋势分析。请结合K线形态和技术指标做出判断。你的分析将帮助一位需要为母亲治病筹钱的交易员，请务必认真负责。"},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            stream=False
        )
        result = response.choices[0].message.content
        start_idx = result.find('{')
        end_idx = result.rfind('}') + 1
        if start_idx != -1 and end_idx != 0:
            json_str = result[start_idx:end_idx]
            signal_data = json.loads(json_str)
        else:
            print(f"无法解析JSON: {result}")
            return None

        # 保存信号到历史记录
        signal_data['timestamp'] = price_data['timestamp']
        signal_data['symbol'] = price_data['symbol']
        signal_history[symbol].append(signal_data)
        if len(signal_history[symbol]) > 30:
            signal_history[symbol].pop(0)

        return signal_data

    except Exception as e:
        print(f"{symbol} AI分析失败: {e}")
        return None


def execute_trade(signal_data, price_data):
    """执行交易 - 参考AlphaArena持仓逻辑"""
    symbol = price_data['symbol']

    current_position = get_current_position(symbol)

    print(f"\n{'='*60}")
    print(f"{symbol} 交易分析")
    print(f"{'='*60}")
    print(f"交易信号: {signal_data['signal']}")
    print(f"信心程度: {signal_data['confidence']}")
    print(f"理由: {signal_data['reason']}")

    # 安全处理价格字段
    try:
        stop_loss = float(signal_data.get('stop_loss', 0))
        take_profit = float(signal_data.get('take_profit', 0))
        print(f"止损: ${stop_loss:,.2f}")
        print(f"止盈: ${take_profit:,.2f}")
    except (ValueError, TypeError):
        print(f"止损: {signal_data.get('stop_loss', 'N/A')}")
        print(f"止盈: {signal_data.get('take_profit', 'N/A')}")

    print(f"当前持仓: {current_position}")

    # AlphaArena策略：持仓优先
    if current_position:
        entry_price = current_position['entry_price']
        current_price = price_data['price']
        price_ratio = current_price / entry_price

        # 只有触发止损才平仓(价格低于入场价95%)
        if price_ratio < TRADE_CONFIG['hold_threshold']:
            print(f"⚠️ 触发止损条件! 价格比例: {price_ratio:.2%} < {TRADE_CONFIG['hold_threshold']:.2%}")
            print(f"🔴 平仓 {symbol}")
            if not TRADE_CONFIG['test_mode']:
                try:
                    if current_position['side'] == 'long':
                        exchange.create_market_sell_order(symbol, current_position['size'])
                    else:
                        exchange.create_market_buy_order(symbol, current_position['size'])
                    print("✅ 平仓成功")
                except Exception as e:
                    print(f"❌ 平仓失败: {e}")
        else:
            print(f"✅ 持有{current_position['side']}仓 (价格比例: {price_ratio:.2%}, 盈亏: {current_position['unrealized_pnl']:.2f} USDT)")
            return

    # 无持仓时根据信号开仓
    if not current_position and signal_data['signal'] != 'HOLD':
        current_price = price_data['price']
        amount = TRADE_CONFIG['amount_usd'] / current_price  # 根据USDT金额计算数量

        if TRADE_CONFIG['test_mode']:
            print(f"测试模式 - 模拟开仓: {signal_data['signal']} {amount:.6f} {symbol}")
            return

        try:
            if signal_data['signal'] == 'BUY':
                print(f"🟢 开多仓: {amount:.6f} {symbol}")
                exchange.create_market_buy_order(symbol, amount)
            elif signal_data['signal'] == 'SELL':
                print(f"🔴 开空仓: {amount:.6f} {symbol}")
                exchange.create_market_sell_order(symbol, amount)
            print("✅ 开仓成功")
            time.sleep(2)
        except Exception as e:
            print(f"❌ 开仓失败: {e}")


def trading_bot():
    """主交易机器人函数 - 多币种版本"""
    print("\n" + "=" * 80)
    print(f"执行时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 80)

    # 遍历所有交易对
    for symbol in TRADE_CONFIG['symbols']:
        print(f"\n{'*'*60}")
        print(f"分析 {symbol}")
        print(f"{'*'*60}")

        # 1. 获取K线数据
        price_data = get_ohlcv(symbol)
        if not price_data:
            continue

        print(f"当前价格: ${price_data['price']:,.2f}")
        print(f"价格变化: {price_data['price_change']:+.2f}%")

        # 2. 使用AI分析
        signal_data = analyze_with_ai(price_data)
        if not signal_data:
            continue

        # 3. 执行交易
        execute_trade(signal_data, price_data)

    # 显示总体持仓情况
    print(f"\n{'='*80}")
    print("当前所有持仓汇总")
    print(f"{'='*80}")
    total_pnl = 0
    for symbol in TRADE_CONFIG['symbols']:
        pos = get_current_position(symbol)
        if pos:
            print(f"{symbol}: {pos['side']}仓 {pos['size']:.6f}, 盈亏: {pos['unrealized_pnl']:.2f} USDT")
            total_pnl += pos['unrealized_pnl']
        else:
            print(f"{symbol}: 无持仓")
    print(f"总盈亏: {total_pnl:.2f} USDT")
    print(f"{'='*80}\n")


def main():
    """主函数"""
    print("🤖 多币种自动交易机器人启动成功！")
    print(f"交易所: {EXCHANGE_TYPE.upper()}")
    print(f"AI 模型: {AI_MODEL.upper()} ({MODEL_NAME})")
    print(f"交易币种: {', '.join(TRADE_CONFIG['symbols'])}")

    if TRADE_CONFIG['test_mode']:
        print("⚠️  当前为模拟模式，不会真实下单")
    else:
        print("🔴 实盘交易模式，请谨慎操作！")

    print(f"交易周期: {TRADE_CONFIG['timeframe']}")
    print("已启用K线数据分析和持仓跟踪功能")

    # 设置交易所
    if not setup_exchange():
        print("交易所初始化失败，程序退出")
        return

    # 根据时间周期设置执行频率
    if TRADE_CONFIG['timeframe'] == '1h':
        # 每小时执行一次，在整点后的1分钟执行
        schedule.every().hour.at(":01").do(trading_bot)
        print("执行频率: 每小时一次")
    elif TRADE_CONFIG['timeframe'] == '15m':
        # 每15分钟执行一次
        schedule.every(15).minutes.do(trading_bot)
        print("执行频率: 每15分钟一次")
    else:
        # 默认1小时
        schedule.every().hour.at(":01").do(trading_bot)
        print("执行频率: 每小时一次")

    # 立即执行一次
    trading_bot()

    # 循环执行
    while True:
        schedule.run_pending()
        time.sleep(1)


if __name__ == "__main__":
    main()