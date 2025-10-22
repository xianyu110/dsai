@echo off
REM Windows 打包脚本 - 打包成 .exe 和安装程序

echo 🪟 开始 Windows 打包流程...

REM 1. 检查是否安装了 PyInstaller
pip show pyinstaller >nul 2>&1
if %errorlevel% neq 0 (
    echo ⚠️  PyInstaller 未安装，正在安装...
    pip install pyinstaller
)

REM 2. 清理之前的打包文件
echo 🧹 清理旧的打包文件...
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist

REM 3. 使用 PyInstaller 打包
echo 📦 使用 PyInstaller 打包应用...
pyinstaller trading_bot.spec --clean

REM 4. 检查是否生成成功
if not exist "dist\TradingBot" (
    echo ❌ 打包失败！
    exit /b 1
)

echo ✅ EXE 文件生成成功

REM 5. 创建发布包
echo 📁 创建发布包...

REM 创建发布目录
set RELEASE_DIR=dist\TradingBot-Windows
if exist "%RELEASE_DIR%" rmdir /s /q "%RELEASE_DIR%"
mkdir "%RELEASE_DIR%"

REM 复制所有文件
xcopy /E /I /Y "dist\TradingBot" "%RELEASE_DIR%\TradingBot"

REM 复制 .env.example
copy /Y .env.example "%RELEASE_DIR%\.env.example"

REM 创建启动脚本
echo @echo off > "%RELEASE_DIR%\启动 TradingBot.bat"
echo cd TradingBot >> "%RELEASE_DIR%\启动 TradingBot.bat"
echo start TradingBot.exe >> "%RELEASE_DIR%\启动 TradingBot.bat"
echo echo 程序已启动，请在浏览器中访问 http://localhost:5000 >> "%RELEASE_DIR%\启动 TradingBot.bat"
echo pause >> "%RELEASE_DIR%\启动 TradingBot.bat"

REM 创建使用说明
(
echo TradingBot 使用说明
echo.
echo 1. 安装步骤：
echo    - 将整个 TradingBot-Windows 文件夹复制到您希望的位置
echo    - 复制 .env.example 为 .env，并填入您的 API 密钥
echo.
echo 2. 首次运行：
echo    - 双击"启动 TradingBot.bat"
echo    - 或进入 TradingBot 文件夹，双击 TradingBot.exe
echo    - Windows Defender 可能会显示警告，选择"仍要运行"
echo.
echo 3. 使用方法：
echo    - 程序启动后，在浏览器中访问 http://localhost:5000
echo    - 首次使用请配置交易所 API 密钥和 AI API 密钥
echo.
echo 4. 注意事项：
echo    - 请妥善保管 .env 文件，不要泄露 API 密钥
echo    - 建议在测试网络上先测试策略
echo    - 使用代理可提高 API 访问稳定性
echo.
echo 技术支持：https://github.com/your-repo/issues
) > "%RELEASE_DIR%\使用说明.txt"

REM 6. 创建 ZIP 压缩包（可选）
echo 🗜️  创建 ZIP 压缩包...
powershell -Command "Compress-Archive -Path '%RELEASE_DIR%' -DestinationPath 'dist\TradingBot-Windows.zip' -Force"

echo.
echo ✅ 打包完成！
echo.
echo 📁 生成的文件：
echo    - Windows 程序: %RELEASE_DIR%
echo    - ZIP 压缩包: dist\TradingBot-Windows.zip
echo.
echo 🎉 现在您可以将文件分发给其他 Windows 用户！
echo.
pause
