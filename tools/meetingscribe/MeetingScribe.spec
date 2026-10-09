# -*- mode: python ; coding: utf-8 -*-

import sys
from PyInstaller.utils.hooks import collect_all

datas, binaries, hiddenimports = collect_all('faster_whisper')
for package in ('soundcard', 'soundfile', 'ctranslate2', 'tokenizers', 'huggingface_hub', 'mss'):
    d, b, h = collect_all(package)
    datas += d
    binaries += b
    hiddenimports += h

datas += [
    ('assets/meetingscribe-icon.png', 'assets'),
    ('assets/meetingscribe-icon.ico', 'assets'),
    ('assets/chevron-light.svg', 'assets'),
    ('assets/chevron-dark.svg', 'assets'),
]

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
is_mac = sys.platform == 'darwin'
app_icon = 'assets/meetingscribe-icon.icns' if is_mac else 'assets/meetingscribe-icon.ico'

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='MeetingScribe',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=not is_mac,
    console=False,
    icon=app_icon,
    disable_windowed_traceback=False,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=not is_mac,
    upx_exclude=[],
    name='MeetingScribe',
)

if is_mac:
    app = BUNDLE(
        coll,
        name='MeetingScribe.app',
        icon=app_icon,
        bundle_identifier='com.kmalqui.meetingscribe',
        info_plist={
            'CFBundleShortVersionString': '0.4.1',
            'CFBundleVersion': '0.4.1',
            'LSMinimumSystemVersion': '12.0',
            'NSMicrophoneUsageDescription': (
                'MeetingScribe needs microphone access to record your voice and the selected meeting-audio input.'
            ),
            'NSScreenCaptureUsageDescription': (
                'MeetingScribe needs screen recording access only when you choose to include a screen.'
            ),
        },
    )
