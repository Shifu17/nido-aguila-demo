import os
import sys
import tempfile

# Configuración aislada: nunca toca los datos reales de la computadora.
os.environ["NIDO_CARPETA"] = tempfile.mkdtemp(prefix="nido_test_")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest  # noqa: E402

from app.db import Database  # noqa: E402


@pytest.fixture
def base(tmp_path):
    d = Database(str(tmp_path / "club.db"))
    yield d
    d.con.close()


@pytest.fixture
def ventana(tmp_path):
    from PySide6.QtWidgets import QApplication

    from app import estilos
    from app.ventana import VentanaPrincipal
    app = QApplication.instance() or QApplication([])
    app.setStyleSheet(estilos.QSS)
    v = VentanaPrincipal(Database(str(tmp_path / "club.db")))
    yield v
    v.close()
