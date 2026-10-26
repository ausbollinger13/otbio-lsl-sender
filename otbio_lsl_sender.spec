# -*- mode: python ; coding: utf-8 -*-
import os


a = Analysis(
    [os.path.join(SPECPATH, 'scripts', 'main.py')],
    pathex=[],
    binaries=[],
    datas=[(os.path.join(SPECPATH, 'assets'), 'assets'), (os.path.join(SPECPATH, 'src', 'otbio_lsl_sender'), 'otbio_lsl_sender')],
    hiddenimports=['PySide6.QtCore', 'PySide6.QtGui', 'PySide6.QtWidgets', 'pylsl', 'numpy', 'pygame'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['matplotlib', 'scipy', 'pandas'],
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
    name='OTBio_LSL_Sender',
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
    icon=None,  # Add icon path here if you have one
)
