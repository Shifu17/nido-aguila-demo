"""Ventana principal: barra lateral y las páginas Jugadores, Cobro, Recibos y Ajustes."""
import os
from datetime import date

from PySide6.QtCore import QTimer, QUrl, Qt
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (QAbstractItemView, QAbstractSpinBox, QComboBox, QDoubleSpinBox, QFrame, QGridLayout, QHBoxLayout,
                               QHeaderView, QLabel, QLineEdit, QListWidget, QListWidgetItem, QMainWindow,
                               QPushButton, QScrollArea, QSizePolicy, QStackedWidget,
                               QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget)

from app import __version__
from app.db import MESES, METODOS, Database, ErrorUsuario, dinero, telefono_bonito
from app.dialogos import DialogoAlta, DialogoMotivo, DialogoRecibo, avisar_error, boton


def fecha_corta(iso):
    if not iso:
        return ""
    y, m, d = iso[:10].split("-")
    return f"{d}/{m}/{y}"


def etiqueta(texto, nombre=None, envolver=False):
    l = QLabel(texto)
    if nombre:
        l.setObjectName(nombre)
    l.setWordWrap(envolver)
    return l


def badge_categoria(nombre):
    b = etiqueta(nombre, "badgeFem" if nombre == "Femenil" else "badge")
    b.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Fixed)
    return b


def encabezado(titulo, subtitulo, boton_derecha=None):
    caja = QHBoxLayout()
    textos = QVBoxLayout()
    textos.setSpacing(2)
    textos.addWidget(etiqueta(titulo, "titulo"))
    textos.addWidget(etiqueta(subtitulo, "subtitulo"))
    caja.addLayout(textos)
    caja.addStretch()
    if boton_derecha:
        caja.addWidget(boton_derecha, alignment=Qt.AlignTop)
    return caja


def celda(texto, alinear=None, negrita=False):
    it = QTableWidgetItem(texto)
    it.setFlags(it.flags() & ~Qt.ItemIsEditable)
    if alinear:
        it.setTextAlignment(alinear | Qt.AlignVCenter)
    if negrita:
        f = it.font()
        f.setBold(True)
        it.setFont(f)
    return it


def tabla(columnas):
    t = QTableWidget(0, len(columnas))
    t.setHorizontalHeaderLabels(columnas)
    t.verticalHeader().hide()
    t.setShowGrid(False)
    t.setSelectionBehavior(QAbstractItemView.SelectRows)
    t.setSelectionMode(QAbstractItemView.SingleSelection)
    t.setFocusPolicy(Qt.NoFocus)
    t.verticalHeader().setDefaultSectionSize(52)
    t.horizontalHeader().setHighlightSections(False)
    t.horizontalHeader().setDefaultAlignment(Qt.AlignLeft | Qt.AlignVCenter)
    return t


def fijar_columna(t, col, ancho):
    t.horizontalHeader().setSectionResizeMode(col, QHeaderView.Fixed)
    t.setColumnWidth(col, ancho)


def campo_dinero(valor):
    s = QDoubleSpinBox()
    s.setRange(0, 100000)
    s.setDecimals(0)
    s.setSingleStep(50)
    s.setPrefix("$ ")
    s.setButtonSymbols(QAbstractSpinBox.NoButtons)
    s.setAlignment(Qt.AlignRight)
    s.setFixedSize(110, 34)
    s.setValue(valor)
    return s


def acciones(*botones):
    w = QWidget()
    lay = QHBoxLayout(w)
    lay.setContentsMargins(6, 0, 6, 0)
    lay.setSpacing(6)
    lay.addStretch()
    for b in botones:
        lay.addWidget(b)
    return w


def con_retraso(funcion, ms=200):
    t = QTimer()
    t.setSingleShot(True)
    t.setInterval(ms)
    t.timeout.connect(funcion)
    return t


# ====================================================================== jugadores
class PaginaJugadores(QWidget):
    def __init__(self, ventana):
        super().__init__()
        self.v = ventana
        self.db = ventana.db
        lay = QVBoxLayout(self)
        lay.setContentsMargins(32, 26, 32, 26)
        lay.setSpacing(14)
        alta = boton("+ Alta de jugador", "primario")
        alta.clicked.connect(self.alta)
        lay.addLayout(encabezado("Jugadores", "Alta de jugadores con su tutor y teléfonos de emergencia.", alta))

        filtros = QHBoxLayout()
        self.buscar = QLineEdit()
        self.buscar.setPlaceholderText("Buscar por jugador, tutor, teléfono o número")
        self.buscar.setClearButtonEnabled(True)
        self.categoria = QComboBox()
        self.estatus = QComboBox()
        for txt, val in [("Activos", "activo"), ("Bajas", "baja"), ("Todos", "todos")]:
            self.estatus.addItem(txt, val)
        filtros.addWidget(self.buscar, 1)
        filtros.addWidget(self.categoria)
        filtros.addWidget(self.estatus)
        lay.addLayout(filtros)

        self.tabla = tabla(["#", "Jugador", "Nacimiento", "Categoría", "Tutor", "Teléfono", "Alta", "Estatus", ""])
        h = self.tabla.horizontalHeader()
        h.setSectionResizeMode(QHeaderView.ResizeToContents)
        h.setSectionResizeMode(1, QHeaderView.Stretch)
        h.setSectionResizeMode(4, QHeaderView.Stretch)
        fijar_columna(self.tabla, 3, 120)
        fijar_columna(self.tabla, 8, 180)
        self.vacio = etiqueta("", "vacio", envolver=True)
        self.vacio.setAlignment(Qt.AlignCenter)
        self.cuenta = etiqueta("", "suave")
        lay.addWidget(self.tabla, 1)
        lay.addWidget(self.vacio, 1)
        lay.addWidget(self.cuenta)

        self._timer = con_retraso(self.refrescar)
        self.buscar.textChanged.connect(self._timer.start)
        self.categoria.currentIndexChanged.connect(self.refrescar)
        self.estatus.currentIndexChanged.connect(self.refrescar)
        self.recargar_categorias()

    def recargar_categorias(self):
        actual = self.categoria.currentData()
        self.categoria.blockSignals(True)
        self.categoria.clear()
        self.categoria.addItem("Todas las categorías", None)
        for c in self.db.categorias():
            self.categoria.addItem(c["nombre"], c["id"])
        self.categoria.setCurrentIndex(max(0, self.categoria.findData(actual)))
        self.categoria.blockSignals(False)

    def refrescar(self):
        filas = self.db.jugadores(self.buscar.text(), self.categoria.currentData(), self.estatus.currentData())
        self.tabla.setRowCount(len(filas))
        for i, j in enumerate(filas):
            activo = j["estatus"] == "activo"
            self.tabla.setItem(i, 0, celda(j["numero"] or "—"))
            self.tabla.setItem(i, 1, celda(j["nombre"], negrita=True))
            self.tabla.setItem(i, 2, celda(fecha_corta(j["fecha_nac"])))
            self.tabla.setCellWidget(i, 3, acciones(badge_categoria(j["categoria"])))
            self.tabla.setItem(i, 4, celda(j["tutor"]))
            self.tabla.setItem(i, 5, celda(telefono_bonito(j["telefono"])))
            self.tabla.setItem(i, 6, celda(fecha_corta(j["fecha_alta"])))
            est = celda("Activo" if activo else f"Baja {fecha_corta(j['fecha_baja'])}")
            est.setForeground(Qt.darkGreen if activo else Qt.darkRed)
            if not activo:
                est.setToolTip(f"Motivo: {j['motivo_baja']}")
            self.tabla.setItem(i, 7, est)
            if activo:
                cobrar = boton("Cobrar", "chico")
                cobrar.clicked.connect(lambda _=False, t=j["tutor_id"]: self.v.ir_a_cobro(t))
                baja = boton("Baja", "chicoPeligro")
                baja.clicked.connect(lambda _=False, x=j: self.baja(x))
                self.tabla.setCellWidget(i, 8, acciones(cobrar, baja))
            else:
                re = boton("Reactivar", "chico")
                re.clicked.connect(lambda _=False, x=j: self.reactivar(x))
                self.tabla.setCellWidget(i, 8, acciones(re))
        sin_filtro = not self.buscar.text() and self.categoria.currentData() is None \
            and self.estatus.currentData() == "activo"
        self.vacio.setText("Aún no hay jugadores.\nRegistra el primero con “Alta de jugador”. Para probar, en Ajustes "
                           "puedes cargar datos de ejemplo." if sin_filtro
                           else "Sin resultados.\nPrueba con otro nombre, teléfono o categoría.")
        self.tabla.setVisible(bool(filas))
        self.vacio.setVisible(not filas)
        self.cuenta.setText(f"{len(filas)} jugador{'' if len(filas) == 1 else 'es'}" if filas else "")

    def alta(self):
        d = DialogoAlta(self.db, self)
        if d.exec():
            n = d.resultado[1]
            self.buscar.clear()
            self.estatus.setCurrentIndex(0)
            self.refrescar()
            self.v.refrescar_resumen()
            self.v.aviso("Jugador registrado." if n == 1 else f"{n} jugadores registrados.")

    def baja(self, j):
        d = DialogoMotivo(f"Dar de baja a {j['nombre']}",
                          "El jugador sale de la lista de activos y ya no aparece para cobro. Su historial de pagos "
                          "se conserva y se puede reactivar después.", "Dar de baja",
                          lambda motivo: self.db.dar_baja(j["id"], motivo), self)
        if d.exec():
            self.refrescar()
            self.v.refrescar_resumen()
            self.v.aviso(f"{j['nombre']} quedó dado de baja.")

    def reactivar(self, j):
        self.db.reactivar(j["id"])
        self.refrescar()
        self.v.refrescar_resumen()
        self.v.aviso(f"{j['nombre']} fue reactivado.")


# ====================================================================== cobro
class PaginaCobros(QWidget):
    def __init__(self, ventana):
        super().__init__()
        self.v = ventana
        self.db = ventana.db
        self.tutor_id = None
        self.anio = date.today().year
        self.cuotas = {}       # jugador_id -> QDoubleSpinBox
        self.botones_mes = []  # (jugador_id, mes, QPushButton)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(32, 26, 32, 26)
        lay.setSpacing(14)
        lay.addLayout(encabezado("Cobro de mensualidades", "Busca al tutor, marca los meses de cada hijo y genera el recibo."))

        cuerpo = QHBoxLayout()
        cuerpo.setSpacing(16)
        izq = QFrame()
        izq.setObjectName("tarjeta")
        izq.setFixedWidth(320)
        li = QVBoxLayout(izq)
        li.setContentsMargins(14, 14, 14, 14)
        self.buscar = QLineEdit()
        self.buscar.setPlaceholderText("Tutor, jugador o teléfono")
        self.buscar.setClearButtonEnabled(True)
        self.lista = QListWidget()
        li.addWidget(self.buscar)
        li.addWidget(self.lista, 1)
        cuerpo.addWidget(izq)

        der = QVBoxLayout()
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        der.addWidget(self.scroll, 1)

        self.barra = QFrame()
        self.barra.setObjectName("barraPago")
        lb = QHBoxLayout(self.barra)
        lb.setContentsMargins(16, 12, 16, 12)
        totales = QVBoxLayout()
        totales.setSpacing(0)
        self.total = etiqueta("$0", "total")
        self.cuenta = etiqueta("Marca los meses a cobrar", "suave")
        totales.addWidget(self.total)
        totales.addWidget(self.cuenta)
        lb.addLayout(totales, 1)
        self.metodo = QComboBox()
        self.metodo.addItems(METODOS)
        self.referencia = QLineEdit()
        self.referencia.setPlaceholderText("Referencia (opcional)")
        self.referencia.setFixedWidth(150)
        self.metodo.setFixedWidth(135)
        self.btn_cobrar = boton("Cobrar y generar recibo", "primario")
        self.btn_cobrar.setMinimumWidth(self.btn_cobrar.sizeHint().width() + 24)
        self.btn_cobrar.clicked.connect(self.cobrar)
        lb.addWidget(self.metodo)
        lb.addWidget(self.referencia)
        lb.addWidget(self.btn_cobrar)
        der.addWidget(self.barra)
        cuerpo.addLayout(der, 1)
        lay.addLayout(cuerpo, 1)

        self._timer = con_retraso(self.buscar_tutores)
        self.buscar.textChanged.connect(self._timer.start)
        self.lista.itemClicked.connect(lambda it: self.elegir(it.data(Qt.UserRole)))

    def refrescar(self):
        self.buscar_tutores()
        self.mostrar_detalle()

    def buscar_tutores(self):
        self.lista.clear()
        for t in self.db.buscar_tutores(self.buscar.text(), solo_con_activos=True):
            it = QListWidgetItem(f"{t['nombre']}\n{t['hijos']}\n{telefono_bonito(t['telefono'])}")
            it.setData(Qt.UserRole, t["id"])
            self.lista.addItem(it)
            if t["id"] == self.tutor_id:
                it.setSelected(True)
                self.lista.setCurrentItem(it)

    def elegir(self, tutor_id):
        self.tutor_id = tutor_id
        self.mostrar_detalle()

    def mostrar_detalle(self):
        self.cuotas.clear()
        self.botones_mes.clear()
        cont = QWidget()
        cont.setObjectName("contenido")
        lay = QVBoxLayout(cont)
        lay.setContentsMargins(0, 0, 8, 0)
        tarjeta = QFrame()
        tarjeta.setObjectName("tarjeta")
        lt = QVBoxLayout(tarjeta)
        lt.setContentsMargins(18, 16, 18, 16)
        lay.addWidget(tarjeta)
        lay.addStretch()

        tutor = self.db.tutor(self.tutor_id) if self.tutor_id else None
        self.barra.setVisible(bool(tutor))
        if not tutor:
            v = etiqueta("Elige un tutor de la lista.\nAparecerán sus hijos con los meses pagados y pendientes.",
                         "suave", envolver=True)
            v.setAlignment(Qt.AlignCenter)
            v.setMinimumHeight(220)
            lt.addWidget(v)
            self.scroll.setWidget(cont)
            return

        cab = QHBoxLayout()
        datos = QVBoxLayout()
        datos.addWidget(etiqueta(tutor["nombre"], "seccion"))
        emer = (f"Emergencia: {tutor['emergencia_nombre']}"
                + (f" ({tutor['emergencia_parentesco']})" if tutor["emergencia_parentesco"] else "")
                + f" · {telefono_bonito(tutor['emergencia_telefono'])}") if tutor["emergencia_nombre"] \
            else "Sin contacto de emergencia"
        datos.addWidget(etiqueta(f"Tel. {telefono_bonito(tutor['telefono'])} · {emer}", "suave"))
        cab.addLayout(datos)
        cab.addStretch()
        menos, mas = boton("‹", "chico"), boton("›", "chico")
        menos.setToolTip("Año anterior")
        mas.setToolTip("Año siguiente")
        menos.clicked.connect(lambda: self.cambiar_anio(-1))
        mas.clicked.connect(lambda: self.cambiar_anio(1))
        anio = etiqueta(str(self.anio), "seccion")
        cab.addWidget(menos)
        cab.addWidget(anio)
        cab.addWidget(mas)
        lt.addLayout(cab)

        hoy = date.today()
        mes_actual = f"{hoy.year}-{hoy.month:02d}"
        jugadores = self.db.estado_cuenta(self.tutor_id, self.anio)
        if not jugadores:
            lt.addWidget(etiqueta("Este tutor no tiene jugadores activos.", "suave"))
        for j in jugadores:
            linea = QFrame()
            linea.setFrameShape(QFrame.HLine)
            linea.setStyleSheet("color: #dfe5ec")
            lt.addWidget(linea)
            fila = QHBoxLayout()
            fila.addWidget(etiqueta(j["nombre"], "seccion"))
            fila.addWidget(badge_categoria(j["categoria"]))
            fila.addStretch()
            fila.addWidget(etiqueta("Cuota mensual", "suave"))
            cuota = campo_dinero(j["cuota"])
            cuota.valueChanged.connect(self.actualizar_total)
            self.cuotas[j["id"]] = cuota
            fila.addWidget(cuota)
            lt.addLayout(fila)

            meses = QGridLayout()
            meses.setSpacing(6)
            for i, nombre in enumerate(MESES):
                mes = f"{self.anio}-{i + 1:02d}"
                folio = j["pagados"].get(mes)
                b = QPushButton()
                b.setObjectName("mes")
                if folio:
                    b.setText(f"{nombre}\npagado")
                    b.setProperty("estado", "pagado")
                    b.setToolTip(f"Pagado · folio {folio}")
                    b.setFocusPolicy(Qt.NoFocus)
                else:
                    vencido = mes < mes_actual
                    b.setText(f"{nombre}\nadeudo" if vencido else nombre)
                    b.setProperty("estado", "adeudo" if vencido else "pendiente")
                    b.setToolTip("Adeudo: clic para cobrar" if vencido else "Pendiente: clic para cobrar")
                    b.setCheckable(True)
                    b.setCursor(Qt.PointingHandCursor)
                    b.toggled.connect(self.actualizar_total)
                    self.botones_mes.append((j["id"], mes, b))
                b.setMinimumWidth(0)
                b.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Fixed)
                meses.addWidget(b, 0, i)
                meses.setColumnStretch(i, 1)
            lt.addLayout(meses)

        leyenda = etiqueta("■ Verde: pagado (pasa el cursor para ver el folio)   ■ Rojo: adeudo   ■ Azul: seleccionado para cobrar", "suave")
        lt.addSpacing(6)
        lt.addWidget(leyenda)
        self.scroll.setWidget(cont)
        self.actualizar_total()

    def cambiar_anio(self, delta):
        self.anio += delta
        self.mostrar_detalle()

    def seleccion(self):
        return [(jid, mes, self.cuotas[jid].value()) for jid, mes, b in self.botones_mes if b.isChecked()]

    def actualizar_total(self, *_):
        items = self.seleccion()
        self.total.setText(dinero(sum(x[2] for x in items)))
        n = len(items)
        self.cuenta.setText(f"{n} mes{'' if n == 1 else 'es'} seleccionado{'' if n == 1 else 's'}"
                            if n else "Marca los meses a cobrar")
        self.btn_cobrar.setEnabled(bool(n))

    def cobrar(self):
        try:
            pago_id = self.db.cobrar(self.tutor_id, self.metodo.currentText(), self.seleccion(), self.referencia.text())
        except ErrorUsuario as e:
            avisar_error(self, e)
            return
        self.referencia.clear()
        self.mostrar_detalle()
        self.v.refrescar_resumen()
        DialogoRecibo(self.db.recibo(pago_id), self, recien_cobrado=True).exec()


# ====================================================================== recibos
class PaginaRecibos(QWidget):
    def __init__(self, ventana):
        super().__init__()
        self.v = ventana
        self.db = ventana.db
        lay = QVBoxLayout(self)
        lay.setContentsMargins(32, 26, 32, 26)
        lay.setSpacing(14)
        lay.addLayout(encabezado("Recibos", "Todos los recibos emitidos. Uno equivocado se cancela con motivo; nunca se borra."))
        self.buscar = QLineEdit()
        self.buscar.setPlaceholderText("Buscar por folio, tutor o jugador")
        self.buscar.setClearButtonEnabled(True)
        lay.addWidget(self.buscar)
        self.tabla = tabla(["Folio", "Fecha", "Tutor", "Meses", "Método", "Total", "Estatus", ""])
        h = self.tabla.horizontalHeader()
        h.setSectionResizeMode(QHeaderView.ResizeToContents)
        h.setSectionResizeMode(2, QHeaderView.Stretch)
        fijar_columna(self.tabla, 7, 180)
        self.vacio = etiqueta("", "vacio", envolver=True)
        self.vacio.setAlignment(Qt.AlignCenter)
        lay.addWidget(self.tabla, 1)
        lay.addWidget(self.vacio, 1)
        self._timer = con_retraso(self.refrescar)
        self.buscar.textChanged.connect(self._timer.start)

    def refrescar(self):
        filas = self.db.recibos(self.buscar.text())
        self.tabla.setRowCount(len(filas))
        derecha = Qt.AlignRight
        for i, r in enumerate(filas):
            self.tabla.setItem(i, 0, celda(r["folio"], negrita=True))
            self.tabla.setItem(i, 1, celda(f"{fecha_corta(r['fecha'])}  {r['fecha'][11:16]}"))
            self.tabla.setItem(i, 2, celda(r["tutor"]))
            self.tabla.setItem(i, 3, celda(str(r["conceptos"]), derecha))
            self.tabla.setItem(i, 4, celda(r["metodo"]))
            self.tabla.setItem(i, 5, celda(dinero(r["total"]), derecha, negrita=True))
            est = celda("Cancelado" if r["cancelado"] else "Vigente")
            est.setForeground(Qt.darkRed if r["cancelado"] else Qt.darkGreen)
            self.tabla.setItem(i, 6, est)
            ver = boton("Ver", "chico")
            ver.clicked.connect(lambda _=False, x=r["id"]: DialogoRecibo(self.db.recibo(x), self).exec())
            botones = [ver]
            if not r["cancelado"]:
                cancelar = boton("Cancelar", "chicoPeligro")
                cancelar.clicked.connect(lambda _=False, x=r: self.cancelar(x))
                botones.append(cancelar)
            self.tabla.setCellWidget(i, 7, acciones(*botones))
        q = self.buscar.text()
        self.vacio.setText("Sin resultados.\nPrueba con otro folio o nombre." if q
                           else "Aún no hay recibos.\nSe generan al cobrar mensualidades.")
        self.tabla.setVisible(bool(filas))
        self.vacio.setVisible(not filas)

    def cancelar(self, r):
        d = DialogoMotivo(f"Cancelar recibo {r['folio']}",
                          "El recibo queda marcado como cancelado y sus meses vuelven a quedar pendientes. "
                          "El folio no se reutiliza.", "Cancelar recibo",
                          lambda motivo: self.db.cancelar_recibo(r["id"], motivo), self)
        if d.exec():
            self.refrescar()
            self.v.refrescar_resumen()
            self.v.aviso("Recibo cancelado.")


# ====================================================================== ajustes
class PaginaAjustes(QWidget):
    def __init__(self, ventana):
        super().__init__()
        self.v = ventana
        self.db = ventana.db
        lay = QVBoxLayout(self)
        lay.setContentsMargins(32, 26, 32, 26)
        lay.setSpacing(14)
        lay.addLayout(encabezado("Ajustes", "Nombre del club y cuota mensual de cada categoría."))
        cuerpo = QHBoxLayout()
        cuerpo.setSpacing(16)

        izq = QFrame()
        izq.setObjectName("tarjeta")
        li = QVBoxLayout(izq)
        li.setContentsMargins(18, 16, 18, 16)
        li.addWidget(etiqueta("Nombre del club", "suave"))
        self.club = QLineEdit()
        li.addWidget(self.club)
        li.addSpacing(8)
        li.addWidget(etiqueta("Cuotas por categoría", "seccion"))
        self.rejilla = QGridLayout()
        self.rejilla.setVerticalSpacing(8)
        self.rejilla.setColumnStretch(1, 1)
        li.addLayout(self.rejilla)
        li.addStretch()
        guardar = boton("Guardar ajustes", "primario")
        guardar.clicked.connect(self.guardar)
        li.addWidget(guardar, alignment=Qt.AlignRight)
        cuerpo.addWidget(izq, 1)

        der = QFrame()
        der.setObjectName("tarjeta")
        ld = QVBoxLayout(der)
        ld.setContentsMargins(18, 16, 18, 16)
        ld.addWidget(etiqueta("Datos", "seccion"))
        ld.addWidget(etiqueta("La base de datos vive en esta computadora:", "suave"))
        ruta = etiqueta(os.path.dirname(self.db.archivo), envolver=True)
        ruta.setTextInteractionFlags(Qt.TextSelectableByMouse)
        ld.addWidget(ruta)
        abrir = boton("Abrir carpeta de datos")
        abrir.clicked.connect(lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(os.path.dirname(self.db.archivo))))
        ld.addWidget(abrir, alignment=Qt.AlignLeft)
        ld.addSpacing(16)
        ld.addWidget(etiqueta("Demostración", "seccion"))
        ld.addWidget(etiqueta("Carga 5 familias de ejemplo con sus pagos del año para mostrar el sistema. "
                              "Solo funciona si aún no hay jugadores.", "suave", envolver=True))
        ejemplo = boton("Cargar datos de ejemplo", "dorado")
        ejemplo.clicked.connect(self.cargar_ejemplo)
        ld.addWidget(ejemplo, alignment=Qt.AlignLeft)
        ld.addStretch()
        ld.addWidget(etiqueta(f"Versión {__version__} (demo)", "suave"))
        cuerpo.addWidget(der, 1)
        lay.addLayout(cuerpo, 1)
        self.spins = []

    def refrescar(self):
        self.club.setText(self.db.club())
        while self.rejilla.count():
            w = self.rejilla.takeAt(0).widget()
            if w:
                w.deleteLater()
        self.spins = []
        for i, c in enumerate(self.db.categorias()):
            self.rejilla.addWidget(badge_categoria(c["nombre"]), i, 0)
            anios = ("Se elige a mano" if not c["anio_desde"] else
                     str(c["anio_desde"]) if c["anio_desde"] == c["anio_hasta"] else f"{c['anio_desde']}–{c['anio_hasta']}")
            self.rejilla.addWidget(etiqueta(anios, "suave"), i, 1)
            s = campo_dinero(c["cuota"])
            self.rejilla.addWidget(s, i, 2)
            self.spins.append((c["id"], s))

    def guardar(self):
        try:
            self.db.guardar_ajustes(self.club.text(), [(i, s.value()) for i, s in self.spins])
        except ErrorUsuario as e:
            avisar_error(self, e)
            return
        self.v.actualizar_club()
        self.v.aviso("Ajustes guardados.")

    def cargar_ejemplo(self):
        try:
            self.db.cargar_ejemplo()
        except ErrorUsuario as e:
            avisar_error(self, e)
            return
        self.v.refrescar_resumen()
        self.v.aviso("Datos de ejemplo cargados.")
        self.v.ir("jugadores")


# ====================================================================== ventana
class VentanaPrincipal(QMainWindow):
    PAGINAS = [("jugadores", "Jugadores"), ("cobros", "Cobro de mensualidades"), ("recibos", "Recibos"), ("ajustes", "Ajustes")]

    def __init__(self, db=None):
        super().__init__()
        self.db = db or Database()
        self.setMinimumSize(1180, 720)
        self.resize(1320, 840)

        central = QWidget()
        raiz = QHBoxLayout(central)
        raiz.setContentsMargins(0, 0, 0, 0)
        raiz.setSpacing(0)
        self.setCentralWidget(central)

        lateral = QFrame()
        lateral.setObjectName("lateral")
        lateral.setFixedWidth(250)
        ll = QVBoxLayout(lateral)
        ll.setContentsMargins(14, 20, 14, 16)
        ll.setSpacing(6)
        marca = QHBoxLayout()
        logo = etiqueta("NA", "logo")
        logo.setFixedSize(44, 44)
        logo.setAlignment(Qt.AlignCenter)
        nombres = QVBoxLayout()
        nombres.setSpacing(0)
        self.marca = etiqueta("", "marca")
        nombres.addWidget(self.marca)
        nombres.addWidget(etiqueta("Control del club", "marcaSub"))
        marca.addWidget(logo)
        marca.addLayout(nombres)
        marca.addStretch()
        ll.addLayout(marca)
        ll.addSpacing(16)

        self.pila = QStackedWidget()
        self.pila.setObjectName("contenido")
        self.paginas = {"jugadores": PaginaJugadores(self), "cobros": PaginaCobros(self),
                        "recibos": PaginaRecibos(self), "ajustes": PaginaAjustes(self)}
        self.nav = {}
        for clave, texto in self.PAGINAS:
            b = boton(texto, "nav")
            b.setCheckable(True)
            b.setAutoExclusive(True)
            b.clicked.connect(lambda _=False, c=clave: self.ir(c))
            ll.addWidget(b)
            self.nav[clave] = b
            self.pila.addWidget(self.paginas[clave])
        ll.addStretch()

        self.stats = []
        for _ in range(2):
            caja = QFrame()
            caja.setObjectName("stat")
            lc = QVBoxLayout(caja)
            lc.setContentsMargins(14, 10, 14, 10)
            lc.setSpacing(0)
            num, txt = etiqueta("", "statNum"), etiqueta("", "statTxt")
            lc.addWidget(num)
            lc.addWidget(txt)
            ll.addWidget(caja)
            self.stats.append((num, txt))
        ll.addSpacing(6)
        ll.addWidget(etiqueta(f"Demo v{__version__}", "version"))

        raiz.addWidget(lateral)
        raiz.addWidget(self.pila, 1)

        self.aviso_lbl = QLabel(self)
        self.aviso_lbl.setStyleSheet("background:#0f2a44; color:white; padding:10px 16px; border-radius:10px;")
        self.aviso_lbl.hide()
        self._aviso_timer = con_retraso(self.aviso_lbl.hide, 3500)

        self.actualizar_club()
        self.refrescar_resumen()
        self.ir("jugadores")

    def actualizar_club(self):
        club = self.db.club()
        self.marca.setText(club)
        self.setWindowTitle(club)

    def ir(self, clave):
        self.nav[clave].setChecked(True)
        self.pila.setCurrentWidget(self.paginas[clave])
        self.paginas[clave].refrescar()

    def ir_a_cobro(self, tutor_id):
        cobros = self.paginas["cobros"]
        cobros.tutor_id = tutor_id
        cobros.buscar.clear()
        self.ir("cobros")

    def refrescar_resumen(self):
        r = self.db.resumen()
        (n1, t1), (n2, t2) = self.stats
        n1.setText(str(r["activos"]))
        t1.setText("jugadores activos")
        n2.setText(dinero(r["cobrado_mes"]))
        t2.setText(f"cobrado en {r['mes']}")

    def aviso(self, texto):
        self.aviso_lbl.setText(texto)
        self.aviso_lbl.adjustSize()
        self.aviso_lbl.move(self.width() - self.aviso_lbl.width() - 24, self.height() - self.aviso_lbl.height() - 24)
        self.aviso_lbl.raise_()
        self.aviso_lbl.show()
        self._aviso_timer.start()

    def closeEvent(self, e):
        self.db.con.close()
        super().closeEvent(e)

