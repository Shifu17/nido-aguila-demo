"""Colores y hoja de estilos (azul marino y dorado del club)."""
import os
import sys

RECURSOS = (os.path.join(sys._MEIPASS, "app", "recursos") if getattr(sys, "frozen", False)
            else os.path.join(os.path.dirname(os.path.abspath(__file__)), "recursos"))

MARINO = "#0f2a44"
MARINO_2 = "#173b5e"
DORADO = "#e8a920"
DORADO_SUAVE = "#fff4da"
VERDE = "#1f8a4c"
VERDE_SUAVE = "#e3f4ea"
VERDE_BORDE = "#bfe3cc"
ROJO = "#c0392b"
ROJO_SUAVE = "#fdecea"
ROJO_BORDE = "#f0b7b0"
FONDO = "#f4f6f9"
TARJETA = "#ffffff"
TEXTO = "#14202e"
SUAVE = "#5b6b7c"
BORDE = "#dfe5ec"
FEMENIL = ("#f6e8f5", "#8a2f7f")
FLECHA = os.path.join(RECURSOS, "flecha.svg").replace("\\", "/")

QSS = f"""
QWidget {{ font-family: "Segoe UI"; font-size: 10pt; color: {TEXTO}; }}
QMainWindow, #contenido {{ background: {FONDO}; }}
QToolTip {{ background: {MARINO}; color: white; border: 0; padding: 6px; }}

/* Barra lateral */
#lateral {{ background: {MARINO}; }}
#lateral QLabel {{ color: white; }}
#marca {{ font-size: 12pt; font-weight: 700; }}
#marcaSub {{ color: #9fb3c8; font-size: 9pt; }}
#logo {{ background: {DORADO}; color: {MARINO}; border-radius: 22px; font-weight: 900; font-size: 11pt; }}
QPushButton#nav {{
  text-align: left; background: transparent; border: 0; color: #c9d6e3;
  padding: 11px 14px; border-radius: 10px; font-weight: 600;
}}
QPushButton#nav:hover {{ background: {MARINO_2}; color: white; }}
QPushButton#nav:checked {{ background: {MARINO_2}; color: white; }}
#stat {{ background: {MARINO_2}; border-radius: 10px; }}
#statNum {{ color: {DORADO}; font-size: 16pt; font-weight: 800; }}
#statTxt {{ color: #c9d6e3; font-size: 9pt; }}
#version {{ color: #7f96ad; font-size: 8pt; }}

/* Títulos */
#titulo {{ font-size: 19pt; font-weight: 700; color: {MARINO}; }}
#subtitulo {{ color: {SUAVE}; }}
#seccion {{ font-size: 12pt; font-weight: 700; color: {MARINO}; }}
#suave {{ color: {SUAVE}; }}
#vacio {{ color: {SUAVE}; font-size: 11pt; padding: 40px; background: {TARJETA};
          border: 1px solid {BORDE}; border-radius: 12px; }}

/* Campos */
QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox, QDateEdit, QPlainTextEdit {{
  background: white; border: 1px solid {BORDE}; border-radius: 8px; padding: 7px 10px;
}}
QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus, QDateEdit:focus, QPlainTextEdit:focus {{
  border-color: #2f7fd1;
}}
QSpinBox, QDoubleSpinBox {{ padding: 5px 10px; }}
QComboBox, QDateEdit {{ padding-right: 28px; }}
QComboBox::drop-down, QDateEdit::drop-down {{ border: 0; width: 26px; subcontrol-position: center right; }}
QComboBox::down-arrow, QDateEdit::down-arrow {{ image: url("{FLECHA}"); width: 12px; height: 8px; }}
QComboBox QAbstractItemView {{ background: white; border: 1px solid {BORDE}; selection-background-color: {DORADO_SUAVE};
  selection-color: {TEXTO}; }}

/* Botones */
QPushButton {{
  background: white; border: 1px solid {BORDE}; border-radius: 8px; padding: 8px 14px; font-weight: 600;
}}
QPushButton:hover {{ border-color: #b9c5d2; }}
QPushButton:disabled {{ color: #9aa6b2; background: #f1f3f6; }}
QPushButton#primario {{ background: {MARINO}; border-color: {MARINO}; color: white; }}
QPushButton#primario:hover {{ background: {MARINO_2}; }}
QPushButton#primario:disabled {{ background: #8b9aab; border-color: #8b9aab; color: #eef2f6; }}
QPushButton#dorado {{ background: {DORADO}; border-color: {DORADO}; color: #2b1d00; }}
QPushButton#peligro {{ color: {ROJO}; }}
QPushButton#chico {{ padding: 5px 10px; font-size: 9pt; }}
QPushButton#chicoPeligro {{ padding: 5px 10px; font-size: 9pt; color: {ROJO}; }}

/* Tablas */
QTableWidget {{
  background: {TARJETA}; border: 1px solid {BORDE}; border-radius: 12px; gridline-color: transparent;
  selection-background-color: {DORADO_SUAVE}; selection-color: {TEXTO};
}}
QTableWidget::item {{ border-bottom: 1px solid {BORDE}; padding: 4px 8px; }}
QHeaderView::section {{
  background: #f8fafc; color: {SUAVE}; border: 0; border-bottom: 1px solid {BORDE};
  padding: 9px 8px; font-size: 8.5pt; font-weight: 700;
}}

/* Tarjetas y listas */
#tarjeta {{ background: {TARJETA}; border: 1px solid {BORDE}; border-radius: 12px; }}
QListWidget {{ background: transparent; border: 0; outline: 0; }}
QListWidget::item {{ background: white; border: 1px solid {BORDE}; border-radius: 10px; padding: 9px 10px; margin: 3px 0; }}
QListWidget::item:hover {{ border-color: #b9c5d2; }}
QListWidget::item:selected {{ background: {DORADO_SUAVE}; border-color: {MARINO}; color: {TEXTO}; }}
QScrollArea {{ border: 0; background: transparent; }}

/* Meses en cobro */
QPushButton#mes {{ min-height: 44px; padding: 2px; font-size: 9pt; border-radius: 8px; }}
QPushButton#mes[estado="pagado"] {{ background: {VERDE_SUAVE}; border-color: {VERDE_BORDE}; color: {VERDE}; }}
QPushButton#mes[estado="adeudo"] {{ border-color: {ROJO_BORDE}; color: {ROJO}; }}
QPushButton#mes:checked {{ background: {MARINO}; border-color: {MARINO}; color: white; }}

/* Etiquetas de estado */
#badge {{ background: #eef2f6; color: {MARINO}; border-radius: 9px; padding: 2px 9px; font-size: 8.5pt; font-weight: 700; }}
#badgeFem {{ background: {FEMENIL[0]}; color: {FEMENIL[1]}; border-radius: 9px; padding: 2px 9px; font-size: 8.5pt; font-weight: 700; }}

#barraPago {{ background: {TARJETA}; border: 1px solid {BORDE}; border-radius: 12px; }}
#total {{ font-size: 19pt; font-weight: 800; color: {MARINO}; }}

QGroupBox {{ border: 1px solid {BORDE}; border-radius: 12px; margin-top: 14px; padding: 14px 12px 12px; font-weight: 700; color: {MARINO}; }}
QGroupBox::title {{ subcontrol-origin: margin; left: 12px; padding: 0 6px; }}
QRadioButton {{ spacing: 8px; }}
QRadioButton::indicator {{ width: 12px; height: 12px; border-radius: 8px; border: 2px solid #b9c5d2; background: white; }}
QRadioButton::indicator:checked {{ width: 8px; height: 8px; border: 4px solid {MARINO}; }}
QDialog {{ background: white; }}
"""
