import os
from dotenv import load_dotenv
import ccxt

load_dotenv()

# 显示当前配置(脱敏)
api_key = os.getenv('OKX_API_KEY')
api_secret = os.getenv('OKX_SECRET')
api_password = os.getenv('OKX_PASSWORD')

print("当前配置:")
print(f"API Key: {api_key[:10]}...{api_key[-4:] if api_key and len(api_key) > 14 else 'None'}")
print(f"Secret: {api_secret[:10]}...{api_secret[-4:] if api_secret and len(api_secret) > 14 else 'None'}")
print(f"Password: {'已设置' if api_password else '未设置'}")
print()

# 代理配置
proxies = {}
if os.getenv('HTTP_PROXY'):
    proxies = {
        'http': os.getenv('HTTP_PROXY'),
        'https': os.getenv('HTTPS_PROXY', os.getenv('HTTP_PROXY')),
    }
    print(f"使用代理: {proxies['http']}\n")

try:
    exchange = ccxt.okx({
        'apiKey': api_key,
        'secret': api_secret,
        'password': api_password,
        'enableRateLimit': True,
        'proxies': proxies,
    })

    # 测试连接
    print("正在测试 OKX API 连接...")
    balance = exchange.fetch_balance()
    print("✅ API 连接成功!")
    print(f"USDT 余额: {balance.get('USDT', {}).get('free', 0)}")

except Exception as e:
    print(f"❌ API 连接失败")
    print(f"错误详情: {type(e).__name__}: {str(e)}")

    import traceback
    print("\n详细错误:")
    traceback.print_exc()

    print("\n请检查:")
    print("1. API Key/Secret/Password 是否完整且正确")
    print("2. Secret 通常是64位长的字符串")
    print("3. 是否设置了 IP 白名单且包含当前 IP: 113.84.160.56")
    print("4. API 权限是否包含'读取'和'交易'")
    print("5. API 是否已启用(有些需要24小时激活期)")
