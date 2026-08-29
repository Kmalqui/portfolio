# -*- mode: python ; coding: utf-8 -*-

from PyInstaller.utils.hooks import collect_all

datas, binaries, hiddenimports = collect_all('faster_whisper')
for package in ('soundcard', 'soundfile', 'ctranslate2', 'tokenizers', 'huggingface_hub'):
    d, b, h = collect_all(package)
    datas += d
    binaries += b
    hiddenimports += h

datas += [('assets/meetingscribe-icon.png', 'assets')]

a = Analysis(
    ['app.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='MeetingScribe',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    icon='assets/meetingscribe-icon.ico',
    disable_windowed_traceback=False,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='MeetingScribe',
)
