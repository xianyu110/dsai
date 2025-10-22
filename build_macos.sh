#!/bin/bash

# macOS 打包脚本 - 打包成 .app 和 .dmg

set -e

echo "🍎 开始 macOS 打包流程..."

# 1. 检查是否安装了 PyInstaller
if ! pip3 show pyinstaller &> /dev/null; then
    echo "⚠️  PyInstaller 未安装，正在安装..."
    pip3 install pyinstaller
fi

# 2. 清理之前的打包文件
echo "🧹 清理旧的打包文件..."
rm -rf build dist

# 3. 使用 PyInstaller 打包
echo "📦 使用 PyInstaller 打包应用..."
python3 -m PyInstaller trading_bot.spec --clean

# 4. 检查 .app 是否生成成功
if [ ! -d "dist/TradingBot.app" ]; then
    echo "❌ .app 文件生成失败！"
    exit 1
fi

echo "✅ .app 文件生成成功"

# 5. 创建 DMG 镜像
echo "💿 创建 DMG 镜像..."

# 创建临时目录用于 DMG
DMG_DIR="dist/dmg_temp"
mkdir -p "$DMG_DIR"

# 复制 .app 到临时目录
cp -R "dist/TradingBot.app" "$DMG_DIR/"

# 复制 .env.example 和使用说明
cp .env.example "$DMG_DIR/.env.example"

# 创建使用说明文本
cat > "$DMG_DIR/使用说明.txt" << 'EOF'
TradingBot 使用说明

1. 安装步骤：
   - 将 TradingBot.app 拖拽到应用程序文件夹
   - 复制 .env.example 为 .env，并填入您的 API 密钥

2. 首次运行：
   - 右键点击 TradingBot.app，选择"打开"
   - 在弹出的安全提示中选择"打开"
   - 等待程序启动（约 5-10 秒）

3. 使用方法：
   - 程序启动后，在浏览器中访问 http://localhost:5000
   - 首次使用请配置交易所 API 密钥和 AI API 密钥

4. 注意事项：
   - 请妥善保管 .env 文件，不要泄露 API 密钥
   - 建议在测试网络上先测试策略
   - 使用代理可提高 API 访问稳定性

技术支持：https://github.com/your-repo/issues
EOF

# 创建到应用程序文件夹的符号链接（方便拖拽安装）
ln -s /Applications "$DMG_DIR/Applications"

# 设置 DMG 名称
DMG_NAME="TradingBot-macOS-$(uname -m).dmg"
DMG_PATH="dist/$DMG_NAME"

# 删除旧的 DMG（如果存在）
rm -f "$DMG_PATH"

# 创建 DMG
echo "📀 正在创建 DMG 文件..."
hdiutil create -volname "TradingBot" \
    -srcfolder "$DMG_DIR" \
    -ov -format UDZO \
    "$DMG_PATH"

# 清理临时文件
rm -rf "$DMG_DIR"

echo ""
echo "✅ 打包完成！"
echo ""
echo "📁 生成的文件："
echo "   - macOS App: dist/TradingBot.app"
echo "   - DMG 镜像: $DMG_PATH"
echo ""
echo "📦 DMG 文件大小: $(du -h "$DMG_PATH" | cut -f1)"
echo ""
echo "🎉 现在您可以将 DMG 文件分发给其他 macOS 用户！"
