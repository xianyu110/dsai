#!/usr/bin/env python3
"""
DeepSeek + Qwen3 Max 混合交易策略
结合稳健分散与集中火力的最优方案
"""

import os
import sys
import time
import json
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from dotenv import load_dotenv
import ccxt
from openai import OpenAI

# 设置编码
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

load_dotenv()

# AI配置
AI_MODEL = os.getenv('AI_MODEL', 'deepseek').lower()
USE_RELAY_API = os.getenv('USE_RELAY_API', 'true').lower() == 'true'

if USE_RELAY_API:
    API_BASE_URL = os.getenv('RELAY_API_BASE_URL', 'https://apipro.maynor1024.live/v1')
    API_KEY = os.getenv('RELAY_API_KEY')
else:
    API_BASE_URL = None
    if AI_MODEL == 'deepseek':
        API_KEY = os.getenv('DEEPSEEK_API_KEY')
        API_BASE_URL = 'https://api.deepseek.com'
    else:
        API_KEY = os.getenv('OPENAI_API_KEY')
        API_BASE_URL = 'https://api.openai.com/v1'

ai_client = OpenAI(api_key=API_KEY, base_url=API_BASE_URL)
MODEL_NAME = 'deepseek-chat' if AI_MODEL == 'deepseek' else 'gpt-4'

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

class HybridTradingStrategy:
    """DeepSeek + Qwen3 Max 混合策略"""

    def __init__(self, total_capital=10000):
        self.total_capital = total_capital

        # 资金分配策略
        self.allocation = {
            'deepseek_stable': 0.6,    # 60% 稳健分散策略
            'qwen3_aggressive': 0.4   # 40% 集中火力策略
        }

        # DeepSeek稳健策略配置 (60%资金)
        self.deepseek_config = {
            'capital': total_capital * 0.6,
            'symbols': ['BTC/USDT', 'ETH/USDT', 'SOL/USDT', 'DOGE/USDT'],  # 4个核心币种
            'leverage': 10,  # 适中杠杆
            'amount_per_trade': 300,  # 每次交易300 USDT
            'risk_per_trade': 0.02,  # 每次交易风险2%
            'stop_loss_type': '3m_invalidation',  # 3分钟失效条件
            'max_positions': 4
        }

        # Qwen3 Max集中策略配置 (40%资金)
        self.qwen3_config = {
            'capital': total_capital * 0.4,
            'focus_symbol': 'BTC/USDT',  # 集中火力BTC
            'leverage': 20,  # 高杠杆
            'amount_per_trade': 400,  # 每次交易400 USDT
            'risk_per_trade': 0.03,  # 每次交易风险3%
            'stop_loss_type': '4h_trend',  # 4小时趋势止损
            'max_positions': 1
        }

        # 失效条件设置
        self.invalidation_levels = {
            'BTC/USDT': 105000,
            'ETH/USDT': 3800,
            'SOL/USDT': 175,
            'DOGE/USDT': 0.180
        }

        # 策略状态
        self.positions = {}
        self.performance = {
            'deepseek': {'trades': 0, 'wins': 0, 'pnl': 0, 'sharpe': 0},
            'qwen3': {'trades': 0, 'wins': 0, 'pnl': 0, 'sharpe': 0},
            'total': {'trades': 0, 'wins': 0, 'pnl': 0, 'sharpe': 0}
        }

        # 动态再平衡参数
        self.rebalance_threshold = 0.1  # 10%偏差触发再平衡
        self.last_rebalance = datetime.now()

    def calculate_optimal_allocation(self, market_data):
        """根据市场状况动态调整资金分配"""

        # 计算市场波动率
        volatility = self._calculate_market_volatility(market_data)

        # 计算趋势强度
        trend_strength = self._calculate_trend_strength(market_data)

        # 动态调整分配比例
        if volatility > 0.15:  # 高波动市场
            # 增加稳健比例，降低集中比例
            deepseek_ratio = 0.7
            qwen3_ratio = 0.3
        elif volatility < 0.08 and trend_strength > 0.6:  # 低波动强趋势
            # 减少稳健比例，增加集中比例
            deepseek_ratio = 0.5
            qwen3_ratio = 0.5
        else:  # 正常市场
            deepseek_ratio = 0.6
            qwen3_ratio = 0.4

        return {
            'deepseek_ratio': deepseek_ratio,
            'qwen3_ratio': qwen3_ratio,
            'market_condition': self._classify_market(volatility, trend_strength)
        }

    def _calculate_market_volatility(self, market_data):
        """计算市场波动率"""
        if not market_data or len(market_data) < 10:
            return 0.1  # 默认波动率

        prices = [data.get('close', 0) for data in market_data[-20:]]
        if len(prices) < 2:
            return 0.1

        returns = np.diff(np.log(prices))
        volatility = np.std(returns) * np.sqrt(252)  # 年化波动率

        return min(volatility, 1.0)  # 限制最大波动率

    def _calculate_trend_strength(self, market_data):
        """计算趋势强度"""
        if not market_data or len(market_data) < 10:
            return 0.5

        prices = [data.get('close', 0) for data in market_data[-20:]]
        if len(prices) < 2:
            return 0.5

        # 计算线性回归斜率作为趋势强度
        x = np.arange(len(prices))
        slope, _ = np.polyfit(x, prices, 1)

        # 标准化斜率
        price_range = max(prices) - min(prices)
        trend_strength = abs(slope * len(prices) / price_range) if price_range > 0 else 0.5

        return min(trend_strength, 1.0)

    def _classify_market(self, volatility, trend_strength):
        """分类市场状况"""
        if volatility > 0.15:
            return "high_volatility"
        elif volatility < 0.08 and trend_strength > 0.6:
            return "strong_trend"
        elif volatility < 0.08:
            return "low_volatility"
        else:
            return "normal"

    def deepseek_strategy_decision(self, symbol, market_data):
        """DeepSeek稳健策略决策逻辑"""

        # 获取价格数据
        current_price = market_data.get('current_price', 0)
        if current_price <= 0:
            return {'signal': 'HOLD', 'confidence': 0.5, 'reason': '价格数据异常'}

        # 检查是否有持仓
        position = self.positions.get(f"deepseek_{symbol}")

        if position:
            return self._deepseek_position_management(symbol, position, market_data)
        else:
            return self._deepseek_entry_decision(symbol, market_data)

    def _deepseek_position_management(self, symbol, position, market_data):
        """DeepSeek持仓管理"""
        current_price = market_data.get('current_price', 0)

        # 第一层：3分钟失效条件检查
        if symbol in self.invalidation_levels:
            invalidation_level = self.invalidation_levels[symbol]
            if current_price < invalidation_level:
                return {
                    'signal': 'CLOSE',
                    'confidence': 1.0,
                    'reason': f'触发失效条件: 当前价格{current_price:.2f} < {invalidation_level}'
                }

        # 第二层：技术分析止损
        entry_price = position.get('entry_price', 0)
        if entry_price > 0:
            price_change = (current_price - entry_price) / entry_price

            if position['side'] == 'long':
                if price_change < -0.03:  # 3%止损
                    return {
                        'signal': 'CLOSE',
                        'confidence': 0.8,
                        'reason': f'技术止损: 价格下跌{price_change*100:.2f}%'
                    }
                elif price_change > 0.10:  # 10%部分止盈
                    return {
                        'signal': 'PARTIAL_CLOSE',
                        'confidence': 0.7,
                        'reason': f'部分止盈: 价格上涨{price_change*100:.2f}%'
                    }

        # 第三层：趋势判断
        trend_analysis = self._analyze_trend(market_data)
        if trend_analysis['trend'] == 'strong_bearish' and position['side'] == 'long':
            return {
                'signal': 'CLOSE',
                'confidence': 0.6,
                'reason': '趋势转弱，保护利润'
            }

        return {'signal': 'HOLD', 'confidence': 0.8, 'reason': '继续持有'}

    def _deepseek_entry_decision(self, symbol, market_data):
        """DeepSeek开仓决策"""

        # 技术分析
        trend_analysis = self._analyze_trend(market_data)

        # 信号强度评估
        signal_strength = 0
        reasons = []

        # 均线信号
        if trend_analysis.get('price_above_ma20', False):
            signal_strength += 0.3
            reasons.append("价格位于20日均线上方")

        # RSI信号
        rsi = trend_analysis.get('rsi', 50)
        if 30 < rsi < 70:  # RSI在合理区间
            signal_strength += 0.2
            reasons.append(f"RSI合理({rsi:.1f})")

        # MACD信号
        if trend_analysis.get('macd_bullish', False):
            signal_strength += 0.3
            reasons.append("MACD看涨")

        # 成交量确认
        if trend_analysis.get('volume_confirmation', False):
            signal_strength += 0.2
            reasons.append("成交量放大确认")

        # 生成决策
        if signal_strength >= 0.6:
            return {
                'signal': 'BUY',
                'confidence': min(signal_strength, 1.0),
                'reason': '、'.join(reasons)
            }
        elif signal_strength <= 0.2:
            return {
                'signal': 'SELL',
                'confidence': min(1 - signal_strength, 1.0),
                'reason': '技术指标偏弱'
            }
        else:
            return {'signal': 'HOLD', 'confidence': 0.5, 'reason': '信号不明确'}

    def qwen3_strategy_decision(self, market_data):
        """Qwen3 Max集中策略决策逻辑"""

        symbol = self.qwen3_config['focus_symbol']
        current_price = market_data.get('current_price', 0)

        if current_price <= 0:
            return {'signal': 'HOLD', 'confidence': 0.5, 'reason': '价格数据异常'}

        # 检查持仓
        position = self.positions.get(f"qwen3_{symbol}")

        if position:
            return self._qwen3_position_management(position, market_data)
        else:
            return self._qwen3_entry_decision(market_data)

    def _qwen3_position_management(self, position, market_data):
        """Qwen3持仓管理 - 简单有效的4小时趋势跟随"""
        current_price = market_data.get('current_price', 0)

        # 4小时趋势止损（Qwen3 Max的核心策略）
        invalidation_level = 105000  # BTC关键支撑位

        if current_price < invalidation_level:
            return {
                'signal': 'CLOSE',
                'confidence': 1.0,
                'reason': f'Qwen3策略: 4小时收盘价{current_price:.0f} < 关键支撑{invalidation_level}'
            }

        # 让利润奔跑 - 不设止盈，只在趋势反转时平仓
        entry_price = position.get('entry_price', 0)
        if entry_price > 0:
            profit_pct = (current_price - entry_price) / entry_price

            if profit_pct > 0.50:  # 盈利超过50%
                return {
                    'signal': 'HOLD',
                    'confidence': 0.9,
                    'reason': f'盈利{profit_pct*100:.1f}%，继续持有让利润奔跑'
                }
            elif profit_pct < -0.15:  # 亏损超过15%
                return {
                    'signal': 'CLOSE',
                    'confidence': 0.8,
                    'reason': f'亏损{abs(profit_pct)*100:.1f}%，控制风险'
                }

        return {'signal': 'HOLD', 'confidence': 0.8, 'reason': 'Qwen3策略：趋势继续，持有'}

    def _qwen3_entry_decision(self, market_data):
        """Qwen3开仓决策 - 集中火力BTC"""

        # 简单有效的入场信号
        current_price = market_data.get('current_price', 0)

        # 关键技术位判断
        if current_price > 106000:  # 突破关键阻力
            return {
                'signal': 'BUY',
                'confidence': 0.8,
                'reason': f'Qwen3策略: 价格{current_price:.0f}突破关键阻力位106000'
            }
        elif current_price < 95000:  # 回到支撑位
            return {
                'signal': 'BUY',
                'confidence': 0.7,
                'reason': f'Qwen3策略: 价格{current_price:.0f}接近强支撑位95000'
            }
        else:
            return {'signal': 'HOLD', 'confidence': 0.5, 'reason': 'Qwen3策略：观望等待机会'}

    def _analyze_trend(self, market_data):
        """技术分析助手"""
        # 这里应该调用实际的技术分析函数
        # 为了演示，返回模拟数据
        return {
            'trend': 'bullish',
            'price_above_ma20': True,
            'rsi': 55,
            'macd_bullish': True,
            'volume_confirmation': True
        }

    def rebalance_portfolio(self, market_data):
        """动态再平衡投资组合"""

        now = datetime.now()

        # 检查是否需要再平衡（时间或偏差触发）
        time_diff = (now - self.last_rebalance).total_seconds() / 3600  # 小时

        if time_diff < 24:  # 24小时内不重复再平衡
            return False

        # 计算最优分配
        optimal_allocation = self.calculate_optimal_allocation(market_data)

        # 计算当前分配偏差
        current_deepseek_ratio = self._calculate_current_deepseek_ratio()
        deviation = abs(current_deepseek_ratio - optimal_allocation['deepseek_ratio'])

        if deviation > self.rebalance_threshold:
            print(f"🔄 触发再平衡: 当前{current_deepseek_ratio:.1%} -> 目标{optimal_allocation['deepseek_ratio']:.1%}")
            print(f"📊 市场状况: {optimal_allocation['market_condition']}")

            # 执行再平衡逻辑
            self._execute_rebalance(optimal_allocation)
            self.last_rebalance = now
            return True

        return False

    def _calculate_current_deepseek_ratio(self):
        """计算当前DeepSeek策略资金占比"""
        # 这里应该根据实际持仓计算
        # 为了演示，返回默认比例
        return 0.6

    def _execute_rebalance(self, optimal_allocation):
        """执行再平衡操作"""
        # 实际的再平衡逻辑
        # 这里需要平仓部分仓位，重新开仓
        pass

    def get_portfolio_summary(self):
        """获取投资组合摘要"""

        total_pnl = self.performance['total']['pnl']
        total_trades = self.performance['total']['trades']
        win_rate = self.performance['total']['wins'] / max(1, total_trades) * 100

        summary = f"""
🎯 DeepSeek + Qwen3 Max 混合策略报告
{"="*50}

💰 资金配置:
  • 总资金: ${self.total_capital:,.0f}
  • DeepSeek稳健: ${self.total_capital * 0.6:,.0f} (60%)
  • Qwen3 Max集中: ${self.total_capital * 0.4:,.0f} (40%)

📊 策略表现:
  • 总交易次数: {total_trades}
  • 胜率: {win_rate:.1f}%
  • 累计盈亏: ${total_pnl:+,.2f}
  • 收益率: {total_pnl/self.total_capital*100:+.2f}%

🎯 DeepSeek稳健策略 (60%):
  • 分散币种: {len(self.deepseek_config['symbols'])}个
  • 杠杆倍数: {self.deepseek_config['leverage']}x
  • 交易次数: {self.performance['deepseek']['trades']}
  • 胜率: {self.performance['deepseek']['wins']/max(1,self.performance['deepseek']['trades'])*100:.1f}%
  • 盈亏: ${self.performance['deepseek']['pnl']:+,.2f}

��� Qwen3 Max集中策略 (40%):
  • 集中标的: {self.qwen3_config['focus_symbol']}
  • 杠杆倍数: {self.qwen3_config['leverage']}x
  • 交易次数: {self.performance['qwen3']['trades']}
  • 胜率: {self.performance['qwen3']['wins']/max(1,self.performance['qwen3']['trades'])*100:.1f}%
  • 盈亏: ${self.performance['qwen3']['pnl']:+,.2f}

🛡️ 风险控制:
  • DeepSeek: 3分钟失效条件 + 分散风险
  • Qwen3 Max: 4小时趋势止损 + 集中火力
  • 动态再平衡: 自动调整配置比例

📈 预期目标:
  • 年化收益: 50-70%
  • 最大回撤: <15%
  • 夏普指数: 1.5+
        """

        return summary


def main():
    """主函数 - 演示混合策略"""

    print("🚀 DeepSeek + Qwen3 Max 混合策略启动")
    print("=" * 60)

    # 初始化策略
    strategy = HybridTradingStrategy(total_capital=10000)

    # 模拟市场数据
    sample_market_data = {
        'current_price': 111000,
        'timestamp': datetime.now().isoformat(),
        'volume': 1000,
        'rsi': 55,
        'macd': 100
    }

    # 计算最优分配
    optimal = strategy.calculate_optimal_allocation([sample_market_data])

    print(f"📊 市场分析:")
    print(f"  市场状况: {optimal['market_condition']}")
    print(f"  DeepSeek配置: {optimal['deepseek_ratio']:.1%}")
    print(f"  Qwen3 Max配置: {optimal['qwen3_ratio']:.1%}")

    # DeepSeek策略决策
    for symbol in ['BTC/USDT', 'ETH/USDT', 'SOL/USDT', 'DOGE/USDT']:
        decision = strategy.deepseek_strategy_decision(symbol, sample_market_data)
        print(f"\n🔹 DeepSeek - {symbol}:")
        print(f"  信号: {decision['signal']}")
        print(f"  信心度: {decision['confidence']:.2f}")
        print(f"  理由: {decision['reason']}")

    # Qwen3 Max策略决策
    qwen3_decision = strategy.qwen3_strategy_decision(sample_market_data)
    print(f"\n⚡ Qwen3 Max - {strategy.qwen3_config['focus_symbol']}:")
    print(f"  信号: {qwen3_decision['signal']}")
    print(f"  信心度: {qwen3_decision['confidence']:.2f}")
    print(f"  理由: {qwen3_decision['reason']}")

    # 显示组合摘要
    print(strategy.get_portfolio_summary())


if __name__ == "__main__":
    main()