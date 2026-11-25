"""Genera capturas de las pantallas con datos de ejemplo (no toca los datos reales).
Uso: python herramientas/capturas.py <carpeta_salida>"""
import os
import sys
import tempfile

os.environ["NIDO_CARPETA"] = tempfile.mkdtemp(prefix="nido_capturas_")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PySide6.QtGui import QFont  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from app import estilos  # noqa: E402
from app.dialogos import DialogoAlta, DialogoRecibo  # noqa: E402
from app.ventana import VentanaPrincipal  # noqa: E402

salida = sys.argv[1] if len(sys.argv) > 1 else "capturas"
os.makedirs(salida, exist_ok=True)
app = QApplication(sys.argv)
app.setFont(QFont("Segoe UI", 10))
app.setStyleSheet(estilos.QSS)
v = VentanaPrincipal()
v.show()


def foto(widget, nombre):
    app.processEvents()
    widget.grab().save(os.path.join(salida, nombre))


v.db.cargar_ejemplo()
v.refrescar_resumen()
v.ir("jugadores")
foto(v, "1-jugadores.png")

d = DialogoAlta(v.db, v)
d.t_nombre.setText("Carlos Pérez")
d.t_tel.setText("8441239999")
d.filas[0].nombre.setText("Bruno Pérez")
d.filas[0].fecha.poner(2009, 5, 1)
d.agregar_jugador()
d.show()
foto(d, "2-alta.png")
d.close()

v.ir_a_cobro(v.db.buscar_tutores("Laura")[0]["id"])
pag = v.paginas["cobros"]
for _, _, b in pag.botones_mes:
    if b.property("estado") == "adeudo":
        b.setChecked(True)
foto(v, "3-cobro.png")

pago = v.db.cobrar(pag.tutor_id, "Efectivo", pag.seleccion())
pag.mostrar_detalle()
r = DialogoRecibo(v.db.recibo(pago), v, recien_cobrado=True)
r.show()
foto(r, "4-recibo.png")
r.close()

v.ir("recibos")
foto(v, "5-recibos.png")
v.ir("ajustes")
foto(v, "6-ajustes.png")
v.close()
print("listo", salida)
