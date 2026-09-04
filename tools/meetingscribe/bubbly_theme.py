"""Lightweight rounded styling: no animations, effects, or background work."""

COMMON = """
QLabel#brandTitle { font-family: "Segoe UI Variable Display", "Segoe UI"; font-size: 31px; font-weight: 800; }
QLabel#sectionTitle { font-size: 16px; }
QFrame#card, QFrame#workspaceCard { border-radius: 23px; }
QFrame#meterPanel { border-radius: 17px; }
QFrame#consentCard { border-radius: 19px; }
QComboBox, QSpinBox { border-radius: 16px; padding-left: 13px; padding-right: 24px; }
QComboBox::drop-down { border: none; width: 24px; }
QPlainTextEdit { border-radius: 17px; padding: 12px; }
QPushButton { border-radius: 20px; padding: 4px 15px; }
QPushButton#recordButton { border-radius: 27px; font-size: 16px; }
QLabel#timer { border-radius: 22px; }
QLabel#statusPill { border-radius: 16px; }
QLabel#privacyBadge { border-radius: 13px; padding: 7px 13px; }
QComboBox#liveMode { border-radius: 12px; padding-right: 24px; }
QPushButton#clarityButton { border-radius: 12px; }
QProgressBar { min-height: 14px; max-height: 14px; border-radius: 7px; }
QProgressBar::chunk { border-radius: 7px; }
QStatusBar { padding: 3px 12px; }
QPushButton:focus, QComboBox:focus, QSpinBox:focus { border: 2px solid #8a67c7; }
"""

LIGHT = """
QWidget { color: #34264d; }
QMainWindow, QWidget#appRoot, QStatusBar { background: #fff8f2; }
QLabel#brandTitle, QLabel#sectionTitle { color: #34264d; }
QLabel#brandSubtitle, QLabel#sectionHint, QLabel#meterState { color: #70627e; }
QLabel#fieldLabel { color: #534163; }
QFrame#card, QFrame#workspaceCard { background: #ffffff; border-color: #e9dded; }
QFrame#workspaceCard[tone="lavender"] { background: #f3edff; border-color: #ddcfed; }
QFrame#workspaceCard[tone="peach"] { background: #fff0e7; border-color: #eed7c8; }
QFrame#workspaceCard[tone="mint"] { background: #edf8ef; border-color: #d0e5d4; }
QFrame#meterPanel { background: #faf6ff; border-color: #e5d8f0; }
QFrame#consentCard { background: #fff4d8; border-color: #e8d4a2; }
QLabel#consentTitle, QCheckBox { color: #725212; }
QComboBox, QSpinBox, QPlainTextEdit { background: #fffcff; border-color: #d9cce3; color: #34264d; selection-background-color: #e5d5fc; selection-color: #34264d; }
QComboBox:hover, QSpinBox:hover { border-color: #9876c7; }
QComboBox QAbstractItemView { background: #fffcff; color: #34264d; selection-background-color: #e5d5fc; }
QPlainTextEdit:focus { background: #ffffff; border-color: #9876c7; }
QPushButton { background: #f0e6ff; color: #4e326e; border-color: #dfcdef; }
QPushButton:hover { background: #e7d7fa; border-color: #ae8bd3; }
QPushButton:pressed { background: #d8bfee; }
QPushButton:disabled { background: #efe9f0; color: #8a7e91; border-color: #e5dce7; }
QPushButton#recordButton { background: #d9c2fc; color: #392252; }
QPushButton#recordButton:hover { background: #cbb0f5; }
QPushButton#recordButton:disabled { background: #eee3f7; color: #85718f; }
QPushButton#recordButton[recording="true"] { background: #b63b54; color: #ffffff; }
QPushButton#recordButton[processing="true"] { background: #655086; color: #ffffff; }
QLabel#timer { background: #fff0e7; border-color: #eed7c8; color: #77462c; }
QLabel#statusPill, QLabel#privacyBadge { background: #e0f3df; color: #375c36; }
QProgressBar { background: #e4d9ed; }
QProgressBar::chunk { background: #a387ca; }
QToolTip { background: #fff8f2; color: #34264d; border: 1px solid #d9cce3; }
"""

DARK = """
QWidget { color: #f0e8fa; }
QMainWindow, QWidget#appRoot, QStatusBar { background: #211d30; }
QLabel#brandTitle, QLabel#sectionTitle { color: #f5ebff; }
QLabel#brandSubtitle, QLabel#sectionHint, QLabel#meterState { color: #c0afce; }
QLabel#fieldLabel { color: #e2cdef; }
QFrame#card, QFrame#workspaceCard { background: #302a40; border-color: #51445f; }
QFrame#workspaceCard[tone="lavender"] { background: #382d4f; border-color: #59446f; }
QFrame#workspaceCard[tone="peach"] { background: #423037; border-color: #674951; }
QFrame#workspaceCard[tone="mint"] { background: #293e38; border-color: #426155; }
QFrame#meterPanel { background: #3c304d; border-color: #5e4873; }
QFrame#consentCard { background: #433823; border-color: #746037; }
QLabel#consentTitle, QCheckBox { color: #f5d68c; }
QComboBox, QSpinBox, QPlainTextEdit { background: #282235; color: #f0e8fa; border-color: #61516e; selection-background-color: #715590; selection-color: #ffffff; }
QComboBox:hover, QSpinBox:hover { border-color: #c8a4f3; }
QComboBox QAbstractItemView { background: #302a40; color: #f0e8fa; selection-background-color: #715590; }
QPlainTextEdit:focus { background: #2f263e; border-color: #c8a4f3; }
QPushButton { background: #493657; color: #f0ddff; border-color: #685077; }
QPushButton:hover { background: #60456f; border-color: #bd94e6; }
QPushButton:pressed { background: #735586; }
QPushButton:disabled { background: #342c40; color: #a494ae; border-color: #4c4058; }
QPushButton#recordButton { background: #d9b7fa; color: #352244; }
QPushButton#recordButton:hover { background: #e3c9fd; }
QPushButton#recordButton:disabled { background: #4c3d5d; color: #bba6c8; }
QPushButton#recordButton[recording="true"] { background: #b13c56; color: #ffffff; }
QPushButton#recordButton[processing="true"] { background: #695083; color: #ffffff; }
QLabel#timer { background: #4a343e; border-color: #78545d; color: #ffd4be; }
QLabel#statusPill, QLabel#privacyBadge { background: #30473c; color: #cfedbb; }
QProgressBar { background: #564563; }
QProgressBar::chunk { background: #c4a0ec; }
QToolTip { background: #302a40; color: #f0e8fa; border: 1px solid #685077; }
"""


def palette_colors(dark=False):
    return {
        "Window": "#211d30" if dark else "#fff8f2",
        "WindowText": "#f0e8fa" if dark else "#34264d",
        "Base": "#282235" if dark else "#fffcff",
        "AlternateBase": "#302a40" if dark else "#f3edff",
        "Text": "#f0e8fa" if dark else "#34264d",
        "Button": "#493657" if dark else "#f0e6ff",
        "ButtonText": "#f0ddff" if dark else "#4e326e",
        "Highlight": "#715590" if dark else "#e5d5fc",
        "HighlightedText": "#ffffff" if dark else "#34264d",
        "PlaceholderText": "#c0afce" if dark else "#70627e",
        "ToolTipBase": "#302a40" if dark else "#fff8f2",
        "ToolTipText": "#f0e8fa" if dark else "#34264d",
    }
