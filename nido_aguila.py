"""Club Nido Águila — punto de entrada."""
import os
import sys
import traceback
from datetime import datetime

from PySide6.QtGui import QFont, QIcon
from PySide6.QtWidgets import QApplication, QMessageBox

from app import estilos
from app.db import CARPETA_LOCAL
from app.ventana import VentanaPrincipal


def _manejar_error(tipo, valor, tb):
    """Evita que el programa se cierre sin aviso: muestra el error y lo guarda en un log."""
    texto = "".join(traceback.format_exception(tipo, valor, tb))
    try:
        os.makedirs(CARPETA_LOCAL, exist_ok=True)
        with open(os.path.join(CARPETA_LOCAL, "errores.log"), "a", encoding="utf-8") as f:
            f.write(f"\n--- {datetime.now():%Y-%m-%d %H:%M:%S} ---\n{texto}")
    except OSError:
        pass
    QMessageBox.critical(None, "Ocurrió un error",
                         f"Se produjo un error inesperado, pero tus datos están a salvo.\n\n{valor}")


def main():
    sys.excepthook = _manejar_error
    app = QApplication(sys.argv)
    app.setApplicationName("Club Nido Aguila")
    app.setFont(QFont("Segoe UI", 10))
    app.setStyleSheet(estilos.QSS)
    app.setWindowIcon(QIcon(os.path.join(estilos.RECURSOS, "icono.png")))
    ventana = VentanaPrincipal()
    ventana.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
