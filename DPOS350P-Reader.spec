# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path
import os,sys
# Resolve runtime libraries from this Python/Qt installation and Windows, not
# unrelated developer tools that may ship incompatible ICU or CRT DLLs.
windows=Path(os.environ.get("SystemRoot","C:/Windows"))
os.environ["PATH"]=os.pathsep.join(str(p) for p in (Path(sys.prefix)/"Scripts",Path(sys.base_prefix),windows/"System32",windows))
root=Path(SPECPATH)
a=Analysis([str(root/'app.py')],pathex=[str(root)],binaries=[],datas=[],hiddenimports=['PySide6.QtSvg'],hookspath=[],hooksconfig={},runtime_hooks=[],excludes=['tkinter','_tkinter','matplotlib','PIL','scipy','numba','PySide6.QtWebEngineCore','PySide6.QtWebEngineWidgets','PySide6.QtWebEngineQuick','PySide6.QtPdf','PySide6.QtPdfWidgets','PySide6.QtQml','PySide6.QtQuick','PySide6.QtQuickWidgets','PySide6.QtMultimedia','PySide6.QtMultimediaWidgets','pyqtgraph.opengl','pyqtgraph.examples'],noarchive=False,optimize=0)
pyz=PYZ(a.pure)
exe=EXE(pyz,a.scripts,[],exclude_binaries=True,name='DPOS350P-Reader',debug=False,strip=False,upx=False,console=False,disable_windowed_traceback=False)
coll=COLLECT(exe,a.binaries,a.datas,strip=False,upx=False,name='DPOS350P-Reader')
