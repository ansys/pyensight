# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs, copy_metadata
import site
import os
import sys
import shutil

search_patterns = ['*.dll', '*.dylib', 'lib*.so', '*.pyd']

api_pyensight_data = collect_data_files("ansys.api.pyensight")
ansys_pyensight_data = collect_data_files("ansys.pyensight.core")
omni_data = collect_data_files("omni", include_py_files=True)
pxr_data = collect_data_files("pxr", include_py_files=True)
omni_files = collect_dynamic_libs("omni", search_patterns=search_patterns)
pxr_files = collect_dynamic_libs("pxr", search_patterns=search_patterns)

_files = omni_files.copy()
_files.extend(pxr_files)
_data = api_pyensight_data.copy()
_data.extend(omni_data)
_data.extend(pxr_data)
_data.extend(ansys_pyensight_data)
_data.extend(copy_metadata("ansys.pyensight.core"))
_data.append(("usd_exporter/omni.ansys.tools.core.kit", "."))

a = Analysis(
    ['usd_exporter\\omni_core_app.py'],
    pathex=[],
    binaries=_files,
    datas=_data,
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
    name='usd_exporter',
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
