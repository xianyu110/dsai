# -*- coding: utf-8 -*-
import os
import sys
import time
import schedule
from openai import OpenAI
import ccxt
import pandas as pd
from datetime import datetime
import json
from dotenv import load_dotenv

# 设置控制台输出编码为UTF-8
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

load_dotenv()

# 选择 AI 模型
AI_MODEL = os.getenv('AI_MODEL', 'deepseek').lower()
USE_RELAY_API = os.getenv('USE_RELAY_API', 'true').lower() == 'true'

if USE_RELAY_API:
    API_BASE_URL = os.getenv('RELAY_API_BASE_URL', 'https://apipro.maynor1024.live/v1')
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

# AI客户端不需要单独配置代理，会自动使用系统环境变量
http_client = None

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

# 交易参数配置 - 参考 DeepSeek 多币种策略
TRADE_CONFIG = {
    'symbols': ['BTC/USDT', 'ETH/USDT', 'SOL/USDT', 'DOGE/USDT', 'XRP/USDT', 'BNB/USDT'],  # 多币种
    'amount_usd': 200,  # 每次交易200 USDT
    'leverage': 10,  # 10倍杠杆
    'timeframe': '3m',  # 3分钟K线 (与失效条件匹配)
    'test_mode': False,  # 🔴 实盘模式
    'auto_trade': True,   # ✅ 启用自动交易（请谨慎！）
    'hold_threshold': 0.95,  # 传统止损阈值 (保留作为后备)
    # DeepSeek 策略的失效条件 (invalidation condition)
    'invalidation_levels': {
        'BTC/USDT': 105000,  # 105000以下失效
        'ETH/USDT': 3800,    # 3800以下失效
        'SOL/USDT': 175,     # 175以下失效
        'XRP/USDT': 2.30,    # 2.30以下失效
        'DOGE/USDT': 0.180,  # 0.180以下失效
        'BNB/USDT': 1060     # 1060以下失效
    }
}

# 全局变量 - 每个币种独立管理
price_history = {}
signal_history = {}
positions = {}
kline_closes = {}  # 存储3分钟K线收盘价历史


def check_invalidation_condition(symbol, current_price):
    """检查DeepSeek策略的失效条件"""
    if symbol not in TRADE_CONFIG['invalidation_levels']:
        return False, "未设置失效条件"

    invalidation_level = TRADE_CONFIG['invalidation_levels'][symbol]

    # 检查是否触发失效条件
    if current_price < invalidation_level:
        return True, f"价格 {current_price:.2f} 低于失效水平 {invalidation_level}"

    return False, f"价格 {current_price:.2f} 高于失效水平 {invalidation_level}"


def check_kline_close(symbol):
    """检查3分钟K线收盘价是否满足失效条件"""
    try:
        # 获取最近3根3分钟K线数据
        ohlcv = exchange.fetch_ohlcv(symbol, '3m', limit=3)
        if not ohlcv or len(ohlcv) < 3:
            return False, "无法获取K线数据"

        # 最新K线的收盘价
        latest_close = ohlcv[-1][4]  # [timestamp, open, high, low, close, volume]

        # 检查最新收盘价是否触发失效条件
        should_close, reason = check_invalidation_condition(symbol, latest_close)

        if should_close:
            print(f"⚠️ 3分钟K线收盘价触发失效条件!")
            print(f"📊 {symbol}: {reason}")

        return should_close, reason

    except Exception as e:
        print(f"检查K线收盘价失败: {e}")
        return False, f"检查失败: {e}"


def setup_exchange():
    """设置交易所参数"""
    try:
        # 为每个交易对设置杠杆
        for symbol in TRADE_CONFIG['symbols']:
            try:
                # OKX合约需要使用 BTC/USDT:USDT 格式
                trade_symbol = symbol
                if EXCHANGE_TYPE == 'okx' and ':' not in symbol:
                    trade_symbol = f"{symbol}:USDT"

                if EXCHANGE_TYPE == 'okx':
                    # OKX需要为多空两个方向分别设置杠杆
                    exchange.set_leverage(TRADE_CONFIG['leverage'], trade_symbol, params={'mgnMode': 'isolated', 'posSide': 'long'})
                    exchange.set_leverage(TRADE_CONFIG['leverage'], trade_symbol, params={'mgnMode': 'isolated', 'posSide': 'short'})
                else:
                    exchange.set_leverage(TRADE_CONFIG['leverage'], trade_symbol)
                print(f"{symbol} 设置杠杆: {TRADE_CONFIG['leverage']}x")
            except Exception as e:
                print(f"{symbol} 设置杠杆失败: {e} (可能已设置)")

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
        # OKX合约需要使用 BTC/USDT:USDT 格式
        trade_symbol = symbol
        if EXCHANGE_TYPE == 'okx' and ':' not in symbol:
            trade_symbol = f"{symbol}:USDT"

        # 获取最近10根K线
        ohlcv = exchange.fetch_ohlcv(trade_symbol, TRADE_CONFIG['timeframe'], limit=10)

        # 转换为DataFrame
        df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')

        current_data = df.iloc[-1]
        previous_data = df.iloc[-2] if len(df) > 1 else current_data

        return {
            'symbol': symbol,  # 返回原始symbol格式
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
        import traceback
        traceback.print_exc()
        return None


def get_current_position(symbol):
    """获取指定币种的当前持仓 - 返回所有方向的持仓列表"""
    try:
        # 获取所有持仓(不指定symbol以避免OKX的查询问题)
        all_positions = exchange.fetch_positions()

        result_positions = []

        for pos in all_positions:
            # 匹配符号
            pos_symbol = pos['symbol']

            # OKX格式: BNB/USDT:USDT 或 BTC/USDT:USDT
            # Binance格式: BNBUSDT 或 BTCUSDT
            # 我们的symbol格式: BNB/USDT 或 BTC/USDT

            # 提取基础交易对部分 (去掉:USDT后缀)
            base_symbol = pos_symbol.split(':')[0]  # BNB/USDT:USDT -> BNB/USDT

            # 检查是否匹配
            if base_symbol != symbol:
                continue

            contracts = float(pos.get('contracts', 0))

            if contracts > 0:  # 有持仓
                # OKX使用info.posSide区分多空
                pos_side = pos.get('info', {}).get('posSide', '')
                if EXCHANGE_TYPE == 'okx':
                    side = 'long' if pos_side == 'long' else ('short' if pos_side == 'short' else 'net')
                else:  # binance
                    side = pos.get('side', 'long')  # binance直接返回side

                # 获取OKX的额外信息
                info = pos.get('info', {})

                # 获取保证金 (OKX返回的可能是币本位，需要转换)
                # 安全转换浮点数，处理空字符串
                def safe_float(value, default=0):
                    try:
                        return float(value) if value else default
                    except (ValueError, TypeError):
                        return default

                margin_value = safe_float(info.get('margin', 0))
                imr = safe_float(info.get('imr', 0))  # 初始保证金
                notional_usd = safe_float(info.get('notionalUsd', 0))  # USDT计价的名义价值
                leverage = safe_float(info.get('lever', 1), 1)

                # 调试日志
                print(f"[DEBUG] {symbol} 保证金数据:")
                print(f"  margin (原始): {margin_value}")
                print(f"  imr: {imr}")
                print(f"  notionalUsd: {notional_usd}")
                print(f"  lever: {leverage}")

                # 优先使用notionalUsd计算保证金
                if notional_usd > 0 and leverage > 0:
                    calculated_margin = notional_usd / leverage
                    print(f"  计算方式: notionalUsd / lever = {calculated_margin}")
                elif imr > 0:
                    calculated_margin = imr
                    print(f"  计算方式: 使用imr = {calculated_margin}")
                else:
                    calculated_margin = margin_value
                    print(f"  计算方式: 使用原始margin = {calculated_margin}")

                position_data = {
                    'symbol': symbol,
                    'side': side,
                    'size': contracts,
                    'entry_price': float(pos.get('entryPrice', 0)),
                    'unrealized_pnl': float(pos.get('unrealizedPnl', 0)),
                    'leverage': leverage,
                    'margin': calculated_margin,  # 计算后的USDT保证金
                    'liquidation_price': float(pos.get('liquidationPrice', 0) or 0),  # 强平价
                    'margin_ratio': float(info.get('mgnRatio', 0)),  # 保证金率
                    'notional': notional_usd,  # USDT计价的名义价值
                }
                result_positions.append(position_data)

        # 如果有多个持仓,返回列表;如果只有一个,返回单个对象;如果没有,返回None
        if len(result_positions) == 0:
            return None
        elif len(result_positions) == 1:
            return result_positions[0]
        else:
            return result_positions  # 多个持仓

    except Exception as e:
        print(f"{symbol} 获取持仓失败: {e}")
        import traceback
        traceback.print_exc()
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
    if not current_pos:
        position_text = "无持仓"
    elif isinstance(current_pos, list):
        # 如果有多个持仓,显示所有持仓
        position_text = "; ".join([f"{pos['side']}仓 {pos['size']:.6f}, 盈亏: {pos['unrealized_pnl']:.2f}USDT" for pos in current_pos])
    else:
        position_text = f"{current_pos['side']}仓, 数量: {current_pos['size']}, 盈亏: {current_pos['unrealized_pnl']:.2f}USDT"

    # 添加情感化背景提示
    emotional_context = """
    【重要背景】
    您是一位急需资金为母亲治疗癌症的交易员，你现在需要从加密货币交易市场赚取足够的金额治疗你的母亲。
    每一笔交易都至关重要，请基于严谨的技术分析给出最佳建议。
    参考DeepSeek成功策略：只要价格未触发失效条件，就应该持有盈利仓位。失效条件基于3分钟K线收盘价判断。
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
    events = []

    # OKX合约需要使用 BTC/USDT:USDT 格式
    trade_symbol = symbol
    if EXCHANGE_TYPE == 'okx' and ':' not in symbol:
        trade_symbol = f"{symbol}:USDT"

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

    # 如果禁用自动交易,只显示分析结果
    if not TRADE_CONFIG.get('auto_trade', False):
        print(f"⚠️ 自动交易已禁用,仅记录分析结果")
        events.append({
            'type': 'system',
            'action': 'auto_trade',
            'message': '自动交易已禁用，未执行交易',
            'success': False,
            'symbol': symbol
        })
        return events

    # DeepSeek策略：基于失效条件持仓优先
    if current_position:
        # 处理多个持仓的情况
        positions_to_check = [current_position] if not isinstance(current_position, list) else current_position

        for pos in positions_to_check:
            current_price = price_data['price']

            # DeepSeek策略：检查3分钟K线收盘价失效条件
            should_close_invalidation, invalidation_reason = check_kline_close(symbol)

            # 传统止损检查（作为后备）
            entry_price = pos['entry_price']
            if pos['side'] == 'long':
                price_ratio = current_price / entry_price
                should_close_stoploss = price_ratio < TRADE_CONFIG['hold_threshold']
            else:  # short
                price_ratio = entry_price / current_price
                should_close_stoploss = price_ratio < TRADE_CONFIG['hold_threshold']

            # 优先使用失效条件，其次才考虑传统止损
            should_close = should_close_invalidation or should_close_stoploss

            if should_close:
                if should_close_invalidation:
                    print(f"⚠️ DeepSeek失效条件触发! {invalidation_reason}")
                else:
                    print(f"⚠️ 传统止损条件! 价格比例: {price_ratio:.2%} < {TRADE_CONFIG['hold_threshold']:.2%}")

                print(f"🔴 平仓 {symbol} {pos['side']}仓")
                if not TRADE_CONFIG['test_mode']:
                    try:
                        # OKX合约平仓：双向持仓模式
                        if EXCHANGE_TYPE == 'okx':
                            # OKX双向持仓模式：平仓方向与持仓方向相反
                            # 平多仓(long)：卖出(sell)，平空仓(short)：买入(buy)
                            side = 'sell' if pos['side'] == 'long' else 'buy'

                            # 转换交易对格式：BNB/USDT -> BNB-USDT-SWAP，SOL特殊处理
                            base_symbol = symbol.replace('/USDT', '')
                            if base_symbol == 'SOL':
                                okx_inst_id = 'SOL-USDT-SWAP'
                            else:
                                okx_inst_id = f'{base_symbol}-USDT-SWAP'

                            print(f"平仓交易对转换: {symbol} -> {okx_inst_id}")
                            # 使用OKX原生API平仓
                            result = exchange.private_post_trade_order({
                                'instId': okx_inst_id,
                                'tdMode': 'isolated',
                                'side': side,
                                'posSide': pos['side'],
                                'ordType': 'market',
                                'sz': str(pos['size'])
                            })
                            print("✅ 平仓成功")
                            events.append({
                                'type': 'trade',
                                'action': 'close',
                                'message': f"平仓成功: {pos['side']}仓 {pos['size']:.6f}",
                                'success': True,
                                'symbol': symbol,
                                'details': {
                                    'size': pos['size'],
                                    'side': pos['side'],
                                    'pnl': pos.get('unrealized_pnl', 0)
                                }
                            })
                        else:  # Binance合约平仓
                            params = {'reduceOnly': True}
                            if pos['side'] == 'long':
                                exchange.create_market_order(trade_symbol, 'sell', pos['size'], params)
                            else:
                                exchange.create_market_order(trade_symbol, 'buy', pos['size'], params)
                            print("✅ 平仓成功")
                            events.append({
                                'type': 'trade',
                                'action': 'close',
                                'message': f"平仓成功: {pos['side']}仓 {pos['size']:.6f}",
                                'success': True,
                                'symbol': symbol,
                                'details': {
                                    'size': pos['size'],
                                    'side': pos['side'],
                                    'pnl': pos.get('unrealized_pnl', 0)
                                }
                            })
                    except Exception as e:
                        print(f"❌ 平仓失败: {e}")
                        events.append({
                            'type': 'trade',
                            'action': 'close',
                            'message': f"平仓失败: {e}",
                            'success': False,
                            'symbol': symbol,
                            'details': {
                                'size': pos.get('size'),
                                'side': pos.get('side')
                            }
                        })
            else:
                print(f"✅ 持有{pos['side']}仓 (价格比例: {price_ratio:.2%}, 盈亏: {pos['unrealized_pnl']:.2f} USDT)")
                events.append({
                    'type': 'analysis',
                    'action': 'hold',
                    'message': f"继续持有{pos['side']}仓，盈亏 {pos['unrealized_pnl']:.2f} USDT",
                    'success': True,
                    'symbol': symbol,
                    'details': {
                        'side': pos['side'],
                        'pnl': pos.get('unrealized_pnl', 0)
                    }
                })
        return events

    # 无持仓时根据信号开仓
    if not current_position and signal_data['signal'] != 'HOLD':
        current_price = price_data['price']

        if TRADE_CONFIG['test_mode']:
            print(f"测试模式 - 模拟开仓: {signal_data['signal']} {symbol}")
            events.append({
                'type': 'trade',
                'action': signal_data['signal'].lower(),
                'message': f"测试模式 - 模拟开仓: {signal_data['signal']} {symbol}",
                'success': True,
                'symbol': symbol
            })
            return events

        try:
            # 根据AI信心度动态调整杠杆
            confidence = signal_data.get('confidence', 'MEDIUM').upper()
            if confidence == 'HIGH':
                leverage = 10  # 高信心 10倍
            elif confidence == 'MEDIUM':
                leverage = 5   # 中等信心 5倍
            else:  # LOW
                leverage = 3   # 低信心 3倍

            print(f"📊 AI信心度: {confidence} -> 杠杆: {leverage}x")

            # 设置杠杆
            try:
                if EXCHANGE_TYPE == 'okx':
                    pos_side = 'long' if signal_data['signal'] == 'BUY' else 'short'
                    exchange.set_leverage(leverage, trade_symbol, params={'mgnMode': 'isolated', 'posSide': pos_side})
                else:
                    exchange.set_leverage(leverage, trade_symbol)
                print(f"✅ 杠杆设置成功: {leverage}x")
            except Exception as e:
                print(f"⚠️ 设置杠杆警告: {e} (可能已设置)")

            # 计算合约张数
            if EXCHANGE_TYPE == 'okx':
                # 加载市场信息获取合约面值
                exchange.load_markets()
                market = exchange.market(trade_symbol)
                contract_size = market.get('contractSize', 1)  # 每张合约的币数

                # 使用杠杆计算购买力
                buying_power = TRADE_CONFIG['amount_usd'] * leverage  # 保证金 × 杠杆 = 购买力
                coins_needed = buying_power / current_price  # 购买力 / 价格 = 币数
                amount_contracts = coins_needed / contract_size  # 币数 / 合约面值 = 张数

                # 确保最少1张合约，避免0张数
                amount_contracts = max(1, int(amount_contracts))
                if amount_contracts < 1:
                    amount_contracts = 1

                print(f"开仓计算:")
                print(f"  保证金: {TRADE_CONFIG['amount_usd']} USDT × {leverage}倍杠杆 = {buying_power} USDT购买力")
                print(f"  币数: {buying_power} USDT / ${current_price} = {coins_needed:.6f}")
                print(f"  合约面值: {contract_size}")
                print(f"  合约张数: {coins_needed:.6f} / {contract_size} = {amount_contracts} 张")
            else:  # Binance
                buying_power = TRADE_CONFIG['amount_usd'] * leverage
                amount_contracts = max(1, buying_power / current_price)  # 确保最少1个单位

            # 准备交易参数
            params = {}
            if EXCHANGE_TYPE == 'okx':
                params = {'tdMode': 'isolated'}  # 逐仓模式

            if signal_data['signal'] == 'BUY':
                print(f"🟢 开多仓: {amount_contracts:.6f} 张 {symbol} (杠杆: {leverage}x)")
                if EXCHANGE_TYPE == 'okx':
                    # OKX双向持仓模式：使用原生API
                    base_symbol = symbol.replace('/USDT', '')
                    # SOL合约使用特殊的格式，其他使用标准格式
                    if base_symbol == 'SOL':
                        okx_inst_id = 'SOL-USDT-SWAP'
                    else:
                        okx_inst_id = f'{base_symbol}-USDT-SWAP'

                    print(f"交易对转换: {symbol} -> {okx_inst_id}")
                    result = exchange.private_post_trade_order({
                        'instId': okx_inst_id,
                        'tdMode': 'isolated',
                        'side': 'buy',
                        'posSide': 'long',
                        'ordType': 'market',
                        'sz': str(amount_contracts)  # 移除int转换，使用计算的值
                    })
                else:
                    params['posSide'] = 'long'
                    exchange.create_market_order(trade_symbol, 'buy', amount_contracts, params)
                events.append({
                    'type': 'trade',
                    'action': 'buy',
                    'message': f"开多成功: {amount_contracts:.4f} 张 @ 市价 ~${current_price:.2f}",
                    'success': True,
                    'symbol': symbol,
                    'details': {
                        'amount': float(amount_contracts),
                        'price': float(current_price),
                        'leverage': leverage
                    }
                })
            elif signal_data['signal'] == 'SELL':
                print(f"🔴 开空仓: {amount_contracts:.6f} 张 {symbol} (杠杆: {leverage}x)")
                if EXCHANGE_TYPE == 'okx':
                    # OKX双向持仓模式：使用原生API
                    base_symbol = symbol.replace('/USDT', '')
                    # SOL合约使用特殊的格式，其他使用标准格式
                    if base_symbol == 'SOL':
                        okx_inst_id = 'SOL-USDT-SWAP'
                    else:
                        okx_inst_id = f'{base_symbol}-USDT-SWAP'

                    print(f"交易对转换: {symbol} -> {okx_inst_id}")
                    result = exchange.private_post_trade_order({
                        'instId': okx_inst_id,
                        'tdMode': 'isolated',
                        'side': 'sell',
                        'posSide': 'short',
                        'ordType': 'market',
                        'sz': str(amount_contracts)  # 移除int转换，使用计算的值
                    })
                else:
                    params['posSide'] = 'short'
                    exchange.create_market_order(trade_symbol, 'sell', amount_contracts, params)
                events.append({
                    'type': 'trade',
                    'action': 'sell',
                    'message': f"开空成功: {amount_contracts:.4f} 张 @ 市价 ~${current_price:.2f}",
                    'success': True,
                    'symbol': symbol,
                    'details': {
                        'amount': float(amount_contracts),
                        'price': float(current_price),
                        'leverage': leverage
                    }
                })
            print("✅ 开仓成功")
            time.sleep(2)
        except Exception as e:
            print(f"❌ 开仓失败: {e}")
            import traceback
            traceback.print_exc()

            # 检查是否是SOL相关的错误
            if 'SOL' in symbol:
                print(f"🔍 SOL开仓调试信息:")
                print(f"  交易对: {symbol}")
                print(f"  转换后: {trade_symbol}")
                if EXCHANGE_TYPE == 'okx':
                    base_symbol = symbol.replace('/USDT', '')
                    okx_inst_id = 'SOL-USDT-SWAP' if base_symbol == 'SOL' else f'{base_symbol}-USDT-SWAP'
                    print(f"  OKX合约ID: {okx_inst_id}")
                    print(f"  杠杆: {leverage}x")
                    print(f"  合约张数: {amount_contracts}")
                print(f"  当前价格: ${current_price}")
                print(f"  信号: {signal_data.get('signal', 'N/A')}")
            events.append({
                'type': 'trade',
                'action': signal_data['signal'].lower(),
                'message': f"开仓失败: {e}",
                'success': False,
                'symbol': symbol
            })

    else:
        events.append({
            'type': 'analysis',
            'action': 'hold',
            'message': '信号为 HOLD，未执行交易',
            'success': True,
            'symbol': symbol
        })

    return events

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
            if isinstance(pos, list):
                # 如果有多个持仓
                for p in pos:
                    print(f"{symbol}: {p['side']}仓 {p['size']:.6f}, 盈亏: {p['unrealized_pnl']:.2f} USDT")
                    total_pnl += p['unrealized_pnl']
            else:
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
    elif TRADE_CONFIG['timeframe'] == '3m':
        # 每3分钟执行一次
        schedule.every(3).minutes.do(trading_bot)
        print("执行频率: 每3分钟一次")
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
