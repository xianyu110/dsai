#!/usr/bin/env python3
"""手动触发一次交易分析"""
import os
import sys
sys.path.insert(0, os.path.dirname(__file__))

from deepseek import trading_bot

if __name__ == "__main__":
    print("手动触发交易分析...")
    trading_bot()
