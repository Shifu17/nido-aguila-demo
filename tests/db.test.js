'use strict';
// Pruebas de la capa de datos: node tests/db.test.js
const assert = require('assert/strict');
const fs = require('fs');
const os = require('os');
const path = require('path');
const { Store } = require('../src/db');

const lanza = (fn, texto) => assert.throws(fn, (e) => e.message.includes(texto), `esperaba error con "${texto}"`);

(async () => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'club-test-'));
  const archivo = path.join(dir, 'club.sqlite');
  let s = await Store.open(archivo);

  const cats = s.ajustes().categorias;
  assert.equal(cats.length, 10);
  const cat2013 = cats.find((c) => c.nombre === '2013').id;
  const femenil = cats.find((c) => c.nombre === 'Femenil').id;

  // Validaciones del alta
  lanza(() => s.crearAlta({ tutor: { nombre: 'X', telefono: '123' }, jugadores: [{ nombre: 'A', fecha_nac: '2013-01-01', categoria_id: cat2013 }] }), '10 dígitos');
  lanza(() => s.crearAlta({ tutor: { nombre: 'X', telefono: '8441234567' }, jugadores: [] }), 'al menos un jugador');

  // Alta de tutor con dos hermanos
  const alta = s.crearAlta({
    tutor: { nombre: 'María López', telefono: '844-123-4567', emergencia_nombre: 'Rosa', emergencia_telefono: '8447654321' },
    jugadores: [
      { nombre: 'Diego López', fecha_nac: '2013-04-12', categoria_id: cat2013, numero: '10' },
      { nombre: 'Sofía López', fecha_nac: '2015-08-03', categoria_id: femenil },
    ],
  });
  assert.equal(alta.registrados, 2);
  assert.equal(s.get('SELECT telefono FROM tutores').telefono, '8441234567');

  // Búsqueda sin acentos y por hijo
  assert.equal(s.buscarTutores({ q: 'lopez' }).length, 1);
  assert.equal(s.buscarTutores({ q: 'sofia' }).length, 1);
  assert.equal(s.listJugadores({ q: 'diego' }).length, 1);

  // Hermano agregado después a tutor existente
  s.crearAlta({ tutor: { id: alta.tutor_id }, jugadores: [{ nombre: 'Leo López', fecha_nac: '2017-02-02', categoria_id: cats.find((c) => c.nombre === '2017').id }] });
  assert.equal(s.listJugadores({}).length, 3);

  // Cobro de varios hijos y meses en un solo recibo
  const [diego, sofia] = s.estadoCuenta({ tutor_id: alta.tutor_id, anio: 2026 }).jugadores
    .filter((j) => j.nombre !== 'Leo López');
  const r1 = s.cobrar({
    tutor_id: alta.tutor_id, metodo: 'Efectivo',
    items: [{ jugador_id: diego.id, mes: '2026-01', monto: 600 }, { jugador_id: diego.id, mes: '2026-02', monto: 600 },
      { jugador_id: sofia.id, mes: '2026-01', monto: 500 }],
  });
  assert.equal(r1.total, 1700);
  assert.equal(r1.detalle.length, 3);
  assert.match(r1.folio, /^0001\/\d{2}$/);

  // No se puede cobrar dos veces el mismo mes
  lanza(() => s.cobrar({ tutor_id: alta.tutor_id, metodo: 'Efectivo', items: [{ jugador_id: diego.id, mes: '2026-01', monto: 600 }] }), 'ya tiene pagado');
  lanza(() => s.cobrar({ tutor_id: alta.tutor_id, metodo: 'Bitcoin', items: [{ jugador_id: diego.id, mes: '2026-03', monto: 600 }] }), 'método');

  const edo = s.estadoCuenta({ tutor_id: alta.tutor_id, anio: 2026 });
  assert.equal(edo.jugadores.find((j) => j.id === diego.id).pagados['2026-02'], r1.folio);

  // Folio consecutivo y cancelación libera el mes
  const r2 = s.cobrar({ tutor_id: alta.tutor_id, metodo: 'Transferencia', referencia: 'SPEI 123', items: [{ jugador_id: diego.id, mes: '2026-03', monto: 600 }] });
  assert.match(r2.folio, /^0002\//);
  lanza(() => s.cancelarRecibo({ id: r2.id, motivo: '' }), 'motivo');
  s.cancelarRecibo({ id: r2.id, motivo: 'mes equivocado' });
  assert.equal(s.recibo({ id: r2.id }).cancelado, 1);
  const r3 = s.cobrar({ tutor_id: alta.tutor_id, metodo: 'Efectivo', items: [{ jugador_id: diego.id, mes: '2026-03', monto: 600 }] });
  assert.match(r3.folio, /^0003\//);
  assert.equal(s.listRecibos({ q: r1.folio.slice(0, 4) }).length, 1);

  // Baja: ya no aparece para cobro ni se le puede cobrar
  s.darBaja({ id: sofia.id, motivo: 'Cambio de ciudad' });
  assert.equal(s.estadoCuenta({ tutor_id: alta.tutor_id, anio: 2026 }).jugadores.length, 2);
  lanza(() => s.cobrar({ tutor_id: alta.tutor_id, metodo: 'Efectivo', items: [{ jugador_id: sofia.id, mes: '2026-02', monto: 500 }] }), 'baja');
  s.reactivar({ id: sofia.id });

  // Los datos persisten al reabrir el archivo (y la búsqueda sigue funcionando)
  s = await Store.open(archivo);
  assert.equal(s.listRecibos({}).length, 3);
  assert.equal(s.buscarTutores({ q: 'maria' }).length, 1);

  // Ajustes y datos de ejemplo
  lanza(() => s.cargarEjemplo(), 'Ya hay jugadores');
  const otra = await Store.open(path.join(dir, 'ejemplo.sqlite'));
  const res = otra.cargarEjemplo();
  assert.equal(res.activos, 7);
  assert.ok(otra.listRecibos({}).length > 20);
  otra.guardarAjustes({ club: 'Nido Águila', cuotas: [{ id: cat2013, cuota: 650 }] });
  assert.equal(otra.ajustes().categorias.find((c) => c.id === cat2013).cuota, 650);

  fs.rmSync(dir, { recursive: true, force: true });
  console.log('OK: todas las pruebas pasaron');
})().catch((e) => {
  console.error(e);
  process.exit(1);
});
