# -*- mode: python ; coding: utf-8 -*-

import sys

block_cipher = None

a = Analysis(
    ['web_ui.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('templates', 'templates'),
        ('static', 'static'),
        ('.env.example', '.'),
    ],
    hiddenimports=[
        'flask',
        'ccxt',
        'pandas',
        'numpy',
        'openai',
        'anthropic',
        'schedule',
        'python_dotenv',
        'requests',
        'urllib3',
        'dateutil',
        'pytz',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='TradingBot',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='TradingBot',
)

# macOS App Bundle
if sys.platform == 'darwin':
    app = BUNDLE(
        coll,
        name='TradingBot.app',
        icon=None,
        bundle_identifier='com.tradingbot.app',
        info_plist={
            'CFBundleName': 'TradingBot',
            'CFBundleDisplayName': 'Trading Bot',
            'CFBundleVersion': '1.0.0',
            'CFBundleShortVersionString': '1.0.0',
            'NSHighResolutionCapable': 'True',
            'LSMinimumSystemVersion': '10.13.0',
        },
    )