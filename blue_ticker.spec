# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['blue_ticker/__main__.py'],
    pathex=[],
    binaries=[],
    datas=[('assets/data_j.csv', 'assets')],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # ビルド・インストールツール（実行時不要）
        'setuptools', '_distutils_hack', 'jaraco', 'more_itertools',
        # 開発・テストツール（実行時不要）
        '_pytest', 'pytest', 'doctest', 'unittest', 'pdb', 'bdb',
        # 数値計算（cache.py の duck-typing 化により不要）
        'numpy',
        # 未使用の HTTP クライアント（httpx/aiohttp を使用）
        'requests', 'urllib3',
        # 未使用のシリアライズ・設定ライブラリ
        'yaml',
        # 未使用の対話型 UI（interactive.py 削除済み）
        'questionary', 'prompt_toolkit',
        # 未使用のその他
        'keyring', 'xmlrpc', 'ftplib', 'smtplib',
    ],
    noarchive=False,
    optimize=1,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='ticker',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
