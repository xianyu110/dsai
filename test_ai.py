import os
from dotenv import load_dotenv
from openai import OpenAI
import httpx

load_dotenv()

# 测试中转 API
api_key = os.getenv('RELAY_API_KEY')
base_url = os.getenv('RELAY_API_BASE_URL', 'https://for.shuo.bar/v1')

# 配置代理
proxies = {}
if os.getenv('HTTP_PROXY'):
    proxies = {
        'http://': os.getenv('HTTP_PROXY'),
        'https://': os.getenv('HTTPS_PROXY', os.getenv('HTTP_PROXY')),
    }
    print(f"使用代理: {os.getenv('HTTP_PROXY')}")

http_client = httpx.Client(proxies=proxies) if proxies else None

print("中转 API 测试")
print(f"Base URL: {base_url}")
print(f"API Key: {api_key[:10]}...{api_key[-4:] if api_key and len(api_key) > 14 else 'None'}")
print()

# 测试多个模型
models = [
    ('deepseek-chat', 'DeepSeek V3.1'),
    ('grok-4', 'Grok 4'),
    ('claude-sonnet-4-5-20250929', 'Claude Sonnet 4.5'),
]

for model_name, model_desc in models:
    print(f"{'='*50}")
    print(f"测试模型: {model_desc} ({model_name})")
    print(f"{'='*50}")

    try:
        client = OpenAI(
            api_key=api_key,
            base_url=base_url,
            http_client=http_client
        )

        response = client.chat.completions.create(
            model=model_name,
            messages=[
                {"role": "system", "content": "你是一个专业的量化交易分析师。"},
                {"role": "user", "content": "简单介绍一下BTC技术分析的基本方法,不超过30字。"}
            ],
            stream=False
        )

        # 调试输出
        print(f"响应类型: {type(response)}")
        print(f"响应内容: {response}")

        result = response.choices[0].message.content
        print(f"✅ {model_desc} API 调用成功!")
        print(f"返回: {result}\n")

    except Exception as e:
        print(f"❌ {model_desc} API 调用失败")
        print(f"错误: {str(e)[:200]}")
        import traceback
        traceback.print_exc()
        print()
