APP_STYLE = """
* {
    font-family: "Segoe UI";
    font-size: 13px;
    color: #DDE8FA;
}
QMainWindow, QWidget#AppRoot { background: #07101F; }
QFrame#Sidebar { background: #0B1528; border-right: 1px solid #20304D; }
QLabel#Brand { font-size: 19px; font-weight: 700; color: #F4F7FF; }
QLabel#BrandAccent { color: #4EE7F2; font-size: 11px; font-weight: 600; }
QPushButton#NavButton {
    background: transparent; border: 0; border-radius: 8px; padding: 11px 14px;
    text-align: left; color: #91A4C4;
}
QPushButton#NavButton:hover { background: #12233D; color: #E7F3FF; }
QPushButton#NavButton:checked { background: #183253; color: #64ECF4; }
QLabel#PageTitle { font-size: 25px; font-weight: 700; color: #F5F8FF; }
QLabel#PageSubtitle { color: #8195B7; }
QFrame#Card {
    background: rgba(16, 30, 54, 220); border: 1px solid #243858; border-radius: 13px;
}
QLabel#CardTitle { color: #8EA5C9; font-size: 12px; }
QLabel#Metric { font-size: 24px; font-weight: 700; color: #F6F8FF; }
QLabel#StatusGood { color: #56E8B3; font-weight: 600; }
QLabel#StatusMuted { color: #F0BC6B; font-weight: 600; }
QPushButton {
    background: #182942; border: 1px solid #2B4265; border-radius: 8px; padding: 8px 14px;
}
QPushButton:hover { background: #213958; border-color: #4B6E9C; }
QPushButton:pressed { background: #0E1A2C; border-color: #67E8F1; padding-top: 9px; }
QPushButton:focus { border-color: #67E8F1; }
QPushButton:disabled { color: #62738F; background: #111D30; border-color: #1B2A42; }
QPushButton#PrimaryButton {
    background: #6648D9; border: 1px solid #8B71ED; color: white; font-weight: 600;
}
QPushButton#PrimaryButton:hover { background: #7456E6; }
QPushButton#RunningButton {
    background: #123A34; border-color: #2FAF83; color: #72F1C1; font-weight: 700;
}
QPushButton#PauseButton { color: #FFD08A; border-color: #74552E; }
QPushButton#ResumeButton {
    background: #174A3C; border-color: #47C895; color: #8BF1C9; font-weight: 700;
}
QPushButton#DangerButton {
    color: #FFB0BC; background: #351B28; border-color: #854258; font-weight: 600;
}
QPushButton#DangerButton:hover { background: #4A2232; border-color: #B45470; }
QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox {
    background: #0C182A; border: 1px solid #2B3E5E; border-radius: 7px; padding: 7px;
    selection-background-color: #6547D7;
}
QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus {
    border-color: #4EDFE9;
}
QComboBox::drop-down { border: 0; width: 26px; }
QSlider::groove:horizontal { height: 4px; background: #263958; border-radius: 2px; }
QSlider::handle:horizontal { width: 14px; margin: -5px 0; background: #58DFEB; border-radius: 7px; }
QCheckBox { spacing: 8px; }
QCheckBox::indicator { width: 16px; height: 16px; }
QTableWidget {
    background: #0C1729; alternate-background-color: #101D32; border: 1px solid #243858;
    border-radius: 9px; gridline-color: #1C2B44;
}
QHeaderView::section { background: #13223A; color: #90A6C8; padding: 8px; border: 0; }
QScrollBar:vertical { background: transparent; width: 10px; }
QScrollBar::handle:vertical { background: #2B4265; border-radius: 5px; min-height: 24px; }
QToolTip { background: #14233A; color: #F2F6FF; border: 1px solid #3B557C; padding: 5px; }
"""

