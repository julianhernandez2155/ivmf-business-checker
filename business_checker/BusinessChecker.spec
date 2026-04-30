# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec for IVMF Business Checker.

Builds a single-folder distribution (not --onefile):
  - Faster startup (no temp extraction)
  - Lower AV false-positive risk
  - Easier debugging

Build:
    pyinstaller BusinessChecker.spec

Output:
    dist/BusinessChecker/
    ├── BusinessChecker.exe   (Windows) or BusinessChecker (Mac)
    └── ... bundled dependencies
"""

import os
import sys

block_cipher = None

# Paths relative to this spec file
SPEC_DIR = os.path.dirname(os.path.abspath(SPECPATH))

a = Analysis(
    ['main.py'],
    pathex=[SPEC_DIR],
    binaries=[],
    datas=[
        ('templates', 'templates'),
        ('tools', 'tools'),
        ('workflows', 'workflows'),
    ],
    hiddenimports=[
        'flask',
        'werkzeug',
        'jinja2',
        'markupsafe',
        'webview',
        'openpyxl',
        'pydantic',
        'pydantic.deprecated.decorator',
        'requests',
        'bs4',
        'dotenv',
        'csv',
        'queue',
        'uuid',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'tkinter',
        'matplotlib',
        'numpy',
        'pandas',
        'scipy',
        'PIL',
    ],
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
    name='BusinessChecker',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,  # No console window — pywebview handles the UI
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='BusinessChecker',
)
