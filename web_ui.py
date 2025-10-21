from flask import Flask, render_template, jsonify, request
import json
import os
import ccxt
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()
from deepseek import (
    TRADE_CONFIG, get_current_position, get_ohlcv,
    price_history, signal_history, positions, exchange,
    analyze_with_ai, execute_trade, EXCHANGE_TYPE
)

app = Flask(__name__)

@app.route('/')
def index():
    return render_template('index.html')

def get_spot_balance():
    """获取现货账户余额"""
    try:
        # 创建现货交易所实例
        if EXCHANGE_TYPE == 'okx':
            spot_exchange = ccxt.okx({
                'options': {'defaultType': 'spot'},
                'apiKey': os.getenv('OKX_API_KEY'),
                'secret': os.getenv('OKX_SECRET'),
                'password': os.getenv('OKX_PASSWORD'),
                'enableRateLimit': True,
            })
        else:  # binance
            spot_exchange = ccxt.binance({
                'options': {'defaultType': 'spot'},
                'apiKey': os.getenv('BINANCE_API_KEY'),
                'secret': os.getenv('BINANCE_SECRET'),
                'enableRateLimit': True,
            })

        balance = spot_exchange.fetch_balance()
        return balance
    except Exception as e:
        print(f"获取现货余额失败: {e}")
        return None

@app.route('/api/spot_balance')
def get_spot_balance_api():
    """获取现货余额API"""
    try:
        spot_balances = get_spot_balance()
        if spot_balances:
            # 过滤出有余额的币种
            non_zero_balances = {}
            for currency, balance_info in spot_balances['total'].items():
                if float(balance_info) > 0:
                    non_zero_balances[currency] = {
                        'total': float(balance_info),
                        'free': float(spot_balances['free'][currency]),
                        'used': float(spot_balances['used'][currency])
                    }

            return jsonify({
                'success': True,
                'balances': non_zero_balances,
                'timestamp': datetime.now().isoformat()
            })
        else:
            return jsonify({'success': False, 'error': '无法获取现货余额'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/status')
def get_status():
    """获取整体状态"""
    try:
        balance = exchange.fetch_balance()
        usdt_balance = balance['USDT']['free']

        # 获取所有持仓(支持多持仓)
        all_positions = []
        total_pnl = 0
        for symbol in TRADE_CONFIG['symbols']:
            pos = get_current_position(symbol)
            if pos:
                # 处理单个持仓或多个持仓
                if isinstance(pos, list):
                    for p in pos:
                        all_positions.append(p)
                        total_pnl += p['unrealized_pnl']
                else:
                    all_positions.append(pos)
                    total_pnl += pos['unrealized_pnl']

        return jsonify({
            'success': True,
            'balance': usdt_balance,
            'total_pnl': total_pnl,
            'positions': all_positions,
            'config': TRADE_CONFIG,
            'timestamp': datetime.now().isoformat()
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/market/<path:symbol>')
def get_market_data(symbol):
    """获取市场数据"""
    try:
        price_data = get_ohlcv(symbol)
        return jsonify({
            'success': True,
            'data': price_data
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/history/<path:symbol>')
def get_history(symbol):
    """获取历史信号"""
    try:
        return jsonify({
            'success': True,
            'price_history': price_history.get(symbol, [])[-20:],
            'signal_history': signal_history.get(symbol, [])[-20:]
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/analysis', methods=['POST'])
def manual_analysis():
    """手动触发AI分析"""
    try:
        data = request.json
        symbol = data.get('symbol')

        if not symbol:
            return jsonify({'success': False, 'error': '请指定交易对'})

        if symbol not in TRADE_CONFIG['symbols']:
            return jsonify({'success': False, 'error': f'不支持的交易对: {symbol}'})

        # 获取市场数据
        price_data = get_ohlcv(symbol)
        if not price_data:
            return jsonify({'success': False, 'error': f'获取{symbol}市场数据失败'})

        # 执行AI分析
        signal_data = analyze_with_ai(price_data)
        if not signal_data:
            return jsonify({'success': False, 'error': f'AI分析{symbol}失败'})

        # 获取当前持仓
        current_position = get_current_position(symbol)

        return jsonify({
            'success': True,
            'message': f'{symbol} AI分析完成',
            'signal_data': signal_data,
            'price_data': price_data,
            'position': current_position,
            'timestamp': datetime.now().isoformat()
        })

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/execute', methods=['POST'])
def manual_execute():
    """手动执行交易"""
    try:
        data = request.json
        symbol = data.get('symbol')
        action = data.get('action')  # buy/sell/close
        amount = data.get('amount', TRADE_CONFIG['amount_usd'])

        if action == 'close':
            pos = get_current_position(symbol)
            if pos:
                try:
                    # 合约平仓：使用position side参数
                    if pos['side'] == 'long':
                        # 平多仓：卖出
                        exchange.create_market_order(symbol, 'sell', pos['size'], None, {'reduceOnly': True})
                    else:
                        # 平空仓：买入
                        exchange.create_market_order(symbol, 'buy', pos['size'], None, {'reduceOnly': True})
                    return jsonify({'success': True, 'message': '平仓成功'})
                except Exception as e:
                    return jsonify({'success': False, 'error': f'平仓失败: {str(e)}'})
            return jsonify({'success': False, 'error': '无持仓'})

        elif action == 'buy':
            price_data = get_ohlcv(symbol)
            amount_crypto = amount / price_data['price']
            # 合约开多仓
            exchange.create_market_order(symbol, 'buy', amount_crypto)
            return jsonify({'success': True, 'message': '开多成功'})

        elif action == 'sell':
            price_data = get_ohlcv(symbol)
            amount_crypto = amount / price_data['price']
            # 合约开空仓
            exchange.create_market_order(symbol, 'sell', amount_crypto)
            return jsonify({'success': True, 'message': '开空成功'})

        return jsonify({'success': False, 'error': '无效操作'})

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8888, debug=True)
