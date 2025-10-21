# 多币种AI交易机器人

## ✨ 特性

参考 AlphaArena 成功策略打造的多币种自动交易系统

### 核心优势

1. **多币种支持** - BTC, ETH, SOL, DOGE 同时运行
2. **AI驱动决策** - 支持 DeepSeek/Grok 4/Claude Sonnet 4.5
3. **持仓优先策略** - 只要未触发止损就持有,避免过度交易
4. **情感化提示** - 增强AI分析的积极性和责任感

### 配置说明

**AI模型切换:**
```bash
AI_MODEL=deepseek  # 或 grok, claude
```

**交易参数:**
- 每次交易: 50 USDT
- 杠杆: 10x
- 周期: 15分钟
- 止损阈值: 95% (价格低于入场价5%平仓)

**中转API配置:**
```
RELAY_API_BASE_URL=https://apipro.maynor1024.live/v1
RELAY_API_KEY=你的密钥
```

### 运行

```bash
python3 deepseek.py
```

## ⚠️ 风险提示

- 高杠杆交易风险极高
- 建议先用测试模式充分测试
- 务必设置合理的止损
- 不要投入超过承受范围的资金

## 🎯 策略说明

参考 AlphaArena 30%+收益的策略:
1. 持仓为主,减少交易频率
2. 多币种分散风险
3. 严格止损保护
4. AI技术分析决策

---
个人喜欢玩黑箱文化，你们不一样，别上头。
