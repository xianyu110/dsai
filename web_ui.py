from flask import Flask, render_template, jsonify, request
import json
import os
import ccxt
from datetime import datetime
from dotenv import load_dotenv
import threading
import time
from collections import deque
import subprocess
import signal

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

# 策略进程管理
strategy_processes = {}

# 可用策略列表
AVAILABLE_STRATEGIES = {
    'deepseek': {
        'name': 'DeepSeek AI 策略',
        'description': '基于 DeepSeek AI 的多币种交易策略',
        'script': 'deepseek.py',
        'status': 'stopped',
        'auto_start': False,
        'mode': 'live'  # 实盘
    },
    'grok': {
        'name': 'Grok AI 策略 [模拟盘]',
        'description': '基于 Grok AI 的市场分析和技术指标交易（安全测试）',
        'script': 'grok_strategy.py',
        'status': 'stopped',
        'auto_start': False,
        'mode': 'simulated'  # 模拟盘
    },
    'reverse_gpt5': {
        'name': 'GPT-5 反向跟单 [模拟盘]',
        'description': 'GPT-5 做多我们做空，GPT-5 做空我们做多（安全测试，不真实交易）',
        'script': 'reverse_gpt5.py',
        'status': 'stopped',
        'auto_start': False,
        'mode': 'simulated'  # 模拟盘
    }
}

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/strategy_demo')
def strategy_demo():
    """策略管理页面"""
    return render_template('strategy_demo.html')

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

                    add_trade_log(
                        'analysis',
                        symbol,
                        'auto_trade',
                        f"AI信号: {signal_data['signal']} (信心: {signal_data['confidence']})",
                        success=True,
                        details={
                            'signal': signal_data['signal'],
                            'confidence': signal_data['confidence'],
                            'reason': signal_data.get('reason', '')
                        }
                    )

                    # 执行交易（使用合约交易逻辑）
                    trade_events = execute_trade(signal_data, price_data) or []
                    for event in trade_events:
                        event_symbol = event.get('symbol', symbol)
                        add_trade_log(
                            event.get('type', 'trade'),
                            event_symbol,
                            event.get('action', 'auto_trade'),
                            event.get('message', ''),
                            success=event.get('success', True),
                            details=event.get('details')
                        )
                        if event.get('message'):
                            print(f"  📋 {event['message']}")

                except Exception as e:
                    print(f"  ❌ {symbol} 处理失败: {e}")

                # 避免请求过快
                time.sleep(2)

            # 等待下一轮(3分钟)
            print(f"\n⏰ 等待下一轮分析 (3分钟)...")
            time.sleep(3 * 60)

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
        auto_execute = data.get('auto_execute', False)  # 是否自动执行交易

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

        # 如果启用自动执行，则根据信号执行交易
        trade_executed = False
        trade_message = ''
        if auto_execute and signal_data['signal'] in ['BUY', 'SELL']:
            try:
                trade_events = execute_trade(signal_data, price_data) or []
                for event in trade_events:
                    event_symbol = event.get('symbol', symbol)
                    add_trade_log(
                        event.get('type', 'trade'),
                        event_symbol,
                        event.get('action', 'manual_trade'),
                        event.get('message', ''),
                        success=event.get('success', True),
                        details=event.get('details')
                    )
                    if event.get('message'):
                        trade_message += event['message'] + ' '
                trade_executed = True
            except Exception as e:
                trade_message = f'执行交易失败: {str(e)}'
                add_trade_log('trade', symbol, 'auto_trade', trade_message, success=False)

        return jsonify({
            'success': True,
            'message': f'{symbol} AI分析完成' + (f' - {trade_message}' if trade_executed else ''),
            'signal_data': signal_data,
            'price_data': price_data,
            'position': current_position,
            'trade_executed': trade_executed,
            'trade_message': trade_message,
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

@app.route('/api/config', methods=['GET'])
def get_config():
    """获取当前环境变量配置（脱敏）"""
    try:
        config = {
            'exchange_type': os.getenv('EXCHANGE_TYPE', 'okx'),
            'okx_api_key': '***' + (os.getenv('OKX_API_KEY', '')[-4:] if os.getenv('OKX_API_KEY') else ''),
            'okx_secret': '***' if os.getenv('OKX_SECRET') else '',
            'okx_password': '***' if os.getenv('OKX_PASSWORD') else '',
            'binance_api_key': '***' + (os.getenv('BINANCE_API_KEY', '')[-4:] if os.getenv('BINANCE_API_KEY') else ''),
            'binance_secret': '***' if os.getenv('BINANCE_SECRET') else '',
            'ai_model': os.getenv('AI_MODEL', 'deepseek'),
            'use_relay_api': os.getenv('USE_RELAY_API', 'false').lower() == 'true',
            'relay_api_base_url': os.getenv('RELAY_API_BASE_URL', ''),
            'relay_api_key': '***' if os.getenv('RELAY_API_KEY') else '',
            'deepseek_api_key': '***' if os.getenv('DEEPSEEK_API_KEY') else '',
            'grok_api_key': '***' if os.getenv('GROK_API_KEY') else '',
            'claude_api_key': '***' if os.getenv('CLAUDE_API_KEY') else '',
            'http_proxy': os.getenv('HTTP_PROXY', ''),
            'https_proxy': os.getenv('HTTPS_PROXY', ''),
            'symbols': os.getenv('SYMBOLS', 'BTC/USDT,ETH/USDT'),
            'amount_usd': os.getenv('AMOUNT_USD', '100'),
            'leverage': os.getenv('LEVERAGE', '5'),
            'has_config': os.path.exists('.env')
        }
        return jsonify({'success': True, 'config': config})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/config', methods=['POST'])
def update_config():
    """更新环境变量配置"""
    try:
        data = request.json

        # 读取现有的.env文件
        env_path = '.env'
        env_content = {}

        if os.path.exists(env_path):
            with open(env_path, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#') and '=' in line:
                        key, value = line.split('=', 1)
                        env_content[key.strip()] = value.strip()

        # 更新配置（只更新提供的字段）
        if 'exchange_type' in data:
            env_content['EXCHANGE_TYPE'] = data['exchange_type']

        # OKX配置
        if 'okx_api_key' in data and data['okx_api_key'] and not data['okx_api_key'].startswith('***'):
            env_content['OKX_API_KEY'] = data['okx_api_key']
        if 'okx_secret' in data and data['okx_secret'] and data['okx_secret'] != '***':
            env_content['OKX_SECRET'] = data['okx_secret']
        if 'okx_password' in data and data['okx_password'] and data['okx_password'] != '***':
            env_content['OKX_PASSWORD'] = data['okx_password']

        # Binance配置
        if 'binance_api_key' in data and data['binance_api_key'] and not data['binance_api_key'].startswith('***'):
            env_content['BINANCE_API_KEY'] = data['binance_api_key']
        if 'binance_secret' in data and data['binance_secret'] and data['binance_secret'] != '***':
            env_content['BINANCE_SECRET'] = data['binance_secret']

        # AI配置
        if 'ai_model' in data:
            env_content['AI_MODEL'] = data['ai_model']
        if 'use_relay_api' in data:
            env_content['USE_RELAY_API'] = 'true' if data['use_relay_api'] else 'false'
        if 'relay_api_base_url' in data:
            env_content['RELAY_API_BASE_URL'] = data['relay_api_base_url']
        if 'relay_api_key' in data and data['relay_api_key'] and data['relay_api_key'] != '***':
            env_content['RELAY_API_KEY'] = data['relay_api_key']
        if 'deepseek_api_key' in data and data['deepseek_api_key'] and data['deepseek_api_key'] != '***':
            env_content['DEEPSEEK_API_KEY'] = data['deepseek_api_key']
        if 'grok_api_key' in data and data['grok_api_key'] and data['grok_api_key'] != '***':
            env_content['GROK_API_KEY'] = data['grok_api_key']
        if 'claude_api_key' in data and data['claude_api_key'] and data['claude_api_key'] != '***':
            env_content['CLAUDE_API_KEY'] = data['claude_api_key']

        # 代理配置
        if 'http_proxy' in data:
            env_content['HTTP_PROXY'] = data['http_proxy']
        if 'https_proxy' in data:
            env_content['HTTPS_PROXY'] = data['https_proxy']

        # 交易配置
        if 'symbols' in data:
            env_content['SYMBOLS'] = data['symbols']
        if 'amount_usd' in data:
            env_content['AMOUNT_USD'] = str(data['amount_usd'])
        if 'leverage' in data:
            env_content['LEVERAGE'] = str(data['leverage'])

        # 写入.env文件
        with open(env_path, 'w', encoding='utf-8') as f:
            f.write('# AI 模型配置\n')
            f.write('# 可选: deepseek, grok, claude\n')
            f.write(f'AI_MODEL={env_content.get("AI_MODEL", "deepseek")}\n\n')

            f.write('# 是否使用中转API (true/false)\n')
            f.write(f'USE_RELAY_API={env_content.get("USE_RELAY_API", "false")}\n\n')

            f.write('# 中转 API 配置\n')
            f.write(f'RELAY_API_BASE_URL={env_content.get("RELAY_API_BASE_URL", "")}\n')
            f.write(f'RELAY_API_KEY={env_content.get("RELAY_API_KEY", "")}\n\n')

            f.write('# 官方 API 配置\n')
            f.write(f'DEEPSEEK_API_KEY={env_content.get("DEEPSEEK_API_KEY", "")}\n')
            f.write(f'GROK_API_KEY={env_content.get("GROK_API_KEY", "")}\n')
            f.write(f'CLAUDE_API_KEY={env_content.get("CLAUDE_API_KEY", "")}\n\n')

            f.write('# 选择交易所\n')
            f.write(f'EXCHANGE_TYPE={env_content.get("EXCHANGE_TYPE", "okx")}\n\n')

            f.write('# 代理设置 (如果需要访问 OKX)\n')
            f.write('# 格式: http://127.0.0.1:7890 或 socks5://127.0.0.1:1080\n')
            f.write(f'HTTP_PROXY={env_content.get("HTTP_PROXY", "")}\n')
            f.write(f'HTTPS_PROXY={env_content.get("HTTPS_PROXY", "")}\n\n')

            f.write('# 欧易配置 (按下方步骤获取)\n')
            f.write(f'OKX_API_KEY={env_content.get("OKX_API_KEY", "")}\n')
            f.write(f'OKX_SECRET={env_content.get("OKX_SECRET", "")}\n')
            f.write(f'OKX_PASSWORD={env_content.get("OKX_PASSWORD", "")}\n\n')

            f.write('# 币安配置 (暂不使用)\n')
            f.write(f'BINANCE_API_KEY={env_content.get("BINANCE_API_KEY", "")}\n')
            f.write(f'BINANCE_SECRET={env_content.get("BINANCE_SECRET", "")}\n\n')

        add_trade_log('system', 'CONFIG', 'update', '配置已更新，需要重启应用生效', success=True)

        return jsonify({
            'success': True,
            'message': '配置已保存，请重启应用使配置生效',
            'restart_required': True
        })
    except Exception as e:
        add_trade_log('system', 'CONFIG', 'update', f'配置更新失败: {str(e)}', success=False)
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

@app.route('/api/strategies')
def get_strategies():
    """获取所有可用策略"""
    try:
        strategies_list = []
        for strategy_id, strategy_info in AVAILABLE_STRATEGIES.items():
            # 检查进程状态
            if strategy_id in strategy_processes:
                proc = strategy_processes[strategy_id]
                if proc.poll() is None:
                    strategy_info['status'] = 'running'
                else:
                    strategy_info['status'] = 'stopped'
                    del strategy_processes[strategy_id]

            strategies_list.append({
                'id': strategy_id,
                **strategy_info
            })

        return jsonify({
            'success': True,
            'strategies': strategies_list,
            'timestamp': datetime.now().isoformat()
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/strategy/<strategy_id>/start', methods=['POST'])
def start_strategy(strategy_id):
    """启动策略"""
    try:
        if strategy_id not in AVAILABLE_STRATEGIES:
            return jsonify({'success': False, 'error': '策略不存在'})

        strategy = AVAILABLE_STRATEGIES[strategy_id]

        # 检查是否已经在运行
        if strategy_id in strategy_processes:
            proc = strategy_processes[strategy_id]
            if proc.poll() is None:
                return jsonify({'success': False, 'error': '策略已在运行中'})

        # 启动策略进程
        script_path = strategy['script']
        if not os.path.exists(script_path):
            return jsonify({'success': False, 'error': f'策略文件不存在: {script_path}'})

        proc = subprocess.Popen(
            ['python3', script_path],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            preexec_fn=os.setsid  # 创建新的进程组
        )

        strategy_processes[strategy_id] = proc
        strategy['status'] = 'running'

        add_trade_log('system', 'STRATEGY', 'start', f'{strategy["name"]} 已启动', success=True)

        return jsonify({
            'success': True,
            'message': f'{strategy["name"]} 已启动',
            'strategy_id': strategy_id,
            'pid': proc.pid
        })
    except Exception as e:
        add_trade_log('system', 'STRATEGY', 'start', f'启动策略失败: {str(e)}', success=False)
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/strategy/<strategy_id>/stop', methods=['POST'])
def stop_strategy(strategy_id):
    """停止策略"""
    try:
        if strategy_id not in AVAILABLE_STRATEGIES:
            return jsonify({'success': False, 'error': '策略不存在'})

        strategy = AVAILABLE_STRATEGIES[strategy_id]

        # 检查进程是否存在
        if strategy_id not in strategy_processes:
            strategy['status'] = 'stopped'
            return jsonify({'success': False, 'error': '策略未在运行'})

        proc = strategy_processes[strategy_id]

        # 尝试优雅地终止进程
        try:
            os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
            time.sleep(2)

            # 如果还没停止，强制终止
            if proc.poll() is None:
                os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
        except:
            proc.terminate()
            time.sleep(1)
            if proc.poll() is None:
                proc.kill()

        del strategy_processes[strategy_id]
        strategy['status'] = 'stopped'

        add_trade_log('system', 'STRATEGY', 'stop', f'{strategy["name"]} 已停止', success=True)

        return jsonify({
            'success': True,
            'message': f'{strategy["name"]} 已停止',
            'strategy_id': strategy_id
        })
    except Exception as e:
        add_trade_log('system', 'STRATEGY', 'stop', f'停止策略失败: {str(e)}', success=False)
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/strategy/<strategy_id>/logs')
def get_strategy_logs(strategy_id):
    """获取策略日志（最近20条）"""
    try:
        # 从 trade_logs 中筛选该策略的日志
        strategy_logs = [log for log in trade_logs if log.get('strategy_id') == strategy_id]
        return jsonify({
            'success': True,
            'logs': list(strategy_logs)[-20:],
            'timestamp': datetime.now().isoformat()
        })
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
