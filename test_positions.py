#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os
from dotenv import load_dotenv
import ccxt
import json

load_dotenv()

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

print(f"交易所类型: {EXCHANGE_TYPE}")
print(f"正在获取所有持仓...")

try:
    all_positions = exchange.fetch_positions()
    print(f"\n总持仓数: {len(all_positions)}")

    # 过滤出有持仓的
    active_positions = [p for p in all_positions if float(p.get('contracts', 0)) > 0]
    print(f"活跃持仓数: {len(active_positions)}")

    if active_positions:
        print("\n活跃持仓详情:")
        for pos in active_positions:
            print(f"\n{'='*60}")
            print(f"Symbol: {pos.get('symbol')}")
            print(f"Contracts: {pos.get('contracts')}")
            print(f"Side: {pos.get('side')}")
            print(f"Entry Price: {pos.get('entryPrice')}")
            print(f"Unrealized PNL: {pos.get('unrealizedPnl')}")
            print(f"Info posSide: {pos.get('info', {}).get('posSide')}")
            print(f"Info lever: {pos.get('info', {}).get('lever')}")

            # 打印完整的info字段
            print(f"\n完整Info字段:")
            print(json.dumps(pos.get('info', {}), indent=2, ensure_ascii=False))
    else:
        print("\n当前没有活跃持仓")

except Exception as e:
    print(f"错误: {e}")
    import traceback
    traceback.print_exc()
