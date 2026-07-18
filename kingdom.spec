# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec for Kingdom — AI Life OS Windows desktop app.
Run via build_windows.bat on a Windows machine.
"""
import os
from PyInstaller.utils.hooks import collect_all

block_cipher = None

# Collect webview (pywebview) properly
webview_datas, webview_binaries, webview_hiddenimports = collect_all('webview')

a = Analysis(
    ['app.py'],
    pathex=['.'],
    binaries=webview_binaries,
    datas=[
        ('backend/static', 'backend/static'),
        ('backend', 'backend'),
    ] + webview_datas,
    hiddenimports=[
        'uvicorn',
        'uvicorn.logging',
        'uvicorn.loops',
        'uvicorn.loops.auto',
        'uvicorn.protocols',
        'uvicorn.protocols.http',
        'uvicorn.protocols.http.auto',
        'uvicorn.protocols.websockets',
        'uvicorn.protocols.websockets.auto',
        'uvicorn.lifespan',
        'uvicorn.lifespan.on',
        'fastapi',
        'sqlalchemy',
        'sqlalchemy.dialects.sqlite',
        'apscheduler',
        'apscheduler.schedulers.background',
        'webview',
        'webview.platforms.winforms',
    ] + webview_hiddenimports,
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
    name='Kingdom',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,  # no console window
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='kingdom.ico' if os.path.exists('kingdom.ico') else None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='Kingdom',
)
