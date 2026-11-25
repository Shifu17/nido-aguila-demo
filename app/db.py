"""Capa de datos: SQLite local con toda la lógica y validaciones del club."""
import os
import re
import sqlite3
import unicodedata
from datetime import date, datetime

MESES = ["Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"]
METODOS = ["Efectivo", "Transferencia", "Depósito"]
CUOTA_INICIAL = 600

# Los datos viven en la computadora del club, nunca junto al programa.
CARPETA_LOCAL = os.environ.get("NIDO_CARPETA") or os.path.join(
    os.environ.get("LOCALAPPDATA") or os.path.expanduser("~"), "NidoAguila")

ESQUEMA = """
CREATE TABLE IF NOT EXISTS ajustes (clave TEXT PRIMARY KEY, valor TEXT);
CREATE TABLE IF NOT EXISTS categorias (
  id INTEGER PRIMARY KEY, nombre TEXT NOT NULL UNIQUE,
  anio_desde INTEGER, anio_hasta INTEGER,
  cuota REAL NOT NULL DEFAULT 0, orden INTEGER NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS tutores (
  id INTEGER PRIMARY KEY, nombre TEXT NOT NULL, telefono TEXT NOT NULL, correo TEXT,
  emergencia_nombre TEXT, emergencia_parentesco TEXT, emergencia_telefono TEXT,
  creado TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS jugadores (
  id INTEGER PRIMARY KEY, tutor_id INTEGER NOT NULL REFERENCES tutores(id),
  nombre TEXT NOT NULL, fecha_nac TEXT NOT NULL, numero TEXT,
  categoria_id INTEGER NOT NULL REFERENCES categorias(id),
  estatus TEXT NOT NULL DEFAULT 'activo', fecha_alta TEXT NOT NULL,
  fecha_baja TEXT, motivo_baja TEXT);
CREATE TABLE IF NOT EXISTS pagos (
  id INTEGER PRIMARY KEY, anio_folio INTEGER NOT NULL, consecutivo INTEGER NOT NULL,
  fecha TEXT NOT NULL, tutor_id INTEGER NOT NULL REFERENCES tutores(id),
  total REAL NOT NULL, metodo TEXT NOT NULL, referencia TEXT,
  cancelado INTEGER NOT NULL DEFAULT 0, motivo_cancelacion TEXT, fecha_cancelacion TEXT,
  UNIQUE (anio_folio, consecutivo));
CREATE TABLE IF NOT EXISTS pago_detalle (
  id INTEGER PRIMARY KEY, pago_id INTEGER NOT NULL REFERENCES pagos(id),
  jugador_id INTEGER NOT NULL REFERENCES jugadores(id),
  concepto TEXT NOT NULL, mes TEXT NOT NULL, monto REAL NOT NULL);
CREATE INDEX IF NOT EXISTS ix_detalle_jugador_mes ON pago_detalle (jugador_id, mes);
CREATE INDEX IF NOT EXISTS ix_jugadores_tutor ON jugadores (tutor_id);
"""

CATEGORIAS = [("2009-2010", 2009, 2010)] + [(str(a), a, a) for a in range(2011, 2019)] + [("Femenil", None, None)]


class ErrorUsuario(Exception):
    """Error que se le muestra tal cual a la persona (datos faltantes o inválidos)."""


def norm(s):
    s = "" if s is None else str(s)
    s = unicodedata.normalize("NFD", s)
    return "".join(c for c in s if unicodedata.category(c) != "Mn").lower().strip()


def ahora():
    return datetime.now().strftime("%Y-%m-%d %H:%M")


def solo_digitos(s):
    return re.sub(r"\D", "", str(s or ""))


def texto(s):
    return str(s or "").strip()


def folio_de(consecutivo, anio):
    return f"{consecutivo:04d}/{anio % 100:02d}"


def mes_largo(mes):
    y, m = mes.split("-")
    return f"{MESES[int(m) - 1]} {y}"


def dinero(n):
    n = float(n or 0)
    return f"${n:,.0f}" if n == int(n) else f"${n:,.2f}"


def telefono_bonito(t):
    t = t or ""
    return f"{t[:3]} {t[3:6]} {t[6:]}" if len(t) == 10 else t


class Database:
    def __init__(self, archivo=None):
        self.archivo = archivo or os.path.join(CARPETA_LOCAL, "club.db")
        os.makedirs(os.path.dirname(self.archivo), exist_ok=True)
        self.con = sqlite3.connect(self.archivo)
        self.con.row_factory = sqlite3.Row
        self.con.create_function("norm", 1, norm, deterministic=True)
        self.con.execute("PRAGMA foreign_keys = ON")
        self.con.executescript(ESQUEMA)
        if not self._uno("SELECT COUNT(*) FROM categorias"):
            with self.con:
                self.con.executemany(
                    "INSERT INTO categorias (nombre, anio_desde, anio_hasta, cuota, orden) VALUES (?, ?, ?, ?, ?)",
                    [(n, d, h, CUOTA_INICIAL, i) for i, (n, d, h) in enumerate(CATEGORIAS)])
                self.con.execute("INSERT OR IGNORE INTO ajustes VALUES ('club', 'Club Nido Águila')")

    # ---------------------------------------------------------------- utilidades
    def _todos(self, sql, params=()):
        return [dict(r) for r in self.con.execute(sql, params).fetchall()]

    def _fila(self, sql, params=()):
        r = self.con.execute(sql, params).fetchone()
        return dict(r) if r else None

    def _uno(self, sql, params=()):
        return self.con.execute(sql, params).fetchone()[0]

    # ---------------------------------------------------------------- ajustes
    def club(self):
        r = self._fila("SELECT valor FROM ajustes WHERE clave = 'club'")
        return r["valor"] if r else "Club"

    def categorias(self):
        return self._todos("SELECT * FROM categorias ORDER BY orden")

    def categoria_por_anio(self, anio):
        return self._fila("SELECT * FROM categorias WHERE anio_desde <= ? AND anio_hasta >= ?", (anio, anio))

    def guardar_ajustes(self, club, cuotas):
        nombre = texto(club)
        if not nombre:
            raise ErrorUsuario("Escribe el nombre del club.")
        for _, c in cuotas:
            if c is None or c < 0:
                raise ErrorUsuario("Las cuotas deben ser números iguales o mayores a 0.")
        with self.con:
            self.con.execute("INSERT OR REPLACE INTO ajustes VALUES ('club', ?)", (nombre,))
            self.con.executemany("UPDATE categorias SET cuota = ? WHERE id = ?", [(c, i) for i, c in cuotas])

    # ---------------------------------------------------------------- tutores y jugadores
    def buscar_tutores(self, q="", solo_con_activos=False):
        n = norm(q)
        filas = self._todos("""
            SELECT t.*,
              (SELECT group_concat(j.nombre, ', ') FROM jugadores j
                WHERE j.tutor_id = t.id AND j.estatus = 'activo') AS hijos,
              (SELECT COUNT(*) FROM jugadores j WHERE j.tutor_id = t.id AND j.estatus = 'activo') AS activos
            FROM tutores t
            WHERE ?1 = '' OR norm(t.nombre) LIKE ?2 OR t.telefono LIKE ?2
              OR EXISTS (SELECT 1 FROM jugadores j WHERE j.tutor_id = t.id
                         AND (norm(j.nombre) LIKE ?2 OR j.numero = ?1))
            ORDER BY t.nombre LIMIT 50""", (n, f"%{n}%"))
        return [f for f in filas if f["activos"]] if solo_con_activos else filas

    def tutor(self, tutor_id):
        return self._fila("SELECT * FROM tutores WHERE id = ?", (tutor_id,))

    def crear_alta(self, tutor, jugadores):
        """tutor: {'id'} de uno existente o los datos de uno nuevo. jugadores: lista de dicts."""
        tutor_id = tutor.get("id")
        if tutor_id:
            if not self.tutor(tutor_id):
                raise ErrorUsuario("El tutor seleccionado ya no existe.")
            datos = None
        else:
            nombre = texto(tutor.get("nombre"))
            if not nombre:
                raise ErrorUsuario("Escribe el nombre del tutor.")
            tel = solo_digitos(tutor.get("telefono"))
            if len(tel) != 10:
                raise ErrorUsuario("El teléfono principal debe tener 10 dígitos.")
            tel_e = solo_digitos(tutor.get("emergencia_telefono"))
            if tel_e and len(tel_e) != 10:
                raise ErrorUsuario("El teléfono de emergencia debe tener 10 dígitos.")
            datos = (nombre, tel, texto(tutor.get("correo")) or None, texto(tutor.get("emergencia_nombre")) or None,
                     texto(tutor.get("emergencia_parentesco")) or None, tel_e or None, ahora())

        if not jugadores:
            raise ErrorUsuario("Agrega al menos un jugador.")
        cats = {c["id"] for c in self.categorias()}
        limpios = []
        for i, j in enumerate(jugadores, 1):
            etiqueta = f" (jugador {i})" if len(jugadores) > 1 else ""
            nombre = texto(j.get("nombre"))
            if not nombre:
                raise ErrorUsuario(f"Falta el nombre{etiqueta}.")
            fecha = texto(j.get("fecha_nac"))
            if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", fecha):
                raise ErrorUsuario(f"Falta la fecha de nacimiento{etiqueta}.")
            if j.get("categoria_id") not in cats:
                raise ErrorUsuario(f"Elige la categoría{etiqueta}.")
            limpios.append((nombre, fecha, texto(j.get("numero")) or None, j["categoria_id"]))

        with self.con:
            if not tutor_id:
                tutor_id = self.con.execute(
                    """INSERT INTO tutores (nombre, telefono, correo, emergencia_nombre, emergencia_parentesco,
                       emergencia_telefono, creado) VALUES (?, ?, ?, ?, ?, ?, ?)""", datos).lastrowid
            hoy = date.today().isoformat()
            self.con.executemany(
                """INSERT INTO jugadores (tutor_id, nombre, fecha_nac, numero, categoria_id, fecha_alta)
                   VALUES (?, ?, ?, ?, ?, ?)""", [(tutor_id, *x, hoy) for x in limpios])
        return tutor_id, len(limpios)

    def jugadores(self, q="", categoria_id=None, estatus="activo"):
        n = norm(q)
        return self._todos("""
            SELECT j.*, c.nombre AS categoria, t.nombre AS tutor, t.telefono
            FROM jugadores j
            JOIN categorias c ON c.id = j.categoria_id
            JOIN tutores t ON t.id = j.tutor_id
            WHERE (?1 = '' OR norm(j.nombre) LIKE ?2 OR norm(t.nombre) LIKE ?2 OR t.telefono LIKE ?2 OR j.numero = ?1)
              AND (?3 IS NULL OR j.categoria_id = ?3)
              AND (?4 = 'todos' OR j.estatus = ?4)
            ORDER BY c.orden, j.nombre""", (n, f"%{n}%", categoria_id, estatus))

    def dar_baja(self, jugador_id, motivo):
        if not texto(motivo):
            raise ErrorUsuario("Escribe el motivo de la baja.")
        with self.con:
            self.con.execute("UPDATE jugadores SET estatus = 'baja', fecha_baja = ?, motivo_baja = ? WHERE id = ?",
                             (date.today().isoformat(), texto(motivo), jugador_id))

    def reactivar(self, jugador_id):
        with self.con:
            self.con.execute(
                "UPDATE jugadores SET estatus = 'activo', fecha_baja = NULL, motivo_baja = NULL WHERE id = ?",
                (jugador_id,))

    # ---------------------------------------------------------------- cobros
    def estado_cuenta(self, tutor_id, anio):
        jugadores = self._todos("""
            SELECT j.*, c.nombre AS categoria, c.cuota FROM jugadores j
            JOIN categorias c ON c.id = j.categoria_id
            WHERE j.tutor_id = ? AND j.estatus = 'activo' ORDER BY j.fecha_nac""", (tutor_id,))
        pagados = self._todos("""
            SELECT d.jugador_id, d.mes, p.consecutivo, p.anio_folio
            FROM pago_detalle d JOIN pagos p ON p.id = d.pago_id
            WHERE p.tutor_id = ? AND p.cancelado = 0 AND d.mes LIKE ?""", (tutor_id, f"{anio}-%"))
        for j in jugadores:
            j["pagados"] = {p["mes"]: folio_de(p["consecutivo"], p["anio_folio"])
                            for p in pagados if p["jugador_id"] == j["id"]}
        return jugadores

    def cobrar(self, tutor_id, metodo, items, referencia="", fecha=None):
        """items: lista de (jugador_id, 'AAAA-MM', monto). Devuelve el id del pago."""
        if metodo not in METODOS:
            raise ErrorUsuario("Elige el método de pago.")
        if not items:
            raise ErrorUsuario("Marca al menos un mes para cobrar.")
        activos = {j["id"]: j["nombre"] for j in self._todos(
            "SELECT id, nombre FROM jugadores WHERE tutor_id = ? AND estatus = 'activo'", (tutor_id,))}
        vistos, limpios = set(), []
        for jugador_id, mes, monto in items:
            if jugador_id not in activos:
                raise ErrorUsuario("Un jugador no pertenece a este tutor o está dado de baja.")
            if not re.fullmatch(r"\d{4}-(0[1-9]|1[0-2])", mes):
                raise ErrorUsuario("Mes inválido.")
            monto = round(float(monto or 0), 2)
            if monto <= 0:
                raise ErrorUsuario(f"La cuota de {activos[jugador_id]} debe ser mayor a 0.")
            if (jugador_id, mes) in vistos:
                raise ErrorUsuario("Hay un mes repetido en el cobro.")
            vistos.add((jugador_id, mes))
            ya = self._fila("""SELECT p.consecutivo, p.anio_folio FROM pago_detalle d JOIN pagos p ON p.id = d.pago_id
                               WHERE d.jugador_id = ? AND d.mes = ? AND p.cancelado = 0""", (jugador_id, mes))
            if ya:
                raise ErrorUsuario(f"{activos[jugador_id]} ya tiene pagado {mes_largo(mes)} "
                                   f"(folio {folio_de(ya['consecutivo'], ya['anio_folio'])}).")
            limpios.append((jugador_id, mes, monto))

        fecha = fecha or ahora()
        anio = int(fecha[:4])
        with self.con:
            consecutivo = self._uno("SELECT COALESCE(MAX(consecutivo), 0) + 1 FROM pagos WHERE anio_folio = ?", (anio,))
            pago_id = self.con.execute(
                """INSERT INTO pagos (anio_folio, consecutivo, fecha, tutor_id, total, metodo, referencia)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (anio, consecutivo, fecha, tutor_id, sum(x[2] for x in limpios), metodo, texto(referencia) or None),
            ).lastrowid
            self.con.executemany(
                "INSERT INTO pago_detalle (pago_id, jugador_id, concepto, mes, monto) VALUES (?, ?, 'Mensualidad', ?, ?)",
                [(pago_id, *x) for x in limpios])
        return pago_id

    def recibo(self, pago_id):
        p = self._fila("""SELECT p.*, t.nombre AS tutor, t.telefono FROM pagos p
                          JOIN tutores t ON t.id = p.tutor_id WHERE p.id = ?""", (pago_id,))
        if not p:
            raise ErrorUsuario("No se encontró el recibo.")
        p["folio"] = folio_de(p["consecutivo"], p["anio_folio"])
        p["club"] = self.club()
        p["detalle"] = self._todos("""
            SELECT d.*, j.nombre AS jugador, c.nombre AS categoria FROM pago_detalle d
            JOIN jugadores j ON j.id = d.jugador_id JOIN categorias c ON c.id = j.categoria_id
            WHERE d.pago_id = ? ORDER BY j.nombre, d.mes""", (pago_id,))
        return p

    def recibos(self, q=""):
        n = norm(q)
        return self._todos("""
            SELECT p.*, t.nombre AS tutor, printf('%04d/%02d', p.consecutivo, p.anio_folio % 100) AS folio,
              (SELECT COUNT(*) FROM pago_detalle d WHERE d.pago_id = p.id) AS conceptos
            FROM pagos p JOIN tutores t ON t.id = p.tutor_id
            WHERE ?1 = '' OR norm(t.nombre) LIKE ?2 OR printf('%04d/%02d', p.consecutivo, p.anio_folio % 100) LIKE ?2
              OR EXISTS (SELECT 1 FROM pago_detalle d JOIN jugadores j ON j.id = d.jugador_id
                         WHERE d.pago_id = p.id AND norm(j.nombre) LIKE ?2)
            ORDER BY p.id DESC LIMIT 500""", (n, f"%{n}%"))

    def cancelar_recibo(self, pago_id, motivo):
        if not texto(motivo):
            raise ErrorUsuario("Escribe el motivo de la cancelación.")
        p = self._fila("SELECT cancelado FROM pagos WHERE id = ?", (pago_id,))
        if not p:
            raise ErrorUsuario("No se encontró el recibo.")
        if p["cancelado"]:
            raise ErrorUsuario("Ese recibo ya está cancelado.")
        with self.con:
            self.con.execute("UPDATE pagos SET cancelado = 1, motivo_cancelacion = ?, fecha_cancelacion = ? WHERE id = ?",
                             (texto(motivo), ahora(), pago_id))

    def resumen(self):
        mes = ahora()[:7]
        return {
            "activos": self._uno("SELECT COUNT(*) FROM jugadores WHERE estatus = 'activo'"),
            "cobrado_mes": self._uno("SELECT COALESCE(SUM(total), 0) FROM pagos WHERE cancelado = 0 AND fecha LIKE ?",
                                     (f"{mes}%",)),
            "mes": MESES[int(mes[5:]) - 1],
        }

    # ---------------------------------------------------------------- datos de ejemplo
    def cargar_ejemplo(self):
        if self._uno("SELECT COUNT(*) FROM jugadores"):
            raise ErrorUsuario("Ya hay jugadores registrados; los datos de ejemplo solo se cargan en una base vacía.")
        cat = {c["nombre"]: c["id"] for c in self.categorias()}
        familias = [
            (("María Hernández", "8441234567", "Rosa Hernández", "Abuela", "8447654321"), 10,
             [("Diego Hernández", "2013-04-12", "10", "2013"), ("Sofía Hernández", "2015-08-03", "8", "Femenil")]),
            (("Jorge Ramírez", "8449876543", "Lucía Ramírez", "Mamá", "8441112233"), 11,
             [("Emiliano Ramírez", "2009-02-20", "7", "2009-2010")]),
            (("Laura Treviño", "8443344556", "Pedro Treviño", "Papá", "8446677889"), 8,
             [("Santiago Treviño", "2016-11-30", "9", "2016"), ("Mateo Treviño", "2018-01-15", "4", "2018")]),
            (("Ricardo Garza", "8445566778", "Elena Garza", "Tía", "8449988776"), 11,
             [("Iker Garza", "2011-06-08", "22", "2011")]),
            (("Ana Martínez", "8442233445", "José Martínez", "Abuelo", "8445544332"), 9,
             [("Valeria Martínez", "2012-09-19", "5", "Femenil")]),
        ]
        hoy = date.today()
        for (nombre, tel, en, ep, et), hasta, hijos in familias:
            tutor_id, _ = self.crear_alta(
                {"nombre": nombre, "telefono": tel, "emergencia_nombre": en,
                 "emergencia_parentesco": ep, "emergencia_telefono": et},
                [{"nombre": n, "fecha_nac": f, "numero": num, "categoria_id": cat[c]} for n, f, num, c in hijos])
            ids = self._todos("""SELECT j.id, c.cuota FROM jugadores j JOIN categorias c ON c.id = j.categoria_id
                                 WHERE tutor_id = ?""", (tutor_id,))
            for m in range(1, min(hasta, hoy.month) + 1):
                mes = f"{hoy.year}-{m:02d}"
                self.cobrar(tutor_id, "Transferencia" if m % 3 else "Efectivo",
                            [(j["id"], mes, j["cuota"]) for j in ids], fecha=f"{mes}-0{m % 5 + 1} 1{m % 8}:30")
