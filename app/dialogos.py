"""Ventanas emergentes: alta de jugadores, motivo de baja/cancelación y recibo."""
from urllib.parse import quote

from PySide6.QtCore import QDate, QUrl, Qt
from PySide6.QtGui import QDesktopServices, QIntValidator, QPageSize, QTextDocument
from PySide6.QtPrintSupport import QPrintDialog, QPrinter
from PySide6.QtWidgets import (QButtonGroup, QComboBox, QDateEdit, QDialog, QFileDialog, QFrame,
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
class FilaJugador(QFrame):
    """Un jugador dentro del alta (se pueden agregar hermanos)."""

    def __init__(self, categorias, db, al_quitar):
        super().__init__()
        self.db = db
        self.categoria_manual = False
        lay = QGridLayout(self)
        lay.setContentsMargins(0, 6, 0, 6)
        self.nombre = QLineEdit()
        self.nombre.setPlaceholderText("Nombre completo")
        self.fecha = QDateEdit()
        self.fecha.setCalendarPopup(True)
        self.fecha.setDisplayFormat("dd/MM/yyyy")
        self.fecha.setMinimumDate(QDate(2000, 1, 1))
        self.fecha.setMaximumDate(QDate.currentDate())
        self.fecha.setSpecialValueText("Elegir…")
        self.fecha.setDate(self.fecha.minimumDate())  # muestra "Elegir…" hasta que se capture
        self.categoria = QComboBox()
        self.categoria.addItem("Elegir…", None)
        for c in categorias:
            self.categoria.addItem(c["nombre"], c["id"])
        self.numero = QLineEdit()
        self.numero.setPlaceholderText("Núm.")
        self.numero.setMaxLength(3)
        self.numero.setValidator(QIntValidator(0, 999))
        self.quitar = boton("Quitar", "chicoPeligro")
        self.quitar.clicked.connect(lambda: al_quitar(self))
        for col, (txt, w) in enumerate([("Nombre completo*", self.nombre), ("Fecha de nacimiento*", self.fecha),
                                        ("Categoría*", self.categoria), ("Número", self.numero)]):
            et = QLabel(txt)
            et.setObjectName("suave")
            lay.addWidget(et, 0, col)
            lay.addWidget(w, 1, col)
        lay.addWidget(self.quitar, 1, 4)
        lay.setColumnStretch(0, 3)
        lay.setColumnStretch(1, 2)
        lay.setColumnStretch(2, 2)
        lay.setColumnStretch(3, 1)
        self.fecha.dateChanged.connect(self._sugerir_categoria)
        self.categoria.activated.connect(lambda _: setattr(self, "categoria_manual", True))

    def _sugerir_categoria(self, qd):
        if self.categoria_manual or qd == self.fecha.minimumDate():
            return
        c = self.db.categoria_por_anio(qd.year())
        if c:
            self.categoria.setCurrentIndex(self.categoria.findData(c["id"]))

    def datos(self):
        fecha = "" if self.fecha.date() == self.fecha.minimumDate() else self.fecha.date().toString("yyyy-MM-dd")
        return {"nombre": self.nombre.text(), "fecha_nac": fecha,
                "categoria_id": self.categoria.currentData(), "numero": self.numero.text()}


class DialogoAlta(QDialog):
    def __init__(self, db, padre=None):
        super().__init__(padre)
        self.db = db
        self.setWindowTitle("Alta de jugador")
        self.setMinimumSize(860, 640)
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

