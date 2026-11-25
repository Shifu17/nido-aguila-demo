"""Ventanas emergentes: alta de jugadores, motivo de baja/cancelación y recibo."""
import calendar
from datetime import date
from urllib.parse import quote

from PySide6.QtCore import QUrl, Qt, Signal
from PySide6.QtGui import QDesktopServices, QIntValidator, QPageSize, QTextDocument
from PySide6.QtPrintSupport import QPrintDialog, QPrinter
from PySide6.QtWidgets import (QButtonGroup, QComboBox, QDialog, QFileDialog, QFrame,
                               QGridLayout, QGroupBox, QHBoxLayout, QLabel, QLineEdit, QListWidget,
                               QListWidgetItem, QMessageBox, QPlainTextEdit, QPushButton, QRadioButton,
                               QScrollArea, QTextBrowser, QVBoxLayout, QWidget)

from app.db import ErrorUsuario, telefono_bonito
from app.recibo import html_recibo, texto_whatsapp


def avisar_error(padre, e):
    QMessageBox.warning(padre, "Revisa los datos", str(e))


def boton(texto, nombre=None):
    b = QPushButton(texto)
    if nombre:
        b.setObjectName(nombre)
    b.setCursor(Qt.PointingHandCursor)
    return b


def campo_telefono(placeholder="10 dígitos"):
    c = QLineEdit()
    c.setPlaceholderText(placeholder)
    c.setMaxLength(10)
    c.setValidator(QIntValidator(0, 2_147_483_647))  # solo números
    return c


# ====================================================================== alta
MESES_LARGOS = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre",
                "Octubre", "Noviembre", "Diciembre"]


class CampoFecha(QWidget):
    """Fecha de nacimiento con tres listas (día, mes, año): más fácil que un calendario."""
    cambio_anio = Signal(int)

    def __init__(self):
        super().__init__()
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(6)
        self.dia, self.mes, self.anio = QComboBox(), QComboBox(), QComboBox()
        self.dia.setToolTip("Día")
        self.mes.setToolTip("Mes")
        self.anio.setToolTip("Año")
        self.mes.addItem("Mes", None)
        for i, m in enumerate(MESES_LARGOS, 1):
            self.mes.addItem(m, i)
        self.anio.addItem("Año", None)
        hoy = date.today().year
        for a in range(hoy - 3, hoy - 31, -1):  # de los más chicos a los más grandes
            self.anio.addItem(str(a), a)
        self.anio.setMaxVisibleItems(15)
        self._llenar_dias()
        self.dia.setMinimumWidth(82)
        self.mes.setMinimumWidth(130)
        self.anio.setMinimumWidth(100)
        lay.addWidget(self.dia)
        lay.addWidget(self.mes, 1)
        lay.addWidget(self.anio)
        self.mes.currentIndexChanged.connect(self._llenar_dias)
        self.anio.currentIndexChanged.connect(self._llenar_dias)
        self.anio.currentIndexChanged.connect(lambda _: self.cambio_anio.emit(self.anio.currentData() or 0))

    def _llenar_dias(self, *_):
        """Ajusta los días al mes y año elegidos (30, 31 o febrero bisiesto)."""
        elegido = self.dia.currentData()
        m, a = self.mes.currentData(), self.anio.currentData() or 2000
        total = calendar.monthrange(a, m)[1] if m else 31
        self.dia.blockSignals(True)
        self.dia.clear()
        self.dia.addItem("Día", None)
        for d in range(1, total + 1):
            self.dia.addItem(str(d), d)
        if elegido:
            self.dia.setCurrentIndex(min(elegido, total))
        self.dia.blockSignals(False)

    def poner(self, anio, mes, dia):
        self.anio.setCurrentIndex(self.anio.findData(anio))
        self.mes.setCurrentIndex(self.mes.findData(mes))
        self.dia.setCurrentIndex(self.dia.findData(dia))

    def valor(self):
        """'AAAA-MM-DD' o '' si falta algún dato."""
        d, m, a = self.dia.currentData(), self.mes.currentData(), self.anio.currentData()
        return f"{a:04d}-{m:02d}-{d:02d}" if d and m and a else ""


class FilaJugador(QFrame):
    """Un jugador dentro del alta (se pueden agregar hermanos)."""

    def __init__(self, categorias, db, al_quitar):
        super().__init__()
        self.db = db
        self.id_femenil = next((c["id"] for c in categorias if c["nombre"] == "Femenil"), None)
        lay = QGridLayout(self)
        lay.setContentsMargins(0, 6, 0, 6)
        lay.setHorizontalSpacing(10)
        lay.setVerticalSpacing(4)
        self.nombre = QLineEdit()
        self.nombre.setPlaceholderText("Nombre y apellidos")
        self.fecha = CampoFecha()
        self.categoria = QComboBox()
        self.categoria.addItem("Elegir…", None)
        for c in categorias:
            self.categoria.addItem(c["nombre"], c["id"])
        self.categoria.setMinimumWidth(120)
        self.numero = QLineEdit()
        self.numero.setPlaceholderText("Núm.")
        self.numero.setMaxLength(3)
        self.numero.setFixedWidth(64)
        self.numero.setValidator(QIntValidator(0, 999))
        self.quitar = boton("Quitar", "chicoPeligro")
        self.quitar.clicked.connect(lambda: al_quitar(self))
        self.nota = QLabel("Se asigna sola al elegir el año")
        self.nota.setObjectName("nota")
        self.nota.setWordWrap(True)

        def titulo(txt):
            et = QLabel(txt)
            et.setObjectName("suave")
            return et

        # Renglón 1: nombre y número · Renglón 2: fecha y categoría (con su nota debajo)
        lay.addWidget(titulo("Nombre completo*"), 0, 0)
        lay.addWidget(titulo("Número"), 0, 2)
        lay.addWidget(self.nombre, 1, 0, 1, 2)
        lay.addWidget(self.numero, 1, 2)
        lay.addWidget(self.quitar, 1, 3)
        lay.addWidget(titulo("Fecha de nacimiento*"), 2, 0)
        lay.addWidget(titulo("Categoría*"), 2, 1)
        lay.addWidget(self.fecha, 3, 0)
        lay.addWidget(self.categoria, 3, 1, 1, 3)
        lay.addWidget(self.nota, 4, 1, 1, 3)
        lay.setColumnStretch(0, 3)
        lay.setColumnStretch(1, 2)
        lay.setRowMinimumHeight(2, 26)
        self.fecha.cambio_anio.connect(self._categoria_por_anio)
        self.categoria.activated.connect(self._categoria_elegida)

    def _categoria_por_anio(self, anio):
        # Femenil se elige a mano: si ya la eligieron, cambiar el año no la quita.
        if self.id_femenil and self.categoria.currentData() == self.id_femenil:
            return
        c = self.db.categoria_por_anio(anio) if anio else None
        self.categoria.setCurrentIndex(self.categoria.findData(c["id"]) if c else 0)
        if c:
            self.nota.setText(f"Automática: nació en {anio} → {c['nombre']}. Si es niña, cambia a Femenil.")
        elif anio:
            self.nota.setText(f"No hay categoría para {anio}; elígela a mano.")
        else:
            self.nota.setText("Se asigna sola al elegir el año")

    def _categoria_elegida(self, _):
        actual = self.categoria.currentText()
        if self.categoria.currentData() == self.id_femenil:
            self.nota.setText("Femenil (elegida a mano)")
        elif self.categoria.currentData():
            self.nota.setText(f"{actual} (elegida a mano)")

    def datos(self):
        return {"nombre": self.nombre.text(), "fecha_nac": self.fecha.valor(),
                "categoria_id": self.categoria.currentData(), "numero": self.numero.text()}


class DialogoAlta(QDialog):
    def __init__(self, db, padre=None):
        super().__init__(padre)
        self.db = db
        self.setWindowTitle("Alta de jugador")
        self.setMinimumSize(860, 700)
        self.tutor_elegido = None
        raiz = QVBoxLayout(self)
        raiz.setContentsMargins(22, 18, 22, 18)
        t = QLabel("Alta de jugador")
        t.setObjectName("seccion")
        raiz.addWidget(t)
        s = QLabel("Registra al tutor una sola vez y agrega a todos sus hijos; después se cobran juntos.")
        s.setObjectName("suave")
        raiz.addWidget(s)

        # --- Tutor
        caja_t = QGroupBox("Tutor")
        lt = QVBoxLayout(caja_t)
        modo = QHBoxLayout()
        self.r_nuevo = QRadioButton("Nuevo tutor")
        self.r_existente = QRadioButton("Tutor ya registrado")
        self.r_nuevo.setChecked(True)
        grupo = QButtonGroup(self)
        grupo.addButton(self.r_nuevo)
        grupo.addButton(self.r_existente)
        modo.addWidget(self.r_nuevo)
        modo.addWidget(self.r_existente)
        modo.addStretch()
        lt.addLayout(modo)

        self.panel_nuevo = QWidget()
        f = QGridLayout(self.panel_nuevo)
        f.setContentsMargins(0, 4, 0, 0)
        self.t_nombre = QLineEdit()
        self.t_tel = campo_telefono()
        self.t_correo = QLineEdit()
        self.t_correo.setPlaceholderText("opcional")
        self.e_nombre = QLineEdit()
        self.e_parentesco = QLineEdit()
        self.e_parentesco.setPlaceholderText("Abuela, tío…")
        self.e_tel = campo_telefono()
        campos = [("Nombre completo*", self.t_nombre, 0, 0), ("Teléfono principal (WhatsApp)*", self.t_tel, 0, 1),
                  ("Correo", self.t_correo, 0, 2), ("Contacto de emergencia", self.e_nombre, 2, 0),
                  ("Parentesco", self.e_parentesco, 2, 1), ("Teléfono de emergencia", self.e_tel, 2, 2)]
        for txt, w, fila, col in campos:
            et = QLabel(txt)
            et.setObjectName("suave")
            f.addWidget(et, fila, col)
            f.addWidget(w, fila + 1, col)
        lt.addWidget(self.panel_nuevo)

        self.panel_existente = QWidget()
        le = QVBoxLayout(self.panel_existente)
        le.setContentsMargins(0, 4, 0, 0)
        self.t_buscar = QLineEdit()
        self.t_buscar.setPlaceholderText("Buscar tutor por nombre, teléfono o hijo")
        self.t_lista = QListWidget()
        self.t_lista.setMinimumHeight(170)
        le.addWidget(self.t_buscar)
        le.addWidget(self.t_lista)
        self.panel_existente.hide()
        lt.addWidget(self.panel_existente)
        raiz.addWidget(caja_t)

        self.r_existente.toggled.connect(self._cambiar_modo)
        self.t_buscar.textChanged.connect(self._buscar_tutor)
        self.t_lista.currentItemChanged.connect(
            lambda it, _=None: setattr(self, "tutor_elegido", it.data(Qt.UserRole) if it else None))

        # --- Jugadores
        caja_j = QGroupBox("Jugadores")
        lj = QVBoxLayout(caja_j)
        self.cont_jugadores = QVBoxLayout()
        lj.addLayout(self.cont_jugadores)
        self.filas = []
        self.categorias = db.categorias()
        agregar = boton("+ Agregar hermano")
        agregar.clicked.connect(self.agregar_jugador)
        lj.addWidget(agregar, alignment=Qt.AlignLeft)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setWidget(caja_j)
        raiz.addWidget(scroll, 1)
        self.agregar_jugador()

        # --- Botones
        pie = QHBoxLayout()
        pie.addStretch()
        cancelar = boton("Cancelar")
        cancelar.clicked.connect(self.reject)
        guardar = boton("Guardar alta", "primario")
        guardar.setDefault(True)
        guardar.clicked.connect(self.guardar)
        pie.addWidget(cancelar)
        pie.addWidget(guardar)
        raiz.addLayout(pie)
        self.t_nombre.setFocus()
        self.resultado = None

    def agregar_jugador(self):
        fila = FilaJugador(self.categorias, self.db, self._quitar)
        self.filas.append(fila)
        self.cont_jugadores.addWidget(fila)
        self._actualizar_quitar()
        fila.nombre.setFocus()

    def _quitar(self, fila):
        self.filas.remove(fila)
        fila.deleteLater()
        self._actualizar_quitar()

    def _actualizar_quitar(self):
        for f in self.filas:
            f.quitar.setVisible(len(self.filas) > 1)

    def _cambiar_modo(self, existente):
        self.panel_nuevo.setVisible(not existente)
        self.panel_existente.setVisible(existente)
        if existente:
            self._buscar_tutor(self.t_buscar.text())
            self.t_buscar.setFocus()

    def _buscar_tutor(self, q):
        self.t_lista.clear()
        for t in self.db.buscar_tutores(q):
            it = QListWidgetItem(f"{t['nombre']}\n{telefono_bonito(t['telefono'])}"
                                 + (f" · {t['hijos']}" if t["hijos"] else ""))
            it.setData(Qt.UserRole, t["id"])
            self.t_lista.addItem(it)
        self.tutor_elegido = None

    def guardar(self):
        if self.r_existente.isChecked():
            if not self.tutor_elegido:
                avisar_error(self, "Elige al tutor de la lista.")
                return
            tutor = {"id": self.tutor_elegido}
        else:
            tutor = {"nombre": self.t_nombre.text(), "telefono": self.t_tel.text(), "correo": self.t_correo.text(),
                     "emergencia_nombre": self.e_nombre.text(), "emergencia_parentesco": self.e_parentesco.text(),
                     "emergencia_telefono": self.e_tel.text()}
        try:
            self.resultado = self.db.crear_alta(tutor, [f.datos() for f in self.filas])
        except ErrorUsuario as e:
            avisar_error(self, e)
            return
        self.accept()


# ====================================================================== motivo
class DialogoMotivo(QDialog):
    """Pide un motivo obligatorio (baja de jugador o cancelación de recibo)."""

    def __init__(self, titulo, explicacion, texto_boton, accion, padre=None):
        super().__init__(padre)
        self.accion = accion
        self.setWindowTitle(titulo)
        self.setMinimumWidth(480)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(22, 18, 22, 18)
        t = QLabel(titulo)
        t.setObjectName("seccion")
        e = QLabel(explicacion)
        e.setObjectName("suave")
        e.setWordWrap(True)
        et = QLabel("Motivo*")
        et.setObjectName("suave")
        self.motivo = QPlainTextEdit()
        self.motivo.setFixedHeight(90)
        lay.addWidget(t)
        lay.addWidget(e)
        lay.addSpacing(6)
        lay.addWidget(et)
        lay.addWidget(self.motivo)
        pie = QHBoxLayout()
        pie.addStretch()
        volver = boton("Volver")
        volver.clicked.connect(self.reject)
        ok = boton(texto_boton, "primario")
        ok.clicked.connect(self._aceptar)
        pie.addWidget(volver)
        pie.addWidget(ok)
        lay.addLayout(pie)
        self.motivo.setFocus()

    def _aceptar(self):
        try:
            self.accion(self.motivo.toPlainText())
        except ErrorUsuario as e:
            avisar_error(self, e)
            return
        self.accept()


# ====================================================================== recibo
class DialogoRecibo(QDialog):
    def __init__(self, recibo, padre=None, recien_cobrado=False):
        super().__init__(padre)
        self.r = recibo
        self.setWindowTitle(f"Recibo {recibo['folio']}")
        self.setMinimumSize(520, 640)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(22, 18, 22, 18)
        t = QLabel(f"Recibo {recibo['folio']}")
        t.setObjectName("seccion")
        lay.addWidget(t)
        nota = ("Pago registrado. Imprímelo, guárdalo en PDF o avísale al tutor por WhatsApp."
                if recien_cobrado else ("Este recibo está cancelado." if recibo["cancelado"] else "Recibo emitido."))
        n = QLabel(nota)
        n.setObjectName("suave")
        lay.addWidget(n)
        self.vista = QTextBrowser()
        self.vista.setStyleSheet("QTextBrowser { border: 0; background: #f4f6f9; border-radius: 10px; padding: 12px; }")
        self.vista.setHtml(html_recibo(recibo))
        lay.addWidget(self.vista, 1)
        pie = QHBoxLayout()
        cerrar = boton("Cerrar")
        cerrar.clicked.connect(self.accept)
        wa = boton("WhatsApp al tutor")
        wa.setEnabled(not recibo["cancelado"])
        wa.clicked.connect(self.whatsapp)
        pdf = boton("Guardar PDF")
        pdf.clicked.connect(self.guardar_pdf)
        imprimir = boton("Imprimir", "primario")
        imprimir.clicked.connect(self.imprimir)
        pie.addWidget(cerrar)
        pie.addStretch()
        pie.addWidget(wa)
        pie.addWidget(pdf)
        pie.addWidget(imprimir)
        lay.addLayout(pie)
        imprimir.setFocus()

    def _documento(self):
        doc = QTextDocument()
        doc.setHtml(html_recibo(self.r))
        return doc

    def imprimir(self):
        impresora = QPrinter(QPrinter.HighResolution)
        if QPrintDialog(impresora, self).exec() == QDialog.Accepted:
            self._documento().print_(impresora)

    def guardar_pdf(self, ruta=None):
        if not ruta:
            sugerido = f"Recibo {self.r['folio'].replace('/', '-')} {self.r['tutor']}.pdf"
            ruta, _ = QFileDialog.getSaveFileName(self, "Guardar recibo en PDF", sugerido, "PDF (*.pdf)")
        if not ruta:
            return None
        impresora = QPrinter(QPrinter.HighResolution)
        impresora.setOutputFormat(QPrinter.PdfFormat)
        impresora.setPageSize(QPageSize(QPageSize.Letter))
        impresora.setOutputFileName(ruta)
        self._documento().print_(impresora)
        return ruta

    def whatsapp(self):
        tel = self.r.get("telefono") or ""
        if len(tel) != 10:
            avisar_error(self, "El tutor no tiene un teléfono de 10 dígitos.")
            return
        QDesktopServices.openUrl(QUrl(f"https://wa.me/52{tel}?text={quote(texto_whatsapp(self.r))}"))

