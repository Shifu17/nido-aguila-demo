# -*- mode: python ; coding: utf-8 -*-
# Genera un solo archivo: dist/NidoAguila.exe
# Sin datos del club: viven en %LOCALAPPDATA%\NidoAguila de cada computadora.

a = Analysis(
    ['nido_aguila.py'],
    pathex=[],
    binaries=[],
    datas=[('app/recursos', 'app/recursos')],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['tkinter', 'pytest', 'PySide6.QtQml', 'PySide6.QtQuick', 'PySide6.QtWebEngineCore',
              'PySide6.QtMultimedia', 'PySide6.Qt3DCore', 'PySide6.QtCharts', 'PySide6.QtDataVisualization'],
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
    name='NidoAguila',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['app/recursos/icono.ico'],
)
