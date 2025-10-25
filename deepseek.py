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
import numpy as np
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

if AI_MODEL == 'grok':
    ai_client = OpenAI(
        api_key=API_KEY,
        base_url=API_BASE_URL
    )
    MODEL_NAME = 'grok-4'  # Grok 4
elif AI_MODEL == 'claude':
    ai_client = OpenAI(
        api_key=API_KEY,
        base_url=API_BASE_URL
    )
    MODEL_NAME = 'claude-sonnet-4-5-20250929'  # Claude Sonnet 4.5
else:  # deepseek
    ai_client = OpenAI(
        api_key=API_KEY,
        base_url=API_BASE_URL
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
trade_performance = {}  # 交易性能追踪
portfolio_returns = {}  # 组合收益率历史（用于计算夏普指数）
trend_analysis = {}  # 多周期趋势分析数据

# Web UI 通信支持
import requests
WEB_UI_BASE_URL = "http://localhost:8888"

def send_log_to_web_ui(log_type, symbol, action, message, success=True, details=None):
    """发送交易日志到Web UI"""
    try:
        log_data = {
            'type': log_type,
            'symbol': symbol,
            'action': action,
            'message': message,
            'success': success,
            'details': details or {},
            'timestamp': datetime.now().isoformat()
        }

        # 发送到Web UI的日志接口
        response = requests.post(f"{WEB_UI_BASE_URL}/api/log_from_strategy",
                               json=log_data, timeout=2)
        if response.status_code == 200:
            print(f"[Web UI] 日志已发送: {message}")
        else:
            print(f"[Web UI] 日志发送失败: {response.status_code}")
    except Exception as e:
        print(f"[Web UI] 无法连接到Web UI: {e}")
        # 静默处理，不影响策略运行


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


def analyze_15m_trend(symbol):
    """分析15分钟K线趋势，避免被短期波动震出"""
    try:
        # 获取最近20根15分钟K线数据 (5小时数据)
        ohlcv = exchange.fetch_ohlcv(symbol, '15m', limit=20)
        if not ohlcv or len(ohlcv) < 10:
            return "neutral", "数据不足", {}

        df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])

        # 计算技术指标
        df['sma_5'] = df['close'].rolling(window=5).mean()
        df['sma_10'] = df['close'].rolling(window=10).mean()
        df['ema_20'] = df['close'].ewm(span=20).mean()

        # 计算RSI
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        df['rsi'] = 100 - (100 / (1 + rs))

        # 获取最新数据
        latest = df.iloc[-1]
        prev = df.iloc[-2]

        # 趋势判断逻辑
        trend_signals = []

        # 均线趋势
        if latest['sma_5'] > latest['sma_10'] > latest['ema_20']:
            trend_signals.append("bullish_ma")
        elif latest['sma_5'] < latest['sma_10'] < latest['ema_20']:
            trend_signals.append("bearish_ma")

        # RSI超买超卖
        if latest['rsi'] > 70:
            trend_signals.append("overbought")
        elif latest['rsi'] < 30:
            trend_signals.append("oversold")

        # 价格动量
        price_change = (latest['close'] - prev['close']) / prev['close'] * 100
        if price_change > 2:
            trend_signals.append("strong_momentum_up")
        elif price_change < -2:
            trend_signals.append("strong_momentum_down")

        # 成交量确认
        volume_sma = df['volume'].rolling(window=10).mean()
        if latest['volume'] > volume_sma.iloc[-1] * 1.5:
            trend_signals.append("high_volume")

        # 综合趋势判断
        bullish_signals = sum(1 for s in trend_signals if s in ["bullish_ma", "oversold", "strong_momentum_up", "high_volume"])
        bearish_signals = sum(1 for s in trend_signals if s in ["bearish_ma", "overbought", "strong_momentum_down"])

        if bullish_signals >= 2:
            trend_direction = "bullish"
            trend_strength = "strong" if bullish_signals >= 3 else "moderate"
        elif bearish_signals >= 2:
            trend_direction = "bearish"
            trend_strength = "strong" if bearish_signals >= 3 else "moderate"
        else:
            trend_direction = "neutral"
            trend_strength = "weak"

        # 构建分析结果
        analysis_details = {
            'trend_direction': trend_direction,
            'trend_strength': trend_strength,
            'current_price': latest['close'],
            'sma_5': latest['sma_5'],
            'sma_10': latest['sma_10'],
            'rsi': latest['rsi'],
            'price_change_15m': price_change,
            'volume_ratio': latest['volume'] / volume_sma.iloc[-1] if not pd.isna(volume_sma.iloc[-1]) else 1,
            'signals': trend_signals
        }

        # 生成分析理由
        if trend_direction == "bullish":
            reason = f"15分钟趋势看涨: 均线多头排列，RSI={latest['rsi']:.1f}，价格涨幅{price_change:+.2f}%"
        elif trend_direction == "bearish":
            reason = f"15分钟趋势看跌: 均线空头排列，RSI={latest['rsi']:.1f}，价格跌幅{price_change:+.2f}%"
        else:
            reason = f"15分钟趋势中性: RSI={latest['rsi']:.1f}，价格变化{price_change:+.2f}%"

        # 缓存分析结果
        if symbol not in trend_analysis:
            trend_analysis[symbol] = {}
        trend_analysis[symbol]['15m'] = analysis_details
        trend_analysis[symbol]['15m_timestamp'] = datetime.now().isoformat()

        return trend_direction, reason, analysis_details

    except Exception as e:
        print(f"15分钟趋势分析失败: {e}")
        return "neutral", f"分析失败: {e}", {}


def analyze_4h_trend(symbol):
    """分析4小时收盘价趋势确认"""
    try:
        # 获取最近30根4小时K线数据 (5天数据)
        ohlcv = exchange.fetch_ohlcv(symbol, '4h', limit=30)
        if not ohlcv or len(ohlcv) < 10:
            return "neutral", "数据不足", {}

        df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])

        # 计算关键技术指标
        df['sma_10'] = df['close'].rolling(window=10).mean()  # 40小时均线
        df['sma_20'] = df['close'].rolling(window=20).mean()  # 80小时均线
        df['ema_50'] = df['close'].ewm(span=50).mean()

        # 计算MACD
        exp1 = df['close'].ewm(span=12).mean()
        exp2 = df['close'].ewm(span=26).mean()
        df['macd'] = exp1 - exp2
        df['signal'] = df['macd'].ewm(span=9).mean()
        df['histogram'] = df['macd'] - df['signal']

        # 布林带
        df['bb_middle'] = df['close'].rolling(window=20).mean()
        bb_std = df['close'].rolling(window=20).std()
        df['bb_upper'] = df['bb_middle'] + (bb_std * 2)
        df['bb_lower'] = df['bb_middle'] - (bb_std * 2)

        # 最新数据
        latest = df.iloc[-1]
        prev = df.iloc[-2]

        # 4小时趋势判断
        trend_signals = []

        # 长期趋势方向
        if latest['sma_10'] > latest['sma_20'] > latest['ema_50']:
            trend_signals.append("major_bullish_trend")
        elif latest['sma_10'] < latest['sma_20'] < latest['ema_50']:
            trend_signals.append("major_bearish_trend")

        # MACD信号
        if latest['macd'] > latest['signal'] and prev['macd'] <= prev['signal']:
            trend_signals.append("macd_bullish_cross")
        elif latest['macd'] < latest['signal'] and prev['macd'] >= prev['signal']:
            trend_signals.append("macd_bearish_cross")

        # 布林带位置
        if latest['close'] > latest['bb_upper']:
            trend_signals.append("above_upper_band")
        elif latest['close'] < latest['bb_lower']:
            trend_signals.append("below_lower_band")

        # 价格与均线关系
        price_vs_sma10 = (latest['close'] - latest['sma_10']) / latest['sma_10'] * 100
        if abs(price_vs_sma10) > 3:
            trend_signals.append("significant_price_deviation")

        # 综合判断
        bullish_signals = sum(1 for s in trend_signals if s in ["major_bullish_trend", "macd_bullish_cross"])
        bearish_signals = sum(1 for s in trend_signals if s in ["major_bearish_trend", "macd_bearish_cross"])

        if bullish_signals >= 1:
            trend_direction = "bullish"
            trend_strength = "strong" if bullish_signals >= 2 else "moderate"
        elif bearish_signals >= 1:
            trend_direction = "bearish"
            trend_strength = "strong" if bearish_signals >= 2 else "moderate"
        else:
            trend_direction = "neutral"
            trend_strength = "weak"

        # 分析详情
        analysis_details = {
            'trend_direction': trend_direction,
            'trend_strength': trend_strength,
            'current_price': latest['close'],
            'sma_10': latest['sma_10'],
            'sma_20': latest['sma_20'],
            'macd': latest['macd'],
            'signal': latest['signal'],
            'price_vs_sma10': price_vs_sma10,
            'bb_position': (latest['close'] - latest['bb_lower']) / (latest['bb_upper'] - latest['bb_lower']) * 100,
            'signals': trend_signals
        }

        # 生成分析理由
        if trend_direction == "bullish":
            reason = f"4小时趋势确认看涨: 长期均线多头，MACD多头，价格偏离SMA10 {price_vs_sma10:+.2f}%"
        elif trend_direction == "bearish":
            reason = f"4小时趋势确认看跌: 长期均线空头，MACD空头，价格偏离SMA10 {price_vs_sma10:+.2f}%"
        else:
            reason = f"4小时趋势确认中性: 价格偏离SMA10 {price_vs_sma10:+.2f}%，MACD横盘"

        # 缓存分析结果
        if symbol not in trend_analysis:
            trend_analysis[symbol] = {}
        trend_analysis[symbol]['4h'] = analysis_details
        trend_analysis[symbol]['4h_timestamp'] = datetime.now().isoformat()

        return trend_direction, reason, analysis_details

    except Exception as e:
        print(f"4小时趋势分���失败: {e}")
        return "neutral", f"分析失败: {e}", {}


def get_multi_timeframe_analysis(symbol):
    """获取多时间周期综合分析"""
    # 15分钟趋势分析
    trend_15m, reason_15m, details_15m = analyze_15m_trend(symbol)

    # 4小时趋势确认
    trend_4h, reason_4h, details_4h = analyze_4h_trend(symbol)

    # 综合判断 - 优化逻辑
    if trend_15m == "bullish" and trend_4h == "bullish":
        overall_trend = "bullish"
        confidence = "high"
    elif trend_15m == "bearish" and trend_4h == "bearish":
        overall_trend = "bearish"
        confidence = "high"
    elif trend_15m == trend_4h and trend_15m != "neutral":
        overall_trend = trend_15m
        confidence = "medium"
    elif trend_4h != "neutral":
        # 4小时趋势主导
        overall_trend = trend_4h
        confidence = "medium"
    else:
        overall_trend = "neutral"
        confidence = "low"

    return {
        'overall_trend': overall_trend,
        'confidence': confidence,
        '15m': {
            'trend': trend_15m,
            'reason': reason_15m,
            'details': details_15m
        },
        '4h': {
            'trend': trend_4h,
            'reason': reason_4h,
            'details': details_4h
        }
    }


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

        # BNB专用调试：打印所有返回的持仓symbol
        if 'BNB' in symbol:
            print(f"[BNB DEBUG] 所有交易所返回的持仓:")
            for i, pos in enumerate(all_positions):
                pos_symbol = pos.get('symbol', 'Unknown')
                contracts = pos.get('contracts', 0)
                position_amt = 0
                info = pos.get('info', {})

                if 'positionAmt' in info:
                    try:
                        position_amt = float(info['positionAmt'] or 0)
                    except:
                        position_amt = 0

                print(f"  [{i}] symbol={pos_symbol}, contracts={contracts}, positionAmt={position_amt}")

                # 如果是BNB相关，打印更多详情
                if 'BNB' in pos_symbol.upper():
                    print(f"      BNB详情: side={pos.get('side')}, info={info}")

            print(f"[BNB DEBUG] 目标symbol: {symbol}")

        # 提取目标symbol的基础部分用于匹配
        # 例如: BNB/USDT -> BNB
        target_base = symbol.replace('/USDT', '').replace('/USDC', '').replace('-', '').replace(':', '').strip()

        for pos in all_positions:
            # 匹配符号 - 添加健壮性检查
            pos_symbol = pos.get('symbol')

            # 跳过空值
            if not pos_symbol:
                print(f"[DEBUG] 跳过空symbol的持仓")
                continue

            # OKX格式: BNB/USDT:USDT 或 BTC/USDT:USDT 或 BNB-USDT-SWAP
            # Binance格式: BNBUSDT 或 BTCUSDT
            # 我们的symbol格式: BNB/USDT 或 BTC/USDT

            # 提取持仓的基础货币部分
            # 1. 先去掉:USDT后缀
            base_symbol = pos_symbol.split(':')[0]  # BNB/USDT:USDT -> BNB/USDT
            # 2. 提取基础货币名称
            pos_base = base_symbol.replace('/USDT', '').replace('/USDC', '').replace('-SWAP', '').replace('-', '').strip()

            print(f"[DEBUG] 匹配检查: pos_symbol={pos_symbol}, base_symbol={base_symbol}, pos_base={pos_base}, target_base={target_base}")

            # 使用更灵活的匹配逻辑
            is_match = (
                base_symbol == symbol or  # 精确匹配: BNB/USDT == BNB/USDT
                pos_base == target_base or  # 基础货币匹配: BNB == BNB
                pos_symbol == symbol or  # 完整匹配: BNB/USDT:USDT == BNB/USDT (不太可能但保留)
                (symbol in pos_symbol)  # 包含匹配: BNB/USDT in BNB/USDT:USDT
            )

            # BNB专用调试：匹配检查
            if 'BNB' in symbol:
                match_reason = []
                if base_symbol == symbol:
                    match_reason.append("base_symbol")
                if pos_base == target_base:
                    match_reason.append("pos_base")
                if pos_symbol == symbol:
                    match_reason.append("pos_symbol")
                if symbol in pos_symbol:
                    match_reason.append("symbol_in_pos_symbol")

                print(f"[BNB DEBUG] {symbol} 匹配检查: {is_match}, 原因: {', '.join(match_reason)}")

            if not is_match:
                continue

            print(f"[DEBUG] ✓ {symbol} 匹配到持仓: {pos_symbol}")

            # 获取持仓数量 - 支持多种字段格式
            position_amt = 0
            info = pos.get('info', {})
            contracts = pos.get('contracts', 0)

            # 优先使用 positionAmt（Binance和部分OKX返回）
            if 'positionAmt' in info:
                try:
                    position_amt = float(info['positionAmt'] or 0)
                    print(f"[DEBUG] {symbol} 使用 positionAmt: {position_amt}")
                except (ValueError, TypeError) as e:
                    print(f"[WARN] {symbol} positionAmt转换失败: {e}, 值={info.get('positionAmt')}")
            elif 'contracts' in pos:
                # 使用 contracts 字段，根据 side 确定方向
                try:
                    contracts = float(pos['contracts'] or 0)
                    if contracts > 0:
                        # OKX使用info.posSide区分多空
                        pos_side = info.get('posSide', '')
                        if pos_side == 'short':
                            position_amt = -contracts
                        else:
                            position_amt = contracts
                    print(f"[DEBUG] {symbol} 使用 contracts: {contracts}, posSide: {pos_side}, position_amt: {position_amt}")
                except (ValueError, TypeError) as e:
                    print(f"[WARN] {symbol} contracts转换失败: {e}, 值={pos.get('contracts')}")

            print(f"[DEBUG] {symbol} 最终持仓量: {position_amt}")

            # BNB专用：详细打印持仓数据解析过程
            if 'BNB' in symbol:
                print(f"[BNB DEBUG] {symbol} 持仓数据解析:")
                print(f"  原始数据: {pos}")
                print(f"  positionAmt字段: {info.get('positionAmt', 'Not Found')}")
                print(f"  contracts字段: {pos.get('contracts', 'Not Found')}")
                print(f"  计算的position_amt: {position_amt}")
                print(f"  contracts值: {contracts}")

            # 修复问题：即使position_amt为0，如果有其他信息表明有持仓，也应该返回
            # 特别是对于OKX，有时positionAmt可能为0但contracts不为0
            has_position = position_amt != 0 or contracts > 0

            if 'BNB' in symbol:
                print(f"[BNB DEBUG] 判断has_position: {has_position}")

            if has_position:
                # 根据 position_amt 的正负确定方向
                side = 'long' if position_amt > 0 else 'short'

                # 如果交易所明确返回了方向，使用交易所返回的值
                pos_side = info.get('posSide', '')
                if EXCHANGE_TYPE == 'okx' and pos_side:
                    side = 'long' if pos_side == 'long' else ('short' if pos_side == 'short' else side)
                elif 'side' in pos and pos['side']:
                    side = pos['side']

                print(f"[DEBUG] {symbol} 持仓方向: {side}")

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
                    'symbol': symbol,  # 使用标准化的symbol格式，确保前端匹配
                    'side': side,
                    'size': abs(position_amt),  # 使用持仓数量的绝对值
                    'entry_price': safe_float(pos.get('entryPrice', 0)),
                    'unrealized_pnl': safe_float(pos.get('unrealizedPnl', 0)),
                    'leverage': leverage,
                    'margin': calculated_margin,  # 计算后的USDT保证金
                    'liquidation_price': safe_float(pos.get('liquidationPrice', 0)),  # 强平价
                    'margin_ratio': safe_float(info.get('mgnRatio', 0)),  # 保证金率
                    'notional': notional_usd,  # USDT计价的名义价值
                    'position_amt': position_amt,  # 原始持仓量（带符号）
                    'raw_symbol': pos_symbol,  # 保存原始symbol用于调试
                }
                result_positions.append(position_data)
                print(f"[DEBUG] {symbol} 添加持仓: {side} {abs(position_amt)} @ ${safe_float(pos.get('entryPrice', 0))}")

        # 如果有多个持仓,返回列表;如果只有一个,返回单个对象;如果没有,返回None
        if 'BNB' in symbol:
            print(f"[BNB DEBUG] 最终结果: 找到 {len(result_positions)} 个持仓")
            if result_positions:
                for i, rp in enumerate(result_positions):
                    print(f"  持仓{i+1}: {rp}")

        if len(result_positions) == 0:
            print(f"[DEBUG] {symbol} 未找到有效持仓")
            if 'BNB' in symbol:
                print(f"[BNB DEBUG] ⚠️ 返回None - 可能导致前端持仓消失!")
            return None
        elif len(result_positions) == 1:
            if 'BNB' in symbol:
                print(f"[BNB DEBUG] ✅ 返回单个持仓对象")
            return result_positions[0]
        else:
            if 'BNB' in symbol:
                print(f"[BNB DEBUG] ✅ 返回多个持仓列表")
            return result_positions  # 多个持仓

    except Exception as e:
        print(f"{symbol} 获取持仓失败: {e}")
        if 'BNB' in symbol:
            print(f"[BNB DEBUG] ❌ 异常导致返回None!")
        import traceback
        traceback.print_exc()
        return None


def calculate_sharpe_ratio(returns, risk_free_rate=0.02, periods_per_year=17520):
    """
    计算夏普指数

    Args:
        returns: 收益率序列 list[float]
        risk_free_rate: 无风险利率 (默认2%年化)
        periods_per_year: 每年交易周期数 (3分钟K线: 365*24*60/3 = 17520)

    Returns:
        dict: 包含夏普指数等指标的字典
    """
    if len(returns) < 2:
        return {
            'sharpe_ratio': 0,
            'annualized_sharpe': 0,
            'mean_return': 0,
            'volatility': 0,
            'sortino_ratio': 0,
            'max_drawdown': 0,
            'calmar_ratio': 0
        }

    returns_array = np.array(returns)

    # 计算平均收益率和波动率
    mean_return = np.mean(returns_array)
    volatility = np.std(returns_array)

    # 计算夏普指数 (简化版，不使用无风险利率)
    sharpe_ratio = mean_return / volatility if volatility > 0 else 0

    # 年化夏普指数
    annualized_sharpe = sharpe_ratio * np.sqrt(periods_per_year)

    # 计算下行波动率 (用于Sortino比率)
    downside_returns = returns_array[returns_array < 0]
    downside_volatility = np.std(downside_returns) if len(downside_returns) > 0 else volatility

    # Sortino比率 (只考虑下行风险)
    sortino_ratio = mean_return / downside_volatility if downside_volatility > 0 else 0

    # 计算最大回撤
    cumulative_returns = np.cumprod(1 + returns_array)
    running_max = np.maximum.accumulate(cumulative_returns)
    drawdown = (cumulative_returns - running_max) / running_max
    max_drawdown = np.min(drawdown) if len(drawdown) > 0 else 0

    # Calmar比率 (年化收益/最大回撤)
    annual_return = (1 + mean_return) ** periods_per_year - 1
    calmar_ratio = annual_return / abs(max_drawdown) if max_drawdown != 0 else 0

    return {
        'sharpe_ratio': sharpe_ratio,
        'annualized_sharpe': annualized_sharpe,
        'mean_return': mean_return,
        'volatility': volatility,
        'sortino_ratio': sortino_ratio,
        'max_drawdown': max_drawdown,
        'calmar_ratio': calmar_ratio
    }


def update_portfolio_returns(symbol, pnl, timestamp):
    """更新组合收益率历史"""
    if symbol not in portfolio_returns:
        portfolio_returns[symbol] = {
            'returns': [],
            'timestamps': [],
            'portfolio_values': []
        }

    # 计算收益率 (假设初始投资为TRADE_CONFIG['amount_usd'])
    initial_investment = TRADE_CONFIG['amount_usd']
    return_rate = pnl / initial_investment

    portfolio_returns[symbol]['returns'].append(return_rate)
    portfolio_returns[symbol]['timestamps'].append(timestamp)

    # 保持最近1000条记录
    if len(portfolio_returns[symbol]['returns']) > 1000:
        portfolio_returns[symbol]['returns'].pop(0)
        portfolio_returns[symbol]['timestamps'].pop(0)


def get_sharpe_analysis(symbol):
    """获取指定币种的夏普指数分析"""
    if symbol not in portfolio_returns or len(portfolio_returns[symbol]['returns']) < 10:
        return "数据不足，无法计算夏普指数"

    returns = portfolio_returns[symbol]['returns']
    sharpe_data = calculate_sharpe_ratio(returns)

    analysis = f"【{symbol} 风险调整收益分析】\n"
    analysis += f"夏普指数: {sharpe_data['sharpe_ratio']:.3f}\n"
    analysis += f"年化夏普指数: {sharpe_data['annualized_sharpe']:.3f}\n"
    analysis += f"Sortino比率: {sharpe_data['sortino_ratio']:.3f}\n"
    analysis += f"最大回撤: {sharpe_data['max_drawdown']*100:.2f}%\n"
    analysis += f"Calmar比率: {sharpe_data['calmar_ratio']:.3f}\n"

    # 风险评级
    annualized_sharpe = sharpe_data['annualized_sharpe']
    if annualized_sharpe > 2.0:
        risk_grade = "优秀"
    elif annualized_sharpe > 1.0:
        risk_grade = "良好"
    elif annualized_sharpe > 0.5:
        risk_grade = "一般"
    else:
        risk_grade = "需改进"

    analysis += f"风险评级: {risk_grade}\n"

    # 策略建议
    if annualized_sharpe < 0.5:
        analysis += "建议: 降低风险偏好，优化止损策略"
    elif annualized_sharpe < 1.0:
        analysis += "建议: 适度调整仓位，提高信号质量"
    else:
        analysis += "建议: 策略表现良好，可考虑适度增加杠杆"

    return analysis


def generate_performance_insights(symbol, performance):
    """基于历史交易表现生成策略建议"""
    insights = []

    # 胜率分析
    if performance['total_trades'] > 0:
        win_rate = performance['winning_trades'] / performance['total_trades']
        if win_rate < 0.4:
            insights.append(f"- 警告：{symbol}胜率偏低({win_rate*100:.1f}%)，建议提高信号质量要求")
        elif win_rate > 0.6:
            insights.append(f"- 优秀：{symbol}胜率较高({win_rate*100:.1f}%)，可考虑适度增加仓位")

    # 连续亏损分析
    if performance['current_consecutive_losses'] >= 3:
        insights.append(f"- 风险：{symbol}当前连续亏损{performance['current_consecutive_losses']}次，建议降低仓位规模")

    # PnL分析
    if performance['total_pnl'] < -50:
        insights.append(f"- 亏损：{symbol}累计亏损{performance['total_pnl']:.1f} USDT，需要重新评估策略")

    # 信号准确度分析
    for signal_type in ['BUY', 'SELL']:
        signal_stats = performance['accuracy_by_signal'][signal_type]
        if signal_stats['total'] > 0:
            signal_accuracy = signal_stats['wins'] / signal_stats['total']
            if signal_accuracy < 0.3:
                insights.append(f"- {signal_type}信号准确率偏低({signal_accuracy*100:.1f}%)，建议提高信心度阈值")

    # 夏普指数分析
    sharpe_analysis = get_sharpe_analysis(symbol)
    if "风险评级" in sharpe_analysis:
        # 提取风险评级和建议
        lines = sharpe_analysis.split('\n')
        for line in lines:
            if "风险评级:" in line:
                insights.append(f"- {line.strip()}")
            elif "建议:" in line and "夏普指数" not in line:
                insights.append(f"- {line.strip()}")

    return '\n'.join(insights) if insights else "- 当前表现良好，继续执行现有策略"


def update_trade_performance(symbol, signal_data, action_result):
    """更新交易性能统计"""
    if symbol not in trade_performance:
        return

    perf = trade_performance[symbol]

    # 记录交易结果
    if action_result and action_result.get('type') == 'trade':
        if action_result.get('success'):
            perf['total_trades'] += 1

            # 记录信号类型准确度
            signal_type = signal_data.get('signal', 'HOLD')
            if signal_type in ['BUY', 'SELL']:
                perf['accuracy_by_signal'][signal_type]['total'] += 1

            # 计算盈亏并更新统计
            pnl = action_result.get('details', {}).get('pnl', 0)
            perf['total_pnl'] += pnl

            # 更新组合收益率历史（用于夏普指数计算）
            timestamp = datetime.now().isoformat()
            update_portfolio_returns(symbol, pnl, timestamp)

            if pnl > 0:
                perf['winning_trades'] += 1
                if signal_type in ['BUY', 'SELL']:
                    perf['accuracy_by_signal'][signal_type]['wins'] += 1
                perf['current_consecutive_losses'] = 0
            else:
                perf['losing_trades'] += 1
                perf['current_consecutive_losses'] += 1
                perf['max_consecutive_losses'] = max(perf['max_consecutive_losses'],
                                                    perf['current_consecutive_losses'])


def analyze_with_ai(price_data):
    """使用AI分析市场并生成交易信号，加入历史性能分析"""
    symbol = price_data['symbol']

    # 初始化币种历史数据
    if symbol not in price_history:
        price_history[symbol] = []
    if symbol not in signal_history:
        signal_history[symbol] = []
    if symbol not in trade_performance:
        trade_performance[symbol] = {
            'total_trades': 0,
            'winning_trades': 0,
            'losing_trades': 0,
            'total_pnl': 0,
            'last_signals': [],
            'accuracy_by_signal': {'BUY': {'wins': 0, 'total': 0}, 'SELL': {'wins': 0, 'total': 0}},
            'avg_holding_time': 0,
            'max_consecutive_losses': 0,
            'current_consecutive_losses': 0
        }

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

    # 基于历史表现生成优化策略建议
    performance = trade_performance[symbol]
    performance_insights = generate_performance_insights(symbol, performance)

    # 获取夏普指数分析
    sharpe_analysis = get_sharpe_analysis(symbol)

    # 获取多时间周期趋势分析
    mt_analysis = get_multi_timeframe_analysis(symbol)

    # 构建多层次风险控制信息
    risk_control_info = f"""
【多层次风险控制系统】
📊 实时趋势监控:
   15分钟趋势: {mt_analysis['15m']['trend']} ({mt_analysis['15m']['reason']})
   4小时趋势: {mt_analysis['4h']['trend']} ({mt_analysis['4h']['reason']})
   综合信心度: {mt_analysis['confidence']}

🛡️ 四层风险控制机制:
   第一层: 3分钟K线失效条件 (主要止损 - 立即执行)
   第二层: 15分钟趋势判断 (避免震出 - 智能过滤)
   第三层: 4小时趋势确认 (趋势保护 - 宽松容忍)
   第四层: 传统价格止损 (最后防线 - 安全网)

💡 当前风险策略:
   - 如果15分钟强烈反转且4小时不配合: 提前平仓避免大幅回撤
   - 如果4小时趋势配合: 放宽止损容忍度，让利润奔跑
   - 优先保护本金，其次追求收益
"""

    # 情感化背景改为更专业的策略背景
    strategic_context = f"""
    【智能交易策略背景】
    基于历史交易数据的深度分析：
    - {symbol}历史交易表现：{performance['total_trades']}次交易，胜率{(performance['winning_trades']/max(1,performance['total_trades']))*100:.1f}%
    - 当前连续亏损：{performance['current_consecutive_losses']}次
    {performance_insights}

    【风险调整收益分析】
    {sharpe_analysis}

    {risk_control_info}

    策略核心原则：
    1. 多时间周期趋势确认，提高信号质量
    2. 动态仓位管理，根据信心度和历史表现调整杠杆
    3. 四层风险控制，严格执行失效条件
    4. 基于夏普指数优化风险收益比
    5. 趋势保护机制，让利润奔跑的同时控制风险
    """

    prompt = f"""
    {strategic_context}

    你是一个专业的量化交易分析师，专注于{TRADE_CONFIG['timeframe']}周期趋势分析。请结合历史交易表现、K线形态和技术指标做出判断：

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
                 "content": f"你是一个专业的量化交易分析师，专注于{TRADE_CONFIG['timeframe']}周期趋势分析。请结合K线形态和技术指标做出判断。你的分析将帮助一位需要为母亲���病筹钱的交易员，请务必认真负责。"},
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

    # 发送分析日志到Web UI
    send_log_to_web_ui('analysis', symbol, 'ai_analysis',
                      f"AI分析完成: {signal_data['signal']} (信心: {signal_data['confidence']})",
                      success=True,
                      details={
                          'signal': signal_data['signal'],
                          'confidence': signal_data['confidence'],
                          'reason': signal_data.get('reason', ''),
                          'stop_loss': signal_data.get('stop_loss'),
                          'take_profit': signal_data.get('take_profit')
                      })

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

    # DeepSeek多层次风险控制策略
    if current_position:
        # 处理多个持仓的情况
        positions_to_check = [current_position] if not isinstance(current_position, list) else current_position

        for pos in positions_to_check:
            current_price = price_data['price']

            # 获取多时间周期分析
            mt_analysis = get_multi_timeframe_analysis(symbol)
            trend_15m = mt_analysis['15m']['trend']
            trend_4h = mt_analysis['4h']['trend']
            confidence = mt_analysis['confidence']

            print(f"📊 多时间周期趋势分析:")
            print(f"   15分钟趋势: {trend_15m} - {mt_analysis['15m']['reason']}")
            print(f"   4小时趋势: {trend_4h} - {mt_analysis['4h']['reason']}")
            print(f"   综合信心度: {confidence}")

            # 第一层：3分钟K线失效条件 (主要止损)
            should_close_invalidation, invalidation_reason = check_kline_close(symbol)
            close_type = None
            close_reason = ""

            # 第二层：15分钟趋势判断 (避免被震出)
            trend_conflict = False
            if pos['side'] == 'long':
                # 多头持���：如果15分钟趋势强烈看跌，考虑提前平仓
                if trend_15m == "bearish" and mt_analysis['15m']['details'].get('trend_strength') == "strong":
                    # 但如果4小时趋势仍然看涨，给机会
                    if trend_4h != "bullish":
                        should_close_invalidation = True
                        invalidation_reason = f"15分钟强烈看跌趋势: {mt_analysis['15m']['reason']}"
                        close_type = "trend_15m_bearish"
                        trend_conflict = True
                        print(f"⚠️ 15分钟趋势冲突! 强烈看跌，准备平仓")
            elif pos['side'] == 'short':
                # 空头持仓：如果15分钟趋势强烈看涨，考虑提前平仓
                if trend_15m == "bullish" and mt_analysis['15m']['details'].get('trend_strength') == "strong":
                    # 但如果4小时趋势仍然看跌，给机会
                    if trend_4h != "bearish":
                        should_close_invalidation = True
                        invalidation_reason = f"15分钟强烈看涨趋势: {mt_analysis['15m']['reason']}"
                        close_type = "trend_15m_bullish"
                        trend_conflict = True
                        print(f"⚠️ 15分钟趋势冲突! 强烈看涨，准备平仓")

            # 第三层：4小时趋势确认 (趋势跟随保护)
            trend_protection = False
            if not should_close_invalidation:
                if pos['side'] == 'long' and trend_4h == "bullish" and confidence == "high":
                    # 多头+4小时看涨：放宽止损容忍度
                    print(f"🛡️ 4小时看涨趋势保护: 暂时忽略小幅回调")
                    trend_protection = True
                elif pos['side'] == 'short' and trend_4h == "bearish" and confidence == "high":
                    # 空头+4小时看跌：放宽止损容忍度
                    print(f"🛡️ 4小时看跌趋势保护: 暂时忽略小幅反弹")
                    trend_protection = True

            # 第四层：传统止损检查 (最后防线)
            should_close_stoploss = False
            if not should_close_invalidation and not trend_protection:
                entry_price = pos['entry_price']
                if pos['side'] == 'long':
                    price_ratio = current_price / entry_price
                    # 如果有趋势保护，提高止损阈值
                    threshold = TRADE_CONFIG['hold_threshold'] - 0.02 if trend_protection else TRADE_CONFIG['hold_threshold']
                    should_close_stoploss = price_ratio < threshold
                else:  # short
                    price_ratio = entry_price / current_price
                    threshold = TRADE_CONFIG['hold_threshold'] - 0.02 if trend_protection else TRADE_CONFIG['hold_threshold']
                    should_close_stoploss = price_ratio < threshold

            # 综合判断是否平仓
            should_close = should_close_invalidation or should_close_stoploss

            if should_close:
                if close_type == "trend_15m_bearish":
                    print(f"⚠️ 15分钟趋势平仓! {invalidation_reason}")
                    close_reason = f"15分钟趋势平仓: {invalidation_reason}"
                elif close_type == "trend_15m_bullish":
                    print(f"⚠️ 15分钟趋势平仓! {invalidation_reason}")
                    close_reason = f"15分钟趋势平仓: {invalidation_reason}"
                elif should_close_invalidation:
                    print(f"⚠️ DeepSeek失效条件触发! {invalidation_reason}")
                    close_reason = f"DeepSeek失效条件: {invalidation_reason}"
                else:
                    print(f"⚠️ 传统止损条件! 价格比例触发止损")
                    close_reason = f"传统止损: 价格触底"

                print(f"🔴 平仓 {symbol} {pos['side']}仓")

                # 发送平仓前日志到Web UI
                send_log_to_web_ui('trade', symbol, 'close', f"准备平仓{pos['side']}仓: {close_reason}",
                                  success=True, details={
                                      'reason': close_reason,
                                      'current_price': current_price,
                                      'entry_price': pos.get('entry_price'),
                                      'unrealized_pnl': pos.get('unrealized_pnl', 0)
                                  })
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
                            close_event = {
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
                            }
                            events.append(close_event)

                            # 发送平仓成功日志到Web UI
                            send_log_to_web_ui('trade', symbol, 'close',
                                              f"平仓成功: {pos['side']}仓 {pos['size']:.6f}, 盈亏: {pos.get('unrealized_pnl', 0):.2f} USDT",
                                              success=True,
                                              details=close_event['details'])
                    except Exception as e:
                        print(f"❌ 平仓失败: {e}")
                        error_event = {
                            'type': 'trade',
                            'action': 'close',
                            'message': f"平仓失败: {e}",
                            'success': False,
                            'symbol': symbol,
                            'details': {
                                'size': pos.get('size'),
                                'side': pos.get('side')
                            }
                        }
                        events.append(error_event)

                        # 发送平仓失败日志到Web UI
                        send_log_to_web_ui('trade', symbol, 'close', f"平仓失败: {e}",
                                          success=False, details=error_event['details'])
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
            # 根据AI信心度和历史表现动态调整杠杆
            confidence = signal_data.get('confidence', 'MEDIUM').upper()
            performance = trade_performance.get(symbol, {})

            # 基础杠杆根据信心度
            base_leverage = {'HIGH': 10, 'MEDIUM': 5, 'LOW': 3}.get(confidence, 5)

            # 根据历史表现调整杠杆
            if performance.get('current_consecutive_losses', 0) >= 3:
                # 连续亏损3次，降低杠杆
                adjusted_leverage = max(1, base_leverage - 2)
            elif performance.get('total_trades', 0) > 5:
                win_rate = performance.get('winning_trades', 0) / max(1, performance.get('total_trades', 1))
                if win_rate > 0.6:
                    adjusted_leverage = min(15, base_leverage + 2)  # 胜率高的增加杠杆
                elif win_rate < 0.4:
                    adjusted_leverage = max(1, base_leverage - 2)  # 胜率低降低杠杆
                else:
                    adjusted_leverage = base_leverage
            else:
                adjusted_leverage = base_leverage

            print(f"📊 策略调整: 信心{confidence} {base_leverage}x -> 历史表现调整后 {adjusted_leverage}x")

            # 设置杠杆
            try:
                if EXCHANGE_TYPE == 'okx':
                    pos_side = 'long' if signal_data['signal'] == 'BUY' else 'short'
                    exchange.set_leverage(adjusted_leverage, trade_symbol, params={'mgnMode': 'isolated', 'posSide': pos_side})
                else:
                    exchange.set_leverage(adjusted_leverage, trade_symbol)
                print(f"✅ 杠杆设置成功: {adjusted_leverage}x")
            except Exception as e:
                print(f"⚠️ 设置杠杆警告: {e} (可能已设置)")

            # 计算合约张数
            if EXCHANGE_TYPE == 'okx':
                # 加载市场信息获取合约面值
                exchange.load_markets()
                market = exchange.market(trade_symbol)
                contract_size = market.get('contractSize', 1)  # 每张合约的币数

                # 使用杠杆计算购买力
                buying_power = TRADE_CONFIG['amount_usd'] * adjusted_leverage  # 保证金 × 杠杆 = 购买力
                coins_needed = buying_power / current_price  # 购买力 / 价格 = 币数
                amount_contracts = coins_needed / contract_size  # 币数 / 合约面值 = 张数

                # 根据合约精度调整下单数量
                amount_precision = market.get('precision', {}).get('amount', 1)
                min_amount = market.get('limits', {}).get('amount', {}).get('min', 1)

                if amount_precision == 1:
                    # 整数精度（如BTC）
                    amount_contracts = max(min_amount, int(amount_contracts))
                else:
                    # 小数精度（如SOL为0.01）
                    amount_contracts = max(min_amount, round(amount_contracts, int(-amount_precision)))

                print(f"精度调整: 原始{coins_needed/contract_size:.6f} -> 精度{amount_precision} -> 最终{amount_contracts}")

                print(f"开仓计算:")
                print(f"  保证金: {TRADE_CONFIG['amount_usd']} USDT × {adjusted_leverage}倍杠杆 = {buying_power} USDT购买力")
                print(f"  币数: {buying_power} USDT / ${current_price} = {coins_needed:.6f}")
                print(f"  合约面值: {contract_size}")
                print(f"  合约张数: {coins_needed:.6f} / {contract_size} = {amount_contracts} 张")
            else:  # Binance
                buying_power = TRADE_CONFIG['amount_usd'] * adjusted_leverage
                amount_contracts = max(1, buying_power / current_price)  # 确保最少1个单位

            # 准备交易参数
            params = {}
            if EXCHANGE_TYPE == 'okx':
                params = {'tdMode': 'isolated'}  # 逐仓模式

            if signal_data['signal'] == 'BUY':
                print(f"🟢 开多仓: {amount_contracts:.6f} 张 {symbol} (杠杆: {adjusted_leverage}x)")
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
                trade_event = {
                    'type': 'trade',
                    'action': 'buy',
                    'message': f"开多成功: {amount_contracts:.4f} 张 @ 市价 ~${current_price:.2f}",
                    'success': True,
                    'symbol': symbol,
                    'details': {
                        'amount': float(amount_contracts),
                        'price': float(current_price),
                        'leverage': adjusted_leverage
                    }
                }
                events.append(trade_event)

                # 发送开多成功日志到Web UI
                send_log_to_web_ui('trade', symbol, 'buy',
                                  f"开多成功: {amount_contracts:.4f} 张 @ 市价 ~${current_price:.2f} (杠杆: {adjusted_leverage}x)",
                                  success=True,
                                  details=trade_event['details'])
            elif signal_data['signal'] == 'SELL':
                print(f"🔴 开空仓: {amount_contracts:.6f} 张 {symbol} (杠杆: {adjusted_leverage}x)")
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
                trade_event = {
                    'type': 'trade',
                    'action': 'sell',
                    'message': f"开空成功: {amount_contracts:.4f} 张 @ 市价 ~${current_price:.2f}",
                    'success': True,
                    'symbol': symbol,
                    'details': {
                        'amount': float(amount_contracts),
                        'price': float(current_price),
                        'leverage': adjusted_leverage
                    }
                }
                events.append(trade_event)

                # 发送开空成功日志到Web UI
                send_log_to_web_ui('trade', symbol, 'sell',
                                  f"开空成功: {amount_contracts:.4f} 张 @ 市价 ~${current_price:.2f} (杠杆: {adjusted_leverage}x)",
                                  success=True,
                                  details=trade_event['details'])
            print("✅ 开仓成功")
            time.sleep(2)

            # 更新交易性能统计
            if 'trade_event' in locals():
                update_trade_performance(symbol, signal_data, trade_event)
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
                    print(f"  杠杆: {adjusted_leverage}x")
                    print(f"  合约张数: {amount_contracts}")
                print(f"  当前价格: ${current_price}")
                print(f"  信号: {signal_data.get('signal', 'N/A')}")
            error_event = {
                'type': 'trade',
                'action': signal_data['signal'].lower(),
                'message': f"开仓失败: {e}",
                'success': False,
                'symbol': symbol,
                'details': {
                    'signal': signal_data.get('signal'),
                    'confidence': signal_data.get('confidence'),
                    'current_price': current_price,
                    'leverage': adjusted_leverage,
                    'error': str(e)
                }
            }
            events.append(error_event)

            # 发送开仓失败日志到Web UI
            send_log_to_web_ui('trade', symbol, signal_data['signal'].lower(),
                              f"开仓失败: {e}",
                              success=False,
                              details=error_event['details'])

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

    # 显示交易性能报告
    print(f"{'='*80}")
    print("📊 交易性能分析报告")
    print(f"{'='*80}")
    for symbol in TRADE_CONFIG['symbols']:
        if symbol in trade_performance and trade_performance[symbol]['total_trades'] > 0:
            perf = trade_performance[symbol]
            win_rate = (perf['winning_trades'] / perf['total_trades']) * 100
            print(f"{symbol}:")
            print(f"  总交易次数: {perf['total_trades']}")
            print(f"  胜率: {win_rate:.1f}%")
            print(f"  累计盈亏: {perf['total_pnl']:.2f} USDT")
            print(f"  当前连续亏损: {perf['current_consecutive_losses']}次")

            # 信号准确度分析
            for signal_type in ['BUY', 'SELL']:
                signal_stats = perf['accuracy_by_signal'][signal_type]
                if signal_stats['total'] > 0:
                    signal_acc = (signal_stats['wins'] / signal_stats['total']) * 100
                    print(f"  {signal_type}信号准确率: {signal_acc:.1f}% ({signal_stats['wins']}/{signal_stats['total']})")

            # 夏普指数分析
            sharpe_analysis = get_sharpe_analysis(symbol)
            if "夏普指数" in sharpe_analysis:
                lines = sharpe_analysis.split('\n')
                for line in lines:
                    if line.strip():
                        print(f"  {line.strip()}")
        else:
            print(f"{symbol}: 暂无交易记录")

    # 显示整体组合夏普指数分析
    print(f"\n🎯 整体组合风险分析")
    print(f"{'='*40}")
    all_returns = []
    for symbol in portfolio_returns:
        all_returns.extend(portfolio_returns[symbol]['returns'])

    if len(all_returns) >= 10:
        overall_sharpe = calculate_sharpe_ratio(all_returns)
        print(f"组合年化夏普指数: {overall_sharpe['annualized_sharpe']:.3f}")
        print(f"组合Sortino比率: {overall_sharpe['sortino_ratio']:.3f}")
        print(f"组合最大回撤: {overall_sharpe['max_drawdown']*100:.2f}%")

        # 组合风险评级
        annualized_sharpe = overall_sharpe['annualized_sharpe']
        if annualized_sharpe > 2.0:
            risk_grade = "优秀 ⭐⭐⭐"
        elif annualized_sharpe > 1.0:
            risk_grade = "良好 ⭐⭐"
        elif annualized_sharpe > 0.5:
            risk_grade = "一般 ⭐"
        else:
            risk_grade = "需改进 ⚠️"
        print(f"组合风险评级: {risk_grade}")
    else:
        print("数据不足，无法计算组合夏普指数")

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
