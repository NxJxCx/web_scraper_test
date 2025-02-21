# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['app.py'],
    pathex=[],
    binaries=[],
    datas=[('server', 'server'), ('static', 'static'), ('templates', 'templates')],
    hiddenimports=['quart', 'hypercorn', 'hypercorn.app', 'hypercorn.config', 'hypercorn.asyncio', 'asyncio', 'pandas', 'secrets', 'platform', 'traceback', 'concurrent', 'concurrent.futures', 'quart_cors', 'selenium', 'selenium.webdriver', 'selenium.webdriver.common.by', 'selenium.webdriver.common.desired_capabilities', 'selenium.webdriver.common.keys', 'selenium.webdriver.remote.webdriver', 'selenium.webdriver.remote.webelement', 'selenium.webdriver.support', 'selenium.webdriver.support.ui'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='WebScraperApp',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
