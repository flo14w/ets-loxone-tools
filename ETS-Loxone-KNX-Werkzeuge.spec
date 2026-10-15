# -*- mode: python ; coding: utf-8 -*-

a = Analysis(
    ['combined_app.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('type_profiles.json', '.'),
        ('output/logo/loxone-ets-exporter-logo-bidirectional-v2.png', 'assets'),
    ],
    hiddenimports=[],
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
    name='ETS-Loxone-KNX-Werkzeuge-v1.0.8',
    version='version_info_combined.txt',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['output/logo/loxone-ets-exporter-logo-bidirectional-v2.png'],
)
