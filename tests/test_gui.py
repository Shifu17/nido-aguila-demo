"""Recorre la interfaz como lo haría el usuario (sin mostrar ventanas)."""
from datetime import date

from PySide6.QtCore import QDate, QTimer
from PySide6.QtWidgets import QApplication

from app import dialogos
from app import ventana as V


def cerrar_dialogos_al_abrir(monkeypatch, capturados):
    def exec_falso(self):
        capturados.append(self)
        return 1
    monkeypatch.setattr(dialogos.DialogoRecibo, "exec", exec_falso)
    monkeypatch.setattr(V.DialogoRecibo, "exec", exec_falso)


def test_alta_desde_el_dialogo(ventana):
    d = dialogos.DialogoAlta(ventana.db, ventana)
    d.t_nombre.setText("Carlos Pérez")
    d.t_tel.setText("8441239999")
    d.filas[0].nombre.setText("Bruno Pérez")
    d.filas[0].fecha.setDate(QDate(2014, 5, 1))
    assert d.filas[0].categoria.currentText() == "2014"  # categoría sugerida por año
    d.agregar_jugador()
    d.filas[1].nombre.setText("Ana Pérez")
    d.filas[1].fecha.setDate(QDate(2016, 1, 1))
    d.filas[1].categoria.setCurrentIndex(d.filas[1].categoria.findText("Femenil"))
    d.guardar()
    assert d.resultado[1] == 2
    ventana.ir("jugadores")
    assert ventana.paginas["jugadores"].tabla.rowCount() == 2


def test_alta_incompleta_no_guarda(ventana, monkeypatch):
    errores = []
    monkeypatch.setattr(dialogos, "avisar_error", lambda padre, e: errores.append(str(e)))
    d = dialogos.DialogoAlta(ventana.db, ventana)
    d.t_nombre.setText("Sin teléfono")
    d.filas[0].nombre.setText("Niño")
    d.guardar()
    assert d.resultado is None and "10 dígitos" in errores[0]


def test_cobro_genera_recibo(ventana, monkeypatch):
    capturados = []
    cerrar_dialogos_al_abrir(monkeypatch, capturados)
    ventana.db.cargar_ejemplo()
    tutor = ventana.db.buscar_tutores("Laura")[0]
    ventana.ir_a_cobro(tutor["id"])
    pag = ventana.paginas["cobros"]
    pendientes = [b for _, _, b in pag.botones_mes]
    assert pendientes, "debe haber meses por cobrar"
    pendientes[0].setChecked(True)
    pendientes[1].setChecked(True)
    assert pag.btn_cobrar.isEnabled()
    assert pag.total.text() == "$1,200"
    pag.cobrar()
    assert len(capturados) == 1
    r = capturados[0].r
    assert r["total"] == 1200 and r["tutor"] == "Laura Treviño"
    assert not pag.btn_cobrar.isEnabled()  # la selección se limpia tras cobrar


def test_recibo_a_pdf(ventana, tmp_path):
    ventana.db.cargar_ejemplo()
    r = ventana.db.recibo(ventana.db.recibos()[0]["id"])
    d = dialogos.DialogoRecibo(r, ventana)
    ruta = d.guardar_pdf(str(tmp_path / "recibo.pdf"))
    with open(ruta, "rb") as f:
        assert f.read(4) == b"%PDF"


def test_navegacion_y_ajustes(ventana):
    ventana.ir("ajustes")
    aj = ventana.paginas["ajustes"]
    aj.club.setText("Nido Águila FC")
    aj.spins[0][1].setValue(700)
    aj.guardar()
    assert ventana.marca.text() == "Nido Águila FC"
    assert ventana.db.categorias()[0]["cuota"] == 700
    aj.cargar_ejemplo()
    assert ventana.pila.currentWidget() is ventana.paginas["jugadores"]
    assert ventana.stats[0][0].text() == "7"
    ventana.ir("recibos")
    assert ventana.paginas["recibos"].tabla.rowCount() > 20
    QTimer.singleShot(0, QApplication.instance().quit)
    assert date.today().year >= 2026
