#!/usr/bin/env python3
"""
部署DeepSeek + Qwen3 Max混合策略
基于现有deepseek.py架构的升级版本
"""

# 从现有deepseek.py导入核心功能
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from deepseek import (
    setup_exchange, get_ohlcv, get_current_position,
    analyze_15m_trend, analyze_4h_trend, get_multi_timeframe_analysis,
    send_log_to_web_ui, execute_trade, check_kline_close,
    update_trade_performance, get_sharpe_analysis,
    price_history, signal_history, trade_performance,
    portfolio_returns, trend_analysis
)

from datetime import datetime
import json

class HybridStrategyDeployer:
    """混合策略部署器"""

    def __init__(self):
        self.total_capital = 10000  # 可配置初始资金

        # 资金分配 (60% DeepSeek + 40% Qwen3 Max)
        self.allocation = {
            'deepseek': 0.6,
            'qwen3_max': 0.4
        }

        # DeepSeek配置 (稳健分散)
        self.deepseek_config = {
            'symbols': ['BTC/USDT', 'ETH/USDT', 'SOL/USDT', 'DOGE/USDT'],
            'leverage': 10,
            'amount_per_trade': 300,
            'invalidation_levels': {
                'BTC/USDT': 105000,
                'ETH/USDT': 3800,
                'SOL/USDT': 175,
                'DOGE/USDT': 0.180
            }
        }

        # Qwen3 Max配置 (集中火力)
        self.qwen3_config = {
            'focus_symbol': 'BTC/USDT',
            'leverage': 20,
            'amount_per_trade': 400,
            'invalidation_level': 105000  # 4小时趋势止损
        }

        self.last_rebalance = datetime.now()
        self.rebalance_hours = 24  # 24小时再平衡一次

    def should_rebalance(self):
        """检查是否需要再平衡"""
        hours_since_rebalance = (datetime.now() - self.last_rebalance).total_seconds() / 3600
        return hours_since_rebalance >= self.rebalance_hours

    def execute_hybrid_strategy(self):
        """执行混合策略主逻辑"""

        print(f"\n🚀 DeepSeek + Qwen3 Max 混合策略执行")
        print(f"执行时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 60)

        # 1. 检��再平衡
        if self.should_rebalance():
            self.perform_rebalance()

        # 2. 执行DeepSeek稳健策略
        deepseek_results = self.execute_deepseek_strategy()

        # 3. 执行Qwen3 Max集中策略
        qwen3_results = self.execute_qwen3_strategy()

        # 4. 汇总结果
        self.report_performance(deepseek_results, qwen3_results)

    def execute_deepseek_strategy(self):
        """执行DeepSeek稳健策略"""

        print(f"\n🔹 DeepSeek稳健策略执行 (60%资金)")
        print("-" * 40)

        results = []

        for symbol in self.deepseek_config['symbols']:
            print(f"\n分析 {symbol}:")

            # 获取市场数据
            price_data = get_ohlcv(symbol)
            if not price_data:
                print(f"  ❌ 无法获取数据")
                continue

            # 多时间周期分析
            mt_analysis = get_multi_timeframe_analysis(symbol)

            # DeepSeek决策逻辑
            decision = self.make_deepseek_decision(symbol, price_data, mt_analysis)

            print(f"  决策: {decision['signal']}")
            print(f"  信心度: {decision['confidence']:.2f}")
            print(f"  理由: {decision['reason']}")

            # 执行交易
            if decision['signal'] in ['BUY', 'SELL', 'CLOSE']:
                trade_result = self.execute_trade_with_config(
                    symbol, decision, self.deepseek_config
                )
                results.append(trade_result)

        return results

    def execute_qwen3_strategy(self):
        """执行Qwen3 Max集中策略"""

        print(f"\n⚡ Qwen3 Max集中策略执行 (40%资金)")
        print("-" * 40)

        symbol = self.qwen3_config['focus_symbol']

        print(f"专注标的: {symbol}")

        # 获取市场数据
        price_data = get_ohlcv(symbol)
        if not price_data:
            print(f"  ❌ 无法获取数据")
            return []

        # 多时间周期分析
        mt_analysis = get_multi_timeframe_analysis(symbol)

        # Qwen3 Max决策逻辑 (简化但有效)
        decision = self.make_qwen3_decision(symbol, price_data, mt_analysis)

        print(f"决策: {decision['signal']}")
        print(f"信心度: {decision['confidence']:.2f}")
        print(f"理由: {decision['reason']}")

        # 执行交易
        if decision['signal'] in ['BUY', 'SELL', 'CLOSE']:
            trade_result = self.execute_trade_with_config(
                symbol, decision, self.qwen3_config
            )
            return [trade_result]

        return []

    def make_deepseek_decision(self, symbol, price_data, mt_analysis):
        """DeepSeek决策逻辑"""

        current_position = get_current_position(symbol)

        if current_position:
            # 持仓管理
            current_price = price_data['price']

            # 第一层: 3分钟失效条件
            should_close, reason = check_kline_close(symbol)
            if should_close:
                return {
                    'signal': 'CLOSE',
                    'confidence': 1.0,
                    'reason': f'失效条件触发: {reason}',
                    'stop_loss': current_price * 0.95
                }

            # 第二层: 15分钟趋势保护
            trend_15m = mt_analysis['15m']['trend']
            position_side = 'long' if current_position.get('side') == 'long' else 'short'

            if position_side == 'long' and trend_15m == 'bearish':
                if mt_analysis['15m']['details'].get('trend_strength') == 'strong':
                    return {
                        'signal': 'CLOSE',
                        'confidence': 0.8,
                        'reason': '15分钟强烈看跌趋势，保护利润',
                        'stop_loss': current_price * 0.98
                    }

            # 第三层: 4小时趋势跟随保护
            trend_4h = mt_analysis['4h']['trend']
            if position_side == 'long' and trend_4h == 'bullish':
                return {
                    'signal': 'HOLD',
                    'confidence': 0.9,
                    'reason': '4小时看涨趋势保护，让利润奔跑',
                    'stop_loss': None
                }

            return {
                'signal': 'HOLD',
                'confidence': 0.7,
                'reason': '继续持有，监控趋势变化',
                'stop_loss': None
            }

        else:
            # 开仓决策
            trend_15m = mt_analysis['15m']['trend']
            trend_4h = mt_analysis['4h']['trend']
            confidence = mt_analysis['confidence']

            # 多时间周期确认
            if trend_15m == 'bullish' and trend_4h in ['bullish', 'neutral']:
                return {
                    'signal': 'BUY',
                    'confidence': confidence,
                    'reason': f'多时间周期看涨确认: 15分钟{trend_15m}, 4小时{trend_4h}',
                    'take_profit': price_data['price'] * 1.1,
                    'stop_loss': price_data['price'] * 0.95
                }

            return {
                'signal': 'HOLD',
                'confidence': 0.5,
                'reason': '信号不明确，等待更好的入场时机',
                'stop_loss': None
            }

    def make_qwen3_decision(self, symbol, price_data, mt_analysis):
        """Qwen3 Max决策逻辑 - 简单有效"""

        current_position = get_current_position(symbol)
        current_price = price_data['price']

        if current_position:
            # Qwen3 Max的核心: 4小时趋势止损
            invalidation_level = self.qwen3_config['invalidation_level']

            if current_price < invalidation_level:
                return {
                    'signal': 'CLOSE',
                    'confidence': 1.0,
                    'reason': f'Qwen3策略: 4小时收盘{current_price:.0f} < 关键支撑{invalidation_level}',
                    'stop_loss': current_price * 0.98
                }

            # 让利润奔跑 - 不设止盈
            entry_price = current_position.get('entry_price', 0)
            if entry_price > 0:
                profit_pct = (current_price - entry_price) / entry_price

                if profit_pct > 0.30:  # 盈利30%以上
                    return {
                        'signal': 'HOLD',
                        'confidence': 0.9,
                        'reason': f'盈利{profit_pct*100:.1f}%，Qwen3策略继续持有让利润奔跑',
                        'stop_loss': None
                    }

            return {
                'signal': 'HOLD',
                'confidence': 0.8,
                'reason': 'Qwen3策略：趋势继续，集中火力持有',
                'stop_loss': None
            }

        else:
            # Qwen3 Max开仓逻辑 - 简单有效
            trend_4h = mt_analysis['4h']['trend']

            # 关键技术位判断
            if current_price > 106000:  # 突破关键阻力
                return {
                    'signal': 'BUY',
                    'confidence': 0.8,
                    'reason': f'Qwen3策略: 价格{current_price:.0f}突破关键阻力位106000',
                    'take_profit': current_price * 1.3,
                    'stop_loss': invalidation_level
                }
            elif current_price < 98000:  # 接近强支撑
                return {
                    'signal': 'BUY',
                    'confidence': 0.7,
                    'reason': f'Qwen3策略: 价格{current_price:.0f}接近强支撑位98000',
                    'take_profit': current_price * 1.25,
                    'stop_loss': current_price * 0.95
                }

            return {
                'signal': 'HOLD',
                'confidence': 0.5,
                'reason': 'Qwen3策略：观望等待突破关键位',
                'stop_loss': None
            }

    def execute_trade_with_config(self, symbol, decision, config):
        """根据配置执行交易"""

        # 构造信号数据
        signal_data = {
            'signal': decision['signal'],
            'confidence': decision['confidence'],
            'reason': decision['reason'],
            'stop_loss': decision.get('stop_loss'),
            'take_profit': decision.get('take_profit')
        }

        # 构造价格数据
        price_data = get_ohlcv(symbol)
        if not price_data:
            return {'success': False, 'reason': '无法获取价格数据'}

        # 执行交易 (复用现有execute_trade函数)
        try:
            events = execute_trade(signal_data, price_data)
            return {
                'success': True,
                'symbol': symbol,
                'strategy': 'deepseek' if config == self.deepseek_config else 'qwen3',
                'decision': decision,
                'events': events
            }
        except Exception as e:
            return {
                'success': False,
                'symbol': symbol,
                'strategy': 'deepseek' if config == self.deepseek_config else 'qwen3',
                'error': str(e)
            }

    def perform_rebalance(self):
        """执行动态再平衡"""

        print(f"\n🔄 执行动态再平衡")
        print("-" * 30)

        # 获取当前总价值
        total_value = self.calculate_total_portfolio_value()

        # 计算新的分配比例
        current_deepseek_value = self.calculate_deepseek_value()
        current_deepseek_ratio = current_deepseek_value / total_value

        target_deepseek_ratio = self.allocation['deepseek']
        deviation = abs(current_deepseek_ratio - target_deepseek_ratio)

        if deviation > 0.1:  # 偏差超过10%
            print(f"当前DeepSeek比例: {current_deepseek_ratio:.1%}")
            print(f"目标DeepSeek比例: {target_deepseek_ratio:.1%}")
            print(f"偏差: {deviation:.1%}")
            print("执行再平衡...")

            # 这里实现具体的再平衡逻辑
            # 平仓部分仓位，重新按比例开仓
            pass
        else:
            print(f"当前配置合理，无需再平衡")

        self.last_rebalance = datetime.now()

    def calculate_total_portfolio_value(self):
        """计算投资组合总价值"""
        # 这里应该连接交易所API获取实际价值
        # 为了演示，返回模拟值
        return 10000

    def calculate_deepseek_value(self):
        """计算DeepSeek策略部分的价值"""
        # 这里应该根据实际持仓计算
        # 为了演示，返回模拟值
        return 6000

    def report_performance(self, deepseek_results, qwen3_results):
        """报告策略表现"""

        print(f"\n📊 混合策略表现报告")
        print("=" * 50)

        # 统计交易结果
        total_trades = len(deepseek_results) + len(qwen3_results)
        successful_trades = len([r for r in deepseek_results + qwen3_results if r.get('success', False)])

        print(f"总交易次数: {total_trades}")
        print(f"成功交易: {successful_trades}")
        print(f"成功率: {successful_trades/max(1,total_trades)*100:.1f}%")

        print(f"\n🔹 DeepSeek策略:")
        print(f"  交易次数: {len(deepseek_results)}")
        print(f"  成功次数: {len([r for r in deepseek_results if r.get('success', False)])}")

        print(f"\n⚡ Qwen3 Max策略:")
        print(f"  交易次数: {len(qwen3_results)}")
        print(f"  成功次数: {len([r for r in qwen3_results if r.get('success', False)])}")

        # 显示当前持仓
        print(f"\n💼 当前持仓:")
        all_symbols = set(self.deepseek_config['symbols'] + [self.qwen3_config['focus_symbol']])

        for symbol in all_symbols:
            position = get_current_position(symbol)
            if position:
                if isinstance(position, list):
                    for pos in position:
                        print(f"  {symbol}: {pos['side']}仓 {pos['size']:.6f}, 盈亏: {pos['unrealized_pnl']:.2f} USDT")
                else:
                    print(f"  {symbol}: {position['side']}仓 {position['size']:.6f}, 盈亏: {position['unrealized_pnl']:.2f} USDT")

def main():
    """主函数"""

    print("🚀 DeepSeek + Qwen3 Max 混合策略部署")
    print("=" * 60)

    # 设置交易所
    if not setup_exchange():
        print("❌ 交易所初始化失败，程序退出")
        return

    # 初始化混合策略
    strategy = HybridStrategyDeployer()

    # 执行策略
    strategy.execute_hybrid_strategy()

    print(f"\n✅ 混合策略执行完成")
    print(f"下次执行: 3分钟后")

if __name__ == "__main__":
    main()