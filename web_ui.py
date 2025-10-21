from flask import Flask, render_template, jsonify, request
import json
import os
from datetime import datetime
from deepseek import (
    TRADE_CONFIG, get_current_position, get_ohlcv,
    price_history, signal_history, positions, exchange
)

app = Flask(__name__)

@app.route('/')
def index():
    return render_template('index.html')

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
                if pos['side'] == 'long':
                    exchange.create_market_sell_order(symbol, pos['size'])
                else:
                    exchange.create_market_buy_order(symbol, pos['size'])
                return jsonify({'success': True, 'message': '平仓成功'})
            return jsonify({'success': False, 'error': '无持仓'})

        elif action == 'buy':
            price_data = get_ohlcv(symbol)
            amount_crypto = amount / price_data['price']
            exchange.create_market_buy_order(symbol, amount_crypto)
            return jsonify({'success': True, 'message': '开多成功'})

        elif action == 'sell':
            price_data = get_ohlcv(symbol)
            amount_crypto = amount / price_data['price']
            exchange.create_market_sell_order(symbol, amount_crypto)
            return jsonify({'success': True, 'message': '开空成功'})

        return jsonify({'success': False, 'error': '无效操作'})

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8888, debug=True)
