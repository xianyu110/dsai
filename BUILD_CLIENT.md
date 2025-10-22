# 客户端打包指南

本项目支持打包成独立的可执行程序，可在 Windows 和 macOS 上运行。

## 方案概述

我们使用 **PyInstaller** 将 Python 项目打包成独立的可执行文件，无需安装 Python 环境即可运行。

- **Windows**: 打包为 EXE 可执行文件和 ZIP 压缩包
- **macOS**: 打包为 .app 应用程序和 DMG 镜像文件

## 打包步骤

### 🪟 Windows 打包 (打包为 EXE + ZIP)

1. **安装 Python 环境**
   - 下载并安装 Python 3.8+ (https://www.python.org/downloads/)
   - 确保在安装时勾选 "Add Python to PATH"

2. **安装依赖**
   ```bash
   pip install -r requirements.txt
   pip install pyinstaller
   ```

3. **运行打包脚本**
   ```bash
   build_windows.bat
   ```

4. **获取打包文件**
   - EXE 程序: `dist/TradingBot-Windows/TradingBot/`
   - ZIP 压缩包: `dist/TradingBot-Windows.zip`
   - 可直接分发 ZIP 文件给其他 Windows 用户

### 🍎 macOS 打包 (打包为 .app + DMG)

1. **安装 Python 环境**
   ```bash
   brew install python@3.9
   ```

2. **安装依赖**
   ```bash
   pip3 install -r requirements.txt
   pip3 install pyinstaller
   ```

3. **运行打包脚本**
   ```bash
   chmod +x build_macos.sh
   ./build_macos.sh
   ```

4. **获取打包文件**
   - macOS 应用: `dist/TradingBot.app`
   - DMG 镜像: `dist/TradingBot-macOS-[架构].dmg`
   - 可直接分发 DMG 文件给其他 macOS 用户

## 使用打包后的程序

### 🪟 Windows 使用方法

**方式一：使用启动脚本（推荐）**
1. 解压 `TradingBot-Windows.zip`
2. 复制 `.env.example` 为 `.env`，并配置您的 API 密钥
3. 双击 `启动 TradingBot.bat`
4. 打开浏览器访问 http://localhost:5000

**方式二：直接运行 EXE**
1. 进入 `TradingBot` 文件夹
2. 双击 `TradingBot.exe`
3. 打开浏览器访问 http://localhost:5000

### 🍎 macOS 使用方法

**方式一：从 DMG 安装（推荐）**
1. 双击打开 DMG 文件
2. 将 `TradingBot.app` 拖拽到应用程序文件夹
3. 在应用程序中右键点击 `TradingBot.app`，选择"打开"
4. 在弹出的安全提示中选择"打开"
5. 打开浏览器访问 http://localhost:5000

**方式二：直接运行 .app**
1. 右键点击 `TradingBot.app`，选择"打开"
2. 在弹出的安全提示中选择"打开"
3. 打开浏览器访问 http://localhost:5000

> **注意**: macOS 首次运行需要右键打开以允许运行未签名的应用

## 注意事项

### ⚠️ 重要提示

1. **首次运行可能需要授权**
   - Windows: 可能会出现 Windows Defender SmartScreen 警告，点击"更多信息" → "仍要运行"
   - macOS: 首次运行需要在"系统偏好设置" → "安全性与隐私"中允许运行

2. **.env 配置文件**
   - 必须在可执行文件同目录下配置 `.env` 文件
   - 包含交易所 API 密钥、代理设置等敏感信息
   - 不要在未加密的情况下分享此文件

3. **文件大小**
   - 打包后的程序较大（约 100-300MB），因为包含了所有依赖库
   - 这是正常的，确保程序可以独立运行

4. **网络代理**
   - 如果需要使用代理访问交易所，确保在 `.env` 中配置了正确的代理设置

### 🔧 常见问题

**Q: 程序无法启动？**
- 检查是否有防病毒软件阻止
- 确保 `.env` 文件配置正确
- 查看日志文件 `trading_bot.log`

**Q: macOS 提示"应用已损坏"？**
- 打开终端，运行: `xattr -cr /Applications/TradingBot.app`
- 或在"系统偏好设置" → "安全性与隐私"中允许运行

**Q: Windows Defender 拦截程序？**
- 点击"更多信息" → "仍要运行"
- 或将程序添加到 Windows Defender 白名单

**Q: 如何更新程序？**
- 重新运行打包脚本生成新版本
- 替换旧的应用文件
- 保留您的 `.env` 配置文件

**Q: 可以在其他电脑上运行吗？**
- 可以！Windows 分发 ZIP 文件，macOS 分发 DMG 文件
- 不需要安装 Python 或其他依赖
- 只需配置 `.env` 文件即可运行

## 高级选项

### 自定义打包配置

如需修改打包配置，编辑 `trading_bot.spec` 文件：

- **修改图标**: 设置 `icon='path/to/icon.ico'`
- **隐藏控制台窗口**: 设置 `console=False`
- **添加额外文件**: 在 `datas` 列表中添加

### 减小文件大小

```bash
# 使用 UPX 压缩（已在 spec 中启用）
pip install upx-ucl

# 或使用单文件模式（启动较慢）
pyinstaller --onefile web_ui.py
```

## 分发建议

### 📦 分发文件

**Windows:**
- 分发 `dist/TradingBot-Windows.zip` 压缩包
- 用户解压即可使用，无需安装

**macOS:**
- 分发 `dist/TradingBot-macOS-[架构].dmg` 镜像文件
- 用户双击 DMG，拖拽到应用程序文件夹即可

### 🔒 代码签名（可选）

为了避免安全警告，建议对可执行文件进行代码签名：

**Windows 代码签名:**
```bash
# 需要购买代码签名证书
signtool sign /f certificate.pfx /p password /t http://timestamp.digicert.com dist/TradingBot-Windows/TradingBot/TradingBot.exe
```

**macOS 代码签名:**
```bash
# 需要 Apple Developer ID
codesign --force --deep --sign "Developer ID Application: Your Name" dist/TradingBot.app
# 公证
xcrun notarytool submit dist/TradingBot-macOS-[架构].dmg --wait --apple-id your@email.com --team-id TEAM_ID
```

### 📋 文件清单

打包完成后，您应该拥有以下文件：

```
dist/
├── TradingBot.app              # macOS 应用（仅 macOS）
├── TradingBot-macOS-arm64.dmg  # macOS DMG（M系列芯片）
├── TradingBot-macOS-x86_64.dmg # macOS DMG（Intel芯片）
├── TradingBot-Windows.zip      # Windows ZIP 压缩包
└── TradingBot-Windows/         # Windows 程序目录
    ├── TradingBot/             # 主程序
    ├── .env.example
    ├── 启动 TradingBot.bat
    └── 使用说明.txt
```

## 替代方案

### 方案二：Docker 容器

如果用户熟悉 Docker，可以使用现有的 Docker 部署方案：

```bash
docker-compose up -d
```

这种方式跨平台性更好，但需要安装 Docker。

### 方案三：Electron 桌面应用

如果需要更好的桌面体验，可以使用 Electron 封装 Web UI：

1. 创建 Electron 项目
2. 内嵌 Python 后端
3. 打包成原生桌面应用

这种方式可以提供更好的用户体验，但开发成本较高。

## 许可证与免责声明

使用本软件进行交易需要您自己承担风险。确保遵守当地法律法规。

---

**技术支持**: 如有问题，请提交 Issue 或查看项目文档。