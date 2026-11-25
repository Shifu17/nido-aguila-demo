'use strict';
// Capa de datos: SQLite (sql.js, sin compilación nativa) guardado en un archivo local.
const fs = require('fs');
const path = require('path');
const initSqlJs = require('sql.js');

const MESES = ['Ene', 'Feb', 'Mar', 'Abr', 'May', 'Jun', 'Jul', 'Ago', 'Sep', 'Oct', 'Nov', 'Dic'];
const METODOS = ['Efectivo', 'Transferencia', 'Depósito'];
const CUOTA_INICIAL = 600;

const SCHEMA = `
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
`;

const CATEGORIAS = [
  ['2009-2010', 2009, 2010], ['2011', 2011, 2011], ['2012', 2012, 2012], ['2013', 2013, 2013],
  ['2014', 2014, 2014], ['2015', 2015, 2015], ['2016', 2016, 2016], ['2017', 2017, 2017],
  ['2018', 2018, 2018], ['Femenil', null, null],
];

const norm = (s) => (s == null ? '' : String(s))
  .normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase().trim();
const pad = (n, w = 2) => String(n).padStart(w, '0');
const ahora = (d = new Date()) =>
  `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`;
const soloDigitos = (s) => String(s ?? '').replace(/\D/g, '');
const texto = (s) => String(s ?? '').trim();
const folioDe = (p) => `${pad(p.consecutivo, 4)}/${pad(p.anio_folio % 100)}`;

class ErrorUsuario extends Error {}
const falla = (msg) => { throw new ErrorUsuario(msg); };

class Store {
  constructor(SQL, file) {
    this.file = file;
    this.db = fs.existsSync(file) ? new SQL.Database(fs.readFileSync(file)) : new SQL.Database();
    this._preparar();
    this.db.exec(SCHEMA);
    if (!this.get('SELECT COUNT(*) AS n FROM categorias').n) {
      CATEGORIAS.forEach(([nombre, desde, hasta], i) => this.db.run(
        'INSERT INTO categorias (nombre, anio_desde, anio_hasta, cuota, orden) VALUES (?, ?, ?, ?, ?)',
        [nombre, desde, hasta, CUOTA_INICIAL, i]));
      this.db.run("INSERT OR IGNORE INTO ajustes VALUES ('club', 'Club Nido Águila')");
    }
    this.guardar();
  }

  static async open(file) {
    const wasmBinary = fs.readFileSync(require.resolve('sql.js/dist/sql-wasm.wasm'));
    const SQL = await initSqlJs({ wasmBinary });
    fs.mkdirSync(path.dirname(file), { recursive: true });
    return new Store(SQL, file);
  }

  // sql.js cierra y reabre la base en export(): hay que volver a registrar pragma y funciones.
  _preparar() {
    this.db.run('PRAGMA foreign_keys = ON');
    this.db.create_function('norm', norm);
  }

  all(sql, params = []) {
    const st = this.db.prepare(sql);
    try {
      if (params.length) st.bind(params);
      const rows = [];
      while (st.step()) rows.push(st.getAsObject());
      return rows;
    } finally {
      st.free();
    }
  }

  get(sql, params = []) { return this.all(sql, params)[0]; }

  insert(sql, params = []) {
    this.db.run(sql, params);
    return this.get('SELECT last_insert_rowid() AS id').id;
  }

  tx(fn) {
    this.db.run('BEGIN');
    let r;
    try {
      r = fn();
      this.db.run('COMMIT');
    } catch (e) {
      this.db.run('ROLLBACK');
      throw e;
    }
    this.guardar();
    return r;
  }

  guardar() {
    const tmp = `${this.file}.tmp`;
    fs.writeFileSync(tmp, Buffer.from(this.db.export()));
    fs.renameSync(tmp, this.file);
    this._preparar();
  }

  // ---------- Ajustes ----------
  ajustes() {
    const club = this.get("SELECT valor FROM ajustes WHERE clave = 'club'")?.valor ?? 'Club';
    return { club, categorias: this.all('SELECT * FROM categorias ORDER BY orden'), metodos: METODOS };
  }

  guardarAjustes({ club, cuotas = [] }) {
    const nombre = texto(club) || falla('Escribe el nombre del club.');
    return this.tx(() => {
      this.db.run("INSERT OR REPLACE INTO ajustes VALUES ('club', ?)", [nombre]);
      for (const { id, cuota } of cuotas) {
        const c = Number(cuota);
        if (!Number.isFinite(c) || c < 0) falla('Las cuotas deben ser números iguales o mayores a 0.');
        this.db.run('UPDATE categorias SET cuota = ? WHERE id = ?', [c, id]);
      }
      return this.ajustes();
    });
  }

  // ---------- Tutores y jugadores ----------
  buscarTutores({ q = '' }) {
    const n = norm(q);
    const like = `%${n}%`;
    return this.all(`
      SELECT t.*,
        (SELECT group_concat(j.nombre, ', ') FROM jugadores j
          WHERE j.tutor_id = t.id AND j.estatus = 'activo') AS hijos,
        (SELECT COUNT(*) FROM jugadores j WHERE j.tutor_id = t.id AND j.estatus = 'activo') AS activos
      FROM tutores t
      WHERE ?1 = '' OR norm(t.nombre) LIKE ?2 OR t.telefono LIKE ?2
        OR EXISTS (SELECT 1 FROM jugadores j WHERE j.tutor_id = t.id
                   AND (norm(j.nombre) LIKE ?2 OR j.numero = ?1))
      ORDER BY t.nombre LIMIT 30`, [n, like]);
  }

  crearAlta({ tutor = {}, jugadores = [] }) {
    if (!jugadores.length) falla('Agrega al menos un jugador.');
    const cats = new Set(this.all('SELECT id FROM categorias').map((c) => c.id));
    const limpios = jugadores.map((j, i) => {
      const etiqueta = jugadores.length > 1 ? ` (jugador ${i + 1})` : '';
      const nombre = texto(j.nombre) || falla(`Falta el nombre${etiqueta}.`);
      const fecha = texto(j.fecha_nac);
      if (!/^\d{4}-\d{2}-\d{2}$/.test(fecha)) falla(`Falta la fecha de nacimiento${etiqueta}.`);
      const categoria = Number(j.categoria_id);
      if (!cats.has(categoria)) falla(`Elige la categoría${etiqueta}.`);
      return { nombre, fecha, numero: texto(j.numero) || null, categoria };
    });

    let tutorId = Number(tutor.id) || null;
    let datosTutor = null;
    if (tutorId) {
      if (!this.get('SELECT id FROM tutores WHERE id = ?', [tutorId])) falla('El tutor seleccionado ya no existe.');
    } else {
      const nombre = texto(tutor.nombre) || falla('Escribe el nombre del tutor.');
      const telefono = soloDigitos(tutor.telefono);
      if (telefono.length !== 10) falla('El teléfono principal debe tener 10 dígitos.');
      const telEmergencia = soloDigitos(tutor.emergencia_telefono);
      if (telEmergencia && telEmergencia.length !== 10) falla('El teléfono de emergencia debe tener 10 dígitos.');
      datosTutor = [nombre, telefono, texto(tutor.correo) || null, texto(tutor.emergencia_nombre) || null,
        texto(tutor.emergencia_parentesco) || null, telEmergencia || null, ahora()];
    }

    return this.tx(() => {
      if (!tutorId) {
        tutorId = this.insert(`INSERT INTO tutores (nombre, telefono, correo, emergencia_nombre,
          emergencia_parentesco, emergencia_telefono, creado) VALUES (?, ?, ?, ?, ?, ?, ?)`, datosTutor);
      }
      const hoy = ahora().slice(0, 10);
      for (const j of limpios) {
        this.db.run(`INSERT INTO jugadores (tutor_id, nombre, fecha_nac, numero, categoria_id, fecha_alta)
          VALUES (?, ?, ?, ?, ?, ?)`, [tutorId, j.nombre, j.fecha, j.numero, j.categoria, hoy]);
      }
      return { tutor_id: tutorId, registrados: limpios.length };
    });
  }

  listJugadores({ q = '', categoria_id = null, estatus = 'activo' }) {
    const n = norm(q);
    return this.all(`
      SELECT j.*, c.nombre AS categoria, t.nombre AS tutor, t.telefono
      FROM jugadores j
      JOIN categorias c ON c.id = j.categoria_id
      JOIN tutores t ON t.id = j.tutor_id
      WHERE (?1 = '' OR norm(j.nombre) LIKE ?2 OR norm(t.nombre) LIKE ?2 OR t.telefono LIKE ?2 OR j.numero = ?1)
        AND (?3 IS NULL OR j.categoria_id = ?3)
        AND (?4 = 'todos' OR j.estatus = ?4)
      ORDER BY c.orden, j.nombre`, [n, `%${n}%`, categoria_id ? Number(categoria_id) : null, estatus]);
  }

  darBaja({ id, motivo }) {
    const m = texto(motivo) || falla('Escribe el motivo de la baja.');
    return this.tx(() => {
      this.db.run("UPDATE jugadores SET estatus = 'baja', fecha_baja = ?, motivo_baja = ? WHERE id = ?",
        [ahora().slice(0, 10), m, id]);
      return true;
    });
  }

  reactivar({ id }) {
    return this.tx(() => {
      this.db.run("UPDATE jugadores SET estatus = 'activo', fecha_baja = NULL, motivo_baja = NULL WHERE id = ?", [id]);
      return true;
    });
  }

  // ---------- Cobros ----------
  estadoCuenta({ tutor_id, anio }) {
    const tutor = this.get('SELECT * FROM tutores WHERE id = ?', [tutor_id]) || falla('No se encontró el tutor.');
    const y = Number(anio) || new Date().getFullYear();
    const jugadores = this.all(`
      SELECT j.*, c.nombre AS categoria, c.cuota FROM jugadores j
      JOIN categorias c ON c.id = j.categoria_id
      WHERE j.tutor_id = ? AND j.estatus = 'activo' ORDER BY j.fecha_nac`, [tutor_id]);
    const pagados = this.all(`
      SELECT d.jugador_id, d.mes, p.id AS pago_id, p.consecutivo, p.anio_folio
      FROM pago_detalle d JOIN pagos p ON p.id = d.pago_id
      WHERE p.tutor_id = ? AND p.cancelado = 0 AND d.mes LIKE ?`, [tutor_id, `${y}-%`]);
    for (const j of jugadores) {
      j.pagados = {};
      for (const p of pagados.filter((x) => x.jugador_id === j.id)) j.pagados[p.mes] = folioDe(p);
    }
    return { tutor, anio: y, jugadores };
  }

  cobrar({ tutor_id, metodo, referencia, items = [] }) {
    return this._registrarPago({ tutor_id, metodo, referencia, items, fecha: ahora() });
  }

  _registrarPago({ tutor_id, metodo, referencia, items, fecha }) {
    if (!METODOS.includes(metodo)) falla('Elige el método de pago.');
    if (!items.length) falla('Marca al menos un mes para cobrar.');
    const jugadores = new Map(this.all("SELECT id, nombre FROM jugadores WHERE tutor_id = ? AND estatus = 'activo'",
      [tutor_id]).map((j) => [j.id, j]));
    const vistos = new Set();
    const limpios = items.map((it) => {
      const jugador = jugadores.get(Number(it.jugador_id)) || falla('Un jugador no pertenece a este tutor o está dado de baja.');
      if (!/^\d{4}-(0[1-9]|1[0-2])$/.test(it.mes)) falla('Mes inválido.');
      const monto = Math.round(Number(it.monto) * 100) / 100;
      if (!Number.isFinite(monto) || monto <= 0) falla(`La cuota de ${jugador.nombre} debe ser mayor a 0.`);
      const clave = `${jugador.id}|${it.mes}`;
      if (vistos.has(clave)) falla('Hay un mes repetido en el cobro.');
      vistos.add(clave);
      const ya = this.get(`SELECT p.consecutivo, p.anio_folio FROM pago_detalle d JOIN pagos p ON p.id = d.pago_id
        WHERE d.jugador_id = ? AND d.mes = ? AND p.cancelado = 0`, [jugador.id, it.mes]);
      if (ya) falla(`${jugador.nombre} ya tiene pagado ${this._mesLargo(it.mes)} (folio ${folioDe(ya)}).`);
      return { jugador_id: jugador.id, mes: it.mes, monto };
    });
    const total = limpios.reduce((s, x) => s + x.monto, 0);
    const anioFolio = Number(fecha.slice(0, 4));

    const pagoId = this.tx(() => {
      const consecutivo = (this.get('SELECT MAX(consecutivo) AS m FROM pagos WHERE anio_folio = ?', [anioFolio]).m || 0) + 1;
      const id = this.insert(`INSERT INTO pagos (anio_folio, consecutivo, fecha, tutor_id, total, metodo, referencia)
        VALUES (?, ?, ?, ?, ?, ?, ?)`, [anioFolio, consecutivo, fecha, tutor_id, total, metodo, texto(referencia) || null]);
      for (const x of limpios) {
        this.db.run('INSERT INTO pago_detalle (pago_id, jugador_id, concepto, mes, monto) VALUES (?, ?, ?, ?, ?)',
          [id, x.jugador_id, 'Mensualidad', x.mes, x.monto]);
      }
      return id;
    });
    return this.recibo({ id: pagoId });
  }

  _mesLargo(mes) {
    const [y, m] = mes.split('-');
    return `${MESES[Number(m) - 1]} ${y}`;
  }

  recibo({ id }) {
    const p = this.get(`SELECT p.*, t.nombre AS tutor, t.telefono FROM pagos p
      JOIN tutores t ON t.id = p.tutor_id WHERE p.id = ?`, [id]) || falla('No se encontró el recibo.');
    const detalle = this.all(`SELECT d.*, j.nombre AS jugador, c.nombre AS categoria FROM pago_detalle d
      JOIN jugadores j ON j.id = d.jugador_id JOIN categorias c ON c.id = j.categoria_id
      WHERE d.pago_id = ? ORDER BY j.nombre, d.mes`, [id]);
    return { ...p, folio: folioDe(p), club: this.ajustes().club, detalle };
  }

  listRecibos({ q = '' }) {
    const n = norm(q);
    return this.all(`
      SELECT p.*, t.nombre AS tutor, printf('%04d/%02d', p.consecutivo, p.anio_folio % 100) AS folio,
        (SELECT COUNT(*) FROM pago_detalle d WHERE d.pago_id = p.id) AS conceptos
      FROM pagos p JOIN tutores t ON t.id = p.tutor_id
      WHERE ?1 = '' OR norm(t.nombre) LIKE ?2 OR printf('%04d/%02d', p.consecutivo, p.anio_folio % 100) LIKE ?2
        OR EXISTS (SELECT 1 FROM pago_detalle d JOIN jugadores j ON j.id = d.jugador_id
                   WHERE d.pago_id = p.id AND norm(j.nombre) LIKE ?2)
      ORDER BY p.id DESC LIMIT 300`, [n, `%${n}%`]);
  }

  cancelarRecibo({ id, motivo }) {
    const m = texto(motivo) || falla('Escribe el motivo de la cancelación.');
    const p = this.get('SELECT cancelado FROM pagos WHERE id = ?', [id]) || falla('No se encontró el recibo.');
    if (p.cancelado) falla('Ese recibo ya está cancelado.');
    return this.tx(() => {
      this.db.run('UPDATE pagos SET cancelado = 1, motivo_cancelacion = ?, fecha_cancelacion = ? WHERE id = ?',
        [m, ahora(), id]);
      return true;
    });
  }

  resumen() {
    const mes = ahora().slice(0, 7);
    return {
      activos: this.get("SELECT COUNT(*) AS n FROM jugadores WHERE estatus = 'activo'").n,
      cobradoMes: this.get('SELECT COALESCE(SUM(total), 0) AS s FROM pagos WHERE cancelado = 0 AND fecha LIKE ?', [`${mes}%`]).s,
      mes: MESES[Number(mes.slice(5)) - 1],
    };
  }

  // ---------- Datos de ejemplo para la demostración ----------
  cargarEjemplo() {
    if (this.get('SELECT COUNT(*) AS n FROM jugadores').n) falla('Ya hay jugadores registrados; los datos de ejemplo solo se cargan en una base vacía.');
    const cat = (nombre) => this.get('SELECT id FROM categorias WHERE nombre = ?', [nombre]).id;
    const familias = [
      { t: ['María Hernández', '8441234567', 'Rosa Hernández', 'Abuela', '8447654321'], hasta: 10,
        j: [['Diego Hernández', '2013-04-12', '10', '2013'], ['Sofía Hernández', '2015-08-03', '8', 'Femenil']] },
      { t: ['Jorge Ramírez', '8449876543', 'Lucía Ramírez', 'Mamá', '8441112233'], hasta: 11,
        j: [['Emiliano Ramírez', '2009-02-20', '7', '2009-2010']] },
      { t: ['Laura Treviño', '8443344556', 'Pedro Treviño', 'Papá', '8446677889'], hasta: 8,
        j: [['Santiago Treviño', '2016-11-30', '9', '2016'], ['Mateo Treviño', '2018-01-15', '4', '2018']] },
      { t: ['Ricardo Garza', '8445566778', 'Elena Garza', 'Tía', '8449988776'], hasta: 11,
        j: [['Iker Garza', '2011-06-08', '22', '2011']] },
      { t: ['Ana Martínez', '8442233445', 'José Martínez', 'Abuelo', '8445544332'], hasta: 9,
        j: [['Valeria Martínez', '2012-09-19', '5', 'Femenil']] },
    ];
    const hoy = new Date();
    const anio = hoy.getFullYear();
    const limite = hoy.getMonth() + 1;
    for (const f of familias) {
      const [nombre, telefono, en, ep, et] = f.t;
      const { tutor_id } = this.crearAlta({
        tutor: { nombre, telefono, emergencia_nombre: en, emergencia_parentesco: ep, emergencia_telefono: et },
        jugadores: f.j.map(([n, fn, num, c]) => ({ nombre: n, fecha_nac: fn, numero: num, categoria_id: cat(c) })),
      });
      const ids = this.all('SELECT j.id, c.cuota FROM jugadores j JOIN categorias c ON c.id = j.categoria_id WHERE tutor_id = ?', [tutor_id]);
      for (let m = 1; m <= Math.min(f.hasta, limite); m++) {
        const mes = `${anio}-${pad(m)}`;
        this._registrarPago({
          tutor_id, metodo: m % 3 ? 'Transferencia' : 'Efectivo', referencia: '',
          items: ids.map((j) => ({ jugador_id: j.id, mes, monto: j.cuota })),
          fecha: `${mes}-0${(m % 5) + 1} 1${m % 8}:30`,
        });
      }
    }
    return this.resumen();
  }
}

module.exports = { Store, ErrorUsuario, MESES, METODOS, norm };
