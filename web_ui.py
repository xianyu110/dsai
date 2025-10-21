from flask import Flask, render_template, jsonify, request
import json
import os
import ccxt
from datetime import datetime
from dotenv import load_dotenv
import threading
import time
from collections import deque

load_dotenv()
from deepseek import (
    TRADE_CONFIG, get_current_position, get_ohlcv,
    price_history, signal_history, positions, exchange,
    analyze_with_ai, execute_trade, EXCHANGE_TYPE
)

app = Flask(__name__)

# 自动交易线程控制
auto_trade_thread = None
auto_trade_running = False

# 交易操作日志（最多保存100条）
trade_logs = deque(maxlen=100)

@app.route('/')
def index():
    return render_template('index.html')

def get_spot_balance():
    """获取现货账户余额"""
    try:
        # 创建现货交易所实例
        if EXCHANGE_TYPE == 'okx':
            # 配置代理
            proxies = {}
            if os.getenv('HTTP_PROXY'):
                proxies = {
                    'http': os.getenv('HTTP_PROXY'),
                    'https': os.getenv('HTTPS_PROXY', os.getenv('HTTP_PROXY')),
                }

            spot_exchange = ccxt.okx({
                'options': {'defaultType': 'spot'},
                'apiKey': os.getenv('OKX_API_KEY'),
                'secret': os.getenv('OKX_SECRET'),
                'password': os.getenv('OKX_PASSWORD'),
                'proxies': proxies,
                'enableRateLimit': True,
            })
        else:  # binance
            # 配置代理
            proxies = {}
            if os.getenv('HTTP_PROXY'):
                proxies = {
                    'http': os.getenv('HTTP_PROXY'),
                    'https': os.getenv('HTTPS_PROXY', os.getenv('HTTP_PROXY')),
                }

            spot_exchange = ccxt.binance({
                'options': {'defaultType': 'spot'},
                'apiKey': os.getenv('BINANCE_API_KEY'),
                'secret': os.getenv('BINANCE_SECRET'),
                'proxies': proxies,
                'enableRateLimit': True,
            })

        balance = spot_exchange.fetch_balance()
        print(f"成功获取现货余额，币种数量: {len([k for k, v in balance.get('total', {}).items() if float(v or 0) > 0])}")
        return balance
    except Exception as e:
        import traceback
        print(f"获取现货余额失败: {e}")
        print(f"详细错误: {traceback.format_exc()}")
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
            'auto_trade': TRADE_CONFIG.get('auto_trade', False),
            'timestamp': datetime.now().isoformat()
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

def auto_trade_worker():
    """自动交易后台任务"""
    global auto_trade_running

    print("🤖 自动交易线程已启动")

    while auto_trade_running and TRADE_CONFIG.get('auto_trade', False):
        try:
            print(f"\n{'='*60}")
            print(f"🔄 开始新一轮自动交易分析 - {datetime.now().strftime('%H:%M:%S')}")
            print(f"{'='*60}")

            for symbol in TRADE_CONFIG['symbols']:
                if not TRADE_CONFIG.get('auto_trade', False):
                    break

                try:
                    print(f"\n📊 分析 {symbol}...")

                    # 获取市场数据
                    price_data = get_ohlcv(symbol)
                    if not price_data:
                        print(f"  ⚠️  无法获取{symbol}市场数据")
                        continue

                    # AI分析
                    signal_data = analyze_with_ai(price_data)
                    if not signal_data:
                        print(f"  ⚠️  {symbol} AI分析失败")
                        continue

                    print(f"  📈 信号: {signal_data['signal']}")
                    print(f"  💪 信心: {signal_data['confidence']}")
                    print(f"  📝 理由: {signal_data['reason']}")

                    # 执行交易
                    result = execute_trade(symbol, price_data, signal_data)
                    if result:
                        print(f"  ✅ {result}")

                except Exception as e:
                    print(f"  ❌ {symbol} 处理失败: {e}")

                # 避免请求过快
                time.sleep(2)

            # 等待下一轮(15分钟)
            print(f"\n⏰ 等待下一轮分析 (15分钟)...")
            time.sleep(15 * 60)

        except Exception as e:
            print(f"❌ 自动交易循环错误: {e}")
            time.sleep(60)

    print("🛑 自动交易线程已停止")

@app.route('/api/auto_trade', methods=['POST'])
def toggle_auto_trade():
    """切换自动交易状态"""
    global auto_trade_thread, auto_trade_running

    try:
        data = request.json
        enable = data.get('enable', False)

        # 更新配置
        TRADE_CONFIG['auto_trade'] = enable

        if enable:
            # 启动自动交易线程
            if auto_trade_thread is None or not auto_trade_thread.is_alive():
                auto_trade_running = True
                auto_trade_thread = threading.Thread(target=auto_trade_worker, daemon=True)
                auto_trade_thread.start()
                status = "启用"
            else:
                status = "已在运行"
        else:
            # 停止自动交易
            auto_trade_running = False
            status = "禁用"

        # 记录日志
        print(f"{'='*50}")
        print(f"⚙️  自动交易已{status}")
        print(f"⏰ 时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"{'='*50}")

        return jsonify({
            'success': True,
            'auto_trade': enable,
            'message': f'自动交易已{status}',
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
            add_trade_log('analysis', symbol, 'analyze', f'AI分析失败', success=False)
            return jsonify({'success': False, 'error': f'AI分析{symbol}失败'})

        # 获取当前持仓
        current_position = get_current_position(symbol)

        # 记录分析日志
        add_trade_log('analysis', symbol, 'analyze',
                    f'AI分析完成: {signal_data["signal"]} (信心: {signal_data["confidence"]})',
                    success=True,
                    details={'signal': signal_data['signal'], 'confidence': signal_data['confidence'], 'reason': signal_data.get('reason', '')})

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

@app.route('/api/orders/<path:symbol>')
def get_recent_orders(symbol):
    """获取最近的订单"""
    try:
        # OKX合约需要使用 BTC/USDT:USDT 格式
        trade_symbol = symbol
        if EXCHANGE_TYPE == 'okx' and ':' not in symbol:
            trade_symbol = f"{symbol}:USDT"

        # OKX需要分别获取开仓和已平仓订单
        open_orders = exchange.fetch_open_orders(trade_symbol)
        closed_orders = exchange.fetch_closed_orders(trade_symbol, limit=10)

        # 合并订单
        all_orders = open_orders + closed_orders
        # 按时间排序
        all_orders.sort(key=lambda x: x.get('timestamp', 0), reverse=True)

        return jsonify({
            'success': True,
            'orders': all_orders[:10],
            'timestamp': datetime.now().isoformat()
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

def add_trade_log(log_type, symbol, action, message, success=True, details=None):
    """添加交易日志"""
    log_entry = {
        'timestamp': datetime.now().isoformat(),
        'type': log_type,  # 'trade', 'analysis', 'system'
        'symbol': symbol,
        'action': action,  # 'buy', 'sell', 'close', 'analyze'
        'message': message,
        'success': success,
        'details': details or {}
    }
    trade_logs.append(log_entry)
    print(f"[日志] {log_entry['timestamp']} - {message}")

@app.route('/api/logs')
def get_trade_logs():
    """获取交易日志"""
    try:
        return jsonify({
            'success': True,
            'logs': list(trade_logs),
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
        leverage = data.get('leverage', 5)  # 默认5倍杠杆

        # 保存原始symbol用于查询持仓
        original_symbol = symbol

        # OKX合约需要使用 BTC/USDT:USDT 格式
        trade_symbol = symbol
        if EXCHANGE_TYPE == 'okx' and ':' not in symbol:
            trade_symbol = f"{symbol}:USDT"

        if action == 'close':
            # 使用原始symbol查询持仓
            pos = get_current_position(original_symbol)
            if pos:
                try:
                    # 处理多个持仓的情况
                    positions_to_close = [pos] if not isinstance(pos, list) else pos

                    for position in positions_to_close:
                        # OKX双向持仓模式平仓
                        if EXCHANGE_TYPE == 'okx':
                            # OKX双向持仓模式：平仓方向与持仓方向相反
                            # 平多仓(long)：卖出(sell)，平空仓(short)：买入(buy)
                            side = 'sell' if position['side'] == 'long' else 'buy'

                            # 转换交易对格式：BNB/USDT -> BNB-USDT-SWAP
                            base_symbol = original_symbol.replace('/USDT', '')
                            okx_inst_id = f'{base_symbol}-USDT-SWAP'

                            # 使用OKX原生API平仓
                            result = exchange.private_post_trade_order({
                                'instId': okx_inst_id,
                                'tdMode': 'isolated',
                                'side': side,
                                'posSide': position['side'],
                                'ordType': 'market',
                                'sz': str(position['size'])
                            })
                            add_trade_log('trade', original_symbol, 'close',
                                        f'平仓成功: {position["side"]}仓 {position["size"]:.6f}',
                                        success=True,
                                        details={'size': position['size'], 'side': position['side'], 'pnl': position.get('unrealized_pnl', 0)})
                        else:  # Binance
                            params = {'reduceOnly': True}
                            if position['side'] == 'long':
                                exchange.create_market_order(trade_symbol, 'sell', position['size'], params)
                            else:
                                exchange.create_market_order(trade_symbol, 'buy', position['size'], params)
                            add_trade_log('trade', original_symbol, 'close',
                                        f'平仓成功: {position["side"]}仓 {position["size"]:.6f}',
                                        success=True,
                                        details={'size': position['size'], 'side': position['side'], 'pnl': position.get('unrealized_pnl', 0)})

                    return jsonify({'success': True, 'message': '平仓成功'})
                except Exception as e:
                    add_trade_log('trade', original_symbol, 'close', f'平仓失败: {str(e)}', success=False)
                    return jsonify({'success': False, 'error': f'平仓失败: {str(e)}'})
            add_trade_log('trade', original_symbol, 'close', '无持仓，无法平仓', success=False)
            return jsonify({'success': False, 'error': f'无持仓 (查询: {original_symbol})'})

        elif action == 'buy':
            price_data = get_ohlcv(original_symbol)
            current_price = price_data['price']

            # 计算合约张数（OKX）
            if EXCHANGE_TYPE == 'okx':
                # 加载市场信息获取合约面值
                exchange.load_markets()
                market = exchange.market(trade_symbol)
                contract_size = market.get('contractSize', 1)  # 每张合约的币数

                # 使用杠杆计算购买力
                buying_power = amount * leverage  # 保证金 × 杠杆 = 购买力
                coins_needed = buying_power / current_price  # 购买力 / 价格 = 币数
                amount_contracts = coins_needed / contract_size  # 币数 / 合约面值 = 张数

                print(f"开仓计算:")
                print(f"  保证金: {amount} USDT × {leverage}倍杠杆 = {buying_power} USDT购买力")
                print(f"  币数: {buying_power} USDT / ${current_price} = {coins_needed:.6f} BTC")
                print(f"  合约张数: {coins_needed:.6f} / {contract_size} = {amount_contracts:.4f} 张")
            else:
                # Binance
                buying_power = amount * leverage
                amount_contracts = buying_power / current_price

            # 合约开多仓 - 使用限价单，价格稍高于当前价以确保成交
            limit_price = current_price * 1.001  # 当前价+0.1%
            try:
                if EXCHANGE_TYPE == 'okx':
                    # 设置杠杆（使用用户选择的倍数）
                    try:
                        exchange.set_leverage(leverage, trade_symbol, params={'mgnMode': 'isolated', 'posSide': 'long'})
                        print(f"✅ 设置杠杆: {leverage}x")
                    except Exception as e:
                        print(f"设置杠杆警告: {e}")
                        pass  # 如果已经设置过杠杆会报错，忽略

                    # OKX双向持仓模式 + 逐仓模式
                    order = exchange.create_order(
                        symbol=trade_symbol,
                        type='limit',
                        side='buy',
                        amount=amount_contracts,
                        price=limit_price,
                        params={
                            'tdMode': 'isolated',  # 逐仓模式
                            'posSide': 'long'
                        }
                    )
                else:
                    # Binance先设置杠杆
                    try:
                        exchange.set_leverage(leverage, trade_symbol)
                    except Exception as e:
                        print(f"设置杠杆警告: {e}")
                    order = exchange.create_limit_order(trade_symbol, 'buy', amount_contracts, limit_price)
                add_trade_log('trade', original_symbol, 'buy',
                            f'开多成功: {amount_contracts:.4f}张 @ ${limit_price:.2f}',
                            success=True,
                            details={'amount': amount_contracts, 'price': limit_price, 'leverage': leverage})
                return jsonify({'success': True, 'message': f'开多成功（限价单，逐仓{leverage}x）', 'order': order})
            except Exception as e:
                add_trade_log('trade', original_symbol, 'buy', f'开多失败: {str(e)}', success=False)
                return jsonify({'success': False, 'error': f'开多失败: {str(e)}'})

        elif action == 'sell':
            price_data = get_ohlcv(original_symbol)
            current_price = price_data['price']

            # 计算合约张数（OKX）
            if EXCHANGE_TYPE == 'okx':
                # 加载市场信息获取合约面值
                exchange.load_markets()
                market = exchange.market(trade_symbol)
                contract_size = market.get('contractSize', 1)  # 每张合约的币数

                # 使用杠杆计算购买力
                buying_power = amount * leverage  # 保证金 × 杠杆 = 购买力
                coins_needed = buying_power / current_price  # 购买力 / 价格 = 币数
                amount_contracts = coins_needed / contract_size  # 币数 / 合约面值 = 张数

                print(f"开仓计算:")
                print(f"  保证金: {amount} USDT × {leverage}倍杠杆 = {buying_power} USDT购买力")
                print(f"  币数: {buying_power} USDT / ${current_price} = {coins_needed:.6f} BTC")
                print(f"  合约张数: {coins_needed:.6f} / {contract_size} = {amount_contracts:.4f} 张")
            else:
                # Binance
                buying_power = amount * leverage
                amount_contracts = buying_power / current_price

            # 合约开空仓 - 使用限价单，价格稍低于当前价以确保成交
            limit_price = current_price * 0.999  # 当前价-0.1%
            try:
                if EXCHANGE_TYPE == 'okx':
                    # 设置杠杆（使用用户选择的倍数）
                    try:
                        exchange.set_leverage(leverage, trade_symbol, params={'mgnMode': 'isolated', 'posSide': 'short'})
                        print(f"✅ 设置杠杆: {leverage}x")
                    except Exception as e:
                        print(f"设置杠杆警告: {e}")
                        pass  # 如果已经设置过杠杆会报错，忽略

                    # OKX双向持仓模式 + 逐仓模式
                    order = exchange.create_order(
                        symbol=trade_symbol,
                        type='limit',
                        side='sell',
                        amount=amount_contracts,
                        price=limit_price,
                        params={
                            'tdMode': 'isolated',  # 逐仓模式
                            'posSide': 'short'
                        }
                    )
                else:
                    # Binance先设置杠杆
                    try:
                        exchange.set_leverage(leverage, trade_symbol)
                    except Exception as e:
                        print(f"设置杠杆警告: {e}")
                    order = exchange.create_limit_order(trade_symbol, 'sell', amount_contracts, limit_price)
                add_trade_log('trade', original_symbol, 'sell',
                            f'开空成功: {amount_contracts:.4f}张 @ ${limit_price:.2f}',
                            success=True,
                            details={'amount': amount_contracts, 'price': limit_price, 'leverage': leverage})
                return jsonify({'success': True, 'message': f'开空成功（限价单，逐仓{leverage}x）', 'order': order})
            except Exception as e:
                add_trade_log('trade', original_symbol, 'sell', f'开空失败: {str(e)}', success=False)
                return jsonify({'success': False, 'error': f'开空失败: {str(e)}'})

        return jsonify({'success': False, 'error': '无效操作'})

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

if __name__ == '__main__':
    # Flask开发服务器配置
    # debug=True: 启用调试模式和自动重载
    # use_reloader=True: 文件变化时自动重启
    # extra_files: 监控额外的文件(静态文件和模板)
    import os
    extra_files = [
        'templates/index.html',
        'static/css/style.css',
        'static/js/app.js',
    ]
    # 只监控存在的文件
    extra_files = [f for f in extra_files if os.path.exists(f)]

    print("🚀 启动AI交易机器人Web界面...")
    print("📡 访问地址: http://localhost:8888")
    print("🔄 热重载已启用 - 修改代码将自动重启")

    app.run(
        host='0.0.0.0',
        port=8888,
        debug=True,
        use_reloader=True,
        extra_files=extra_files
    )
