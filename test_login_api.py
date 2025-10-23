#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""测试登录后的API接口"""
import requests
import json
import sys
import io

# 设置控制台输出编码为UTF-8
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# 创建session保持登录状态
session = requests.Session()

# 1. 登录
print("=" * 60)
print("步骤1: 登录")
print("=" * 60)
login_response = session.post(
    'http://localhost:8888/login',
    json={'password': 'mn123456'}
)
print(f"登录状态码: {login_response.status_code}")
print(f"登录响应: {login_response.json()}")

if not login_response.json().get('success'):
    print("登录失败!")
    exit(1)

print("登录成功!\n")

# 2. 测试 /api/status 接口
print("=" * 60)
print("步骤2: 测试 /api/status 接口")
print("=" * 60)
status_response = session.get('http://localhost:8888/api/status')
print(f"状态码: {status_response.status_code}")
print(f"响应数据:")
try:
    data = status_response.json()
    print(json.dumps(data, indent=2, ensure_ascii=False))

    if data.get('success'):
        print(f"\nAPI调用成功")
        print(f"余额: {data.get('balance')} USDT")
        print(f"总盈亏: {data.get('total_pnl')} USDT")
        print(f"持仓数量: {len(data.get('positions', []))}")

        if data.get('positions'):
            print("\n持仓详情:")
            for pos in data['positions']:
                print(f"  - {pos['symbol']}: {pos['side']} {pos['size']}, 盈亏: {pos['unrealized_pnl']} USDT")
        else:
            print("\n持仓列表为空!")
    else:
        print(f"\nAPI返回失败: {data.get('error')}")
except Exception as e:
    print(f"解析响应失败: {e}")
    print(f"原始响应: {status_response.text}")
