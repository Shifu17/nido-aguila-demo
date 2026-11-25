'use strict';

// ---------- Utilidades ----------
const $ = (s, el = document) => el.querySelector(s);
const $$ = (s, el = document) => [...el.querySelectorAll(s)];
const esc = (v) => String(v ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const dinero = (n) => `$${Number(n || 0).toLocaleString('es-MX', { minimumFractionDigits: 0, maximumFractionDigits: 2 })}`;
const MESES = ['Ene', 'Feb', 'Mar', 'Abr', 'May', 'Jun', 'Jul', 'Ago', 'Sep', 'Oct', 'Nov', 'Dic'];
const pad = (n) => String(n).padStart(2, '0');
const fechaCorta = (iso) => {
  if (!iso) return '';
  const [y, m, d] = iso.slice(0, 10).split('-');
  return `${d}/${m}/${y}`;
};
const telefono = (t) => (t && t.length === 10 ? `${t.slice(0, 3)} ${t.slice(3, 6)} ${t.slice(6)}` : t || '');
// `api` lo expone preload.js (window.api) como variable global.

const state = {
  vista: 'jugadores',
  club: 'Club',
  categorias: [],
  metodos: [],
  filtro: { q: '', categoria_id: '', estatus: 'activo' },
  cobro: { tutorId: null, anio: new Date().getFullYear(), q: '', sel: new Set(), datos: null },
};

let toastTimer;
function aviso(msg, tipo = 'ok') {
  const t = $('#toast');
  t.textContent = msg;
  t.className = `toast ${tipo === 'error' ? 'error' : ''}`;
  t.hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => { t.hidden = true; }, tipo === 'error' ? 6000 : 3500);
}

async function intentar(fn) {
  try {
    return await fn();
  } catch (e) {
    aviso(e.message, 'error');
    return undefined;
  }
}

// ---------- Modal ----------
let alCerrarModal = null;
function abrirModal(html, { ancho = false, alCerrar = null } = {}) {
  const card = $('#modal-card');
  card.className = `modal-card${ancho ? ' wide' : ''}`;
  card.innerHTML = html;
  $('#modal').hidden = false;
  alCerrarModal = alCerrar;
  $$('[data-close]', card).forEach((b) => b.addEventListener('click', cerrarModal));
  const primero = $('input:not([type=radio]), select, textarea, button.primary', card);
  if (primero) primero.focus();
  return card;
}
function cerrarModal() {
  $('#modal').hidden = true;
  $('#modal-card').innerHTML = '';
  const cb = alCerrarModal;
  alCerrarModal = null;
  if (cb) cb();
}
document.addEventListener('keydown', (e) => {
  if (e.key === 'Escape' && !$('#modal').hidden) cerrarModal();
});

// ---------- Navegación ----------
const vistas = { jugadores: vistaJugadores, cobros: vistaCobros, recibos: vistaRecibos, ajustes: vistaAjustes };
async function ir(vista) {
  state.vista = vista;
  $$('.nav button').forEach((b) => b.classList.toggle('active', b.dataset.view === vista));
  await vistas[vista]();
  $('#view').focus();
}
window.__ir = ir; // usado por el modo de capturas
$$('.nav button').forEach((b) => b.addEventListener('click', () => ir(b.dataset.view)));

async function refrescarResumen() {
  const r = await api.call('resumen');
  $('#side-stats').innerHTML = `
    <div class="stat"><b>${r.activos}</b><span>jugadores activos</span></div>
    <div class="stat"><b>${dinero(r.cobradoMes)}</b><span>cobrado en ${esc(r.mes)}</span></div>`;
}

async function cargarAjustes() {
  const a = await api.call('ajustes');
  state.club = a.club;
  state.categorias = a.categorias;
  state.metodos = a.metodos;
  $('#club-nombre').textContent = a.club;
  document.title = a.club;
}

const opcionesCategoria = (sel = '') => state.categorias
  .map((c) => `<option value="${c.id}" ${String(sel) === String(c.id) ? 'selected' : ''}>${esc(c.nombre)}</option>`).join('');

const categoriaPorFecha = (fecha) => {
  const y = Number(String(fecha).slice(0, 4));
  return state.categorias.find((c) => c.anio_desde && y >= c.anio_desde && y <= c.anio_hasta);
};

const badgeCategoria = (nombre) => `<span class="badge ${nombre === 'Femenil' ? 'fem' : ''}">${esc(nombre)}</span>`;

// =====================================================================
// JUGADORES
// =====================================================================
async function vistaJugadores() {
  const f = state.filtro;
  $('#view').innerHTML = `
    <header class="page-head">
      <div>
        <h1>Jugadores</h1>
        <p class="lead">Alta de jugadores con su tutor y teléfonos de emergencia.</p>
      </div>
      <button class="btn primary" id="btn-alta">+ Alta de jugador</button>
    </header>
    <div class="toolbar">
      <input id="f-q" type="search" placeholder="Buscar por jugador, tutor, teléfono o número" value="${esc(f.q)}" aria-label="Buscar">
      <select id="f-cat" aria-label="Categoría"><option value="">Todas las categorías</option>${opcionesCategoria(f.categoria_id)}</select>
      <select id="f-est" aria-label="Estatus">
        <option value="activo" ${f.estatus === 'activo' ? 'selected' : ''}>Activos</option>
        <option value="baja" ${f.estatus === 'baja' ? 'selected' : ''}>Bajas</option>
        <option value="todos" ${f.estatus === 'todos' ? 'selected' : ''}>Todos</option>
      </select>
    </div>
    <div id="tabla"></div>`;
  $('#btn-alta').addEventListener('click', () => modalAlta());
  let t;
  $('#f-q').addEventListener('input', (e) => { f.q = e.target.value; clearTimeout(t); t = setTimeout(cargarJugadores, 180); });
  $('#f-cat').addEventListener('change', (e) => { f.categoria_id = e.target.value; cargarJugadores(); });
  $('#f-est').addEventListener('change', (e) => { f.estatus = e.target.value; cargarJugadores(); });
  await cargarJugadores();
}

async function cargarJugadores() {
  const rows = await intentar(() => api.call('listJugadores', state.filtro));
  if (!rows) return;
  const cont = $('#tabla');
  if (!cont) return;
  if (!rows.length) {
    const sinFiltro = !state.filtro.q && !state.filtro.categoria_id && state.filtro.estatus === 'activo';
    cont.innerHTML = `<div class="table-wrap"><div class="empty">
      <b>${sinFiltro ? 'Aún no hay jugadores' : 'Sin resultados'}</b>
      ${sinFiltro ? 'Registra el primero con “Alta de jugador”. Para probar, en Ajustes puedes cargar datos de ejemplo.' : 'Prueba con otro nombre, teléfono o categoría.'}
    </div></div>`;
    return;
  }
  cont.innerHTML = `<div class="table-wrap"><table>
    <thead><tr><th>#</th><th>Jugador</th><th>Categoría</th><th>Tutor</th><th>Alta</th><th>Estatus</th><th></th></tr></thead>
    <tbody>${rows.map((j) => `
      <tr>
        <td class="num muted">${esc(j.numero || '—')}</td>
        <td><b>${esc(j.nombre)}</b><div class="small muted">Nac. ${fechaCorta(j.fecha_nac)}</div></td>
        <td>${badgeCategoria(j.categoria)}</td>
        <td>${esc(j.tutor)}<div class="small muted">${telefono(j.telefono)}</div></td>
        <td class="num">${fechaCorta(j.fecha_alta)}</td>
        <td>${j.estatus === 'activo' ? '<span class="badge ok">Activo</span>'
          : `<span class="badge off" title="${esc(j.motivo_baja)}">Baja ${fechaCorta(j.fecha_baja)}</span>`}</td>
        <td class="actions">${j.estatus === 'activo'
          ? `<button class="btn sm" data-cobrar="${j.tutor_id}">Cobrar</button><button class="btn sm danger" data-baja="${j.id}" data-nombre="${esc(j.nombre)}">Baja</button>`
          : `<button class="btn sm" data-reactivar="${j.id}">Reactivar</button>`}</td>
      </tr>`).join('')}
    </tbody></table></div>
    <p class="small muted">${rows.length} jugador${rows.length === 1 ? '' : 'es'}</p>`;
  $$('[data-cobrar]', cont).forEach((b) => b.addEventListener('click', () => {
    state.cobro.tutorId = Number(b.dataset.cobrar);
    state.cobro.sel.clear();
    ir('cobros');
  }));
  $$('[data-baja]', cont).forEach((b) => b.addEventListener('click', () => modalBaja(Number(b.dataset.baja), b.dataset.nombre)));
  $$('[data-reactivar]', cont).forEach((b) => b.addEventListener('click', async () => {
    if (await intentar(() => api.call('reactivar', { id: Number(b.dataset.reactivar) }))) {
      aviso('Jugador reactivado.');
      cargarJugadores();
      refrescarResumen();
    }
  }));
}

function modalBaja(id, nombre) {
  const card = abrirModal(`
    <h2>Dar de baja a ${esc(nombre)}</h2>
    <p class="muted">El jugador sale de la lista de activos y ya no aparece para cobro. Su historial de pagos se conserva y se puede reactivar después.</p>
    <label>Motivo de la baja*<textarea id="b-motivo" placeholder="Ej. cambio de ciudad, lesión, ya no asistirá"></textarea></label>
    <div class="modal-actions"><button class="btn" data-close>Cancelar</button><button class="btn primary" id="b-ok">Dar de baja</button></div>`);
  $('#b-ok', card).addEventListener('click', async () => {
    const ok = await intentar(() => api.call('darBaja', { id, motivo: $('#b-motivo').value }));
    if (ok) {
      cerrarModal();
      aviso(`${nombre} quedó dado de baja.`);
      cargarJugadores();
      refrescarResumen();
    }
  });
}

// ---------- Alta (tutor + uno o varios jugadores) ----------
function bloqueJugador() {
  return `<div class="jblock">
    <label>Nombre completo*<input name="j_nombre" autocomplete="off"></label>
    <label>Fecha de nacimiento*<input name="j_fecha" type="date" min="2000-01-01" max="${new Date().toISOString().slice(0, 10)}"></label>
    <label>Categoría*<select name="j_cat"><option value="">Elegir…</option>${opcionesCategoria()}</select></label>
    <label>Número<input name="j_numero" maxlength="3" inputmode="numeric" placeholder="10"></label>
    <button type="button" class="btn sm danger" data-quitar title="Quitar este jugador">Quitar</button>
  </div>`;
}

function modalAlta() {
  const card = abrirModal(`
    <form id="f-alta" novalidate>
      <h2>Alta de jugador</h2>
      <p class="muted small">Registra al tutor una sola vez y agrega a todos sus hijos; después se cobran juntos.</p>
      <fieldset>
        <legend>Tutor</legend>
        <div class="seg" role="radiogroup">
          <label><input type="radio" name="modo" value="nuevo" checked> Nuevo tutor</label>
          <label><input type="radio" name="modo" value="existente"> Tutor ya registrado</label>
        </div>
        <div id="tutor-nuevo" class="grid2">
          <label>Nombre completo*<input name="t_nombre" autocomplete="off"></label>
          <label>Teléfono principal (WhatsApp)*<input name="t_telefono" inputmode="numeric" maxlength="10" placeholder="10 dígitos"></label>
          <label>Correo<input name="t_correo" type="email" placeholder="opcional"></label>
          <div></div>
          <div class="sub-title">Contacto de emergencia</div>
          <label>Nombre<input name="e_nombre" autocomplete="off"></label>
          <div class="grid2">
            <label>Parentesco<input name="e_parentesco" placeholder="Abuela, tío…"></label>
            <label>Teléfono<input name="e_telefono" inputmode="numeric" maxlength="10" placeholder="10 dígitos"></label>
          </div>
        </div>
        <div id="tutor-existente" hidden>
          <input id="t-buscar" type="search" placeholder="Buscar tutor por nombre, teléfono o hijo" style="width:100%" aria-label="Buscar tutor">
          <div id="t-res" class="pick-list" style="max-height:220px"></div>
        </div>
      </fieldset>
      <fieldset>
        <legend>Jugadores</legend>
        <div id="lista-j">${bloqueJugador()}</div>
        <button type="button" class="btn ghost" id="add-j" style="margin-top:10px">+ Agregar hermano</button>
      </fieldset>
      <div class="modal-actions">
        <button type="button" class="btn" data-close>Cancelar</button>
        <button type="submit" class="btn primary">Guardar alta</button>
      </div>
    </form>`, { ancho: true });

  const form = $('#f-alta', card);
  let tutorElegido = null;

  const solo10 = (input) => input.addEventListener('input', () => { input.value = input.value.replace(/\D/g, '').slice(0, 10); });
  solo10(form.t_telefono);
  solo10(form.e_telefono);

  $$('input[name=modo]', form).forEach((r) => r.addEventListener('change', () => {
    const existente = form.modo.value === 'existente';
    $('#tutor-nuevo', form).hidden = existente;
    $('#tutor-existente', form).hidden = !existente;
    if (existente) { buscarTutor(''); $('#t-buscar', form).focus(); }
  }));

  async function buscarTutor(q) {
    const res = await intentar(() => api.call('buscarTutores', { q }));
    if (!res) return;
    const cont = $('#t-res', form);
    cont.innerHTML = res.length ? res.map((t) => `
      <button type="button" class="pick ${tutorElegido === t.id ? 'sel' : ''}" data-id="${t.id}">
        <b>${esc(t.nombre)}</b><span>${telefono(t.telefono)}${t.hijos ? ` · ${esc(t.hijos)}` : ''}</span>
      </button>`).join('') : '<p class="muted small">No hay tutores con ese dato.</p>';
    $$('.pick', cont).forEach((b) => b.addEventListener('click', () => {
      tutorElegido = Number(b.dataset.id);
      $$('.pick', cont).forEach((x) => x.classList.toggle('sel', x === b));
    }));
  }
  let t;
  $('#t-buscar', form).addEventListener('input', (e) => { clearTimeout(t); t = setTimeout(() => buscarTutor(e.target.value), 180); });

  const lista = $('#lista-j', form);
  function prepararBloques() {
    const bloques = $$('.jblock', lista);
    bloques.forEach((b) => {
      $('[data-quitar]', b).style.visibility = bloques.length > 1 ? 'visible' : 'hidden';
      if (b.dataset.listo) return;
      b.dataset.listo = '1';
      const sel = $('select', b);
      $('input[name=j_fecha]', b).addEventListener('change', (e) => {
        if (sel.dataset.manual) return;
        const c = categoriaPorFecha(e.target.value);
        if (c) sel.value = c.id;
      });
      sel.addEventListener('change', () => { sel.dataset.manual = '1'; });
      $('input[name=j_numero]', b).addEventListener('input', (e) => { e.target.value = e.target.value.replace(/\D/g, ''); });
      $('[data-quitar]', b).addEventListener('click', () => { b.remove(); prepararBloques(); });
    });
  }
  prepararBloques();
  $('#add-j', form).addEventListener('click', () => {
    lista.insertAdjacentHTML('beforeend', bloqueJugador());
    prepararBloques();
    $$('input[name=j_nombre]', lista).at(-1).focus();
  });

  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    const existente = form.modo.value === 'existente';
    if (existente && !tutorElegido) { aviso('Elige al tutor de la lista.', 'error'); return; }
    const tutor = existente ? { id: tutorElegido } : {
      nombre: form.t_nombre.value,
      telefono: form.t_telefono.value,
      correo: form.t_correo.value,
      emergencia_nombre: form.e_nombre.value,
      emergencia_parentesco: form.e_parentesco.value,
      emergencia_telefono: form.e_telefono.value,
    };
    const jugadores = $$('.jblock', lista).map((b) => ({
      nombre: $('[name=j_nombre]', b).value,
      fecha_nac: $('[name=j_fecha]', b).value,
      categoria_id: $('[name=j_cat]', b).value,
      numero: $('[name=j_numero]', b).value,
    }));
    const r = await intentar(() => api.call('crearAlta', { tutor, jugadores }));
    if (!r) return;
    cerrarModal();
    aviso(r.registrados === 1 ? 'Jugador registrado.' : `${r.registrados} jugadores registrados.`);
    state.filtro = { q: '', categoria_id: '', estatus: 'activo' };
    if (state.vista === 'jugadores') vistaJugadores();
    refrescarResumen();
  });
}

// =====================================================================
// COBRO DE MENSUALIDADES
// =====================================================================
async function vistaCobros() {
  const c = state.cobro;
  $('#view').innerHTML = `
    <header class="page-head">
      <div>
        <h1>Cobro de mensualidades</h1>
        <p class="lead">Busca al tutor, marca los meses de cada hijo y genera el recibo.</p>
      </div>
    </header>
    <div class="cobro-layout">
      <section class="panel sticky">
        <input id="c-q" type="search" placeholder="Tutor, jugador o teléfono" value="${esc(c.q)}" aria-label="Buscar tutor">
        <div id="c-res" class="pick-list"></div>
      </section>
      <section id="c-det"></section>
    </div>`;
  let t;
  $('#c-q').addEventListener('input', (e) => { c.q = e.target.value; clearTimeout(t); t = setTimeout(buscarCobro, 180); });
  await buscarCobro();
  await detalleCobro();
}

async function buscarCobro() {
  const c = state.cobro;
  const res = await intentar(() => api.call('buscarTutores', { q: c.q }));
  const cont = $('#c-res');
  if (!res || !cont) return;
  const conHijos = res.filter((x) => x.activos > 0);
  cont.innerHTML = conHijos.length ? conHijos.map((x) => `
    <button class="pick ${c.tutorId === x.id ? 'sel' : ''}" data-id="${x.id}">
      <b>${esc(x.nombre)}</b><span>${esc(x.hijos)}</span><span>${telefono(x.telefono)}</span>
    </button>`).join('') : '<p class="muted small">No hay tutores con jugadores activos que coincidan.</p>';
  $$('.pick', cont).forEach((b) => b.addEventListener('click', () => {
    c.tutorId = Number(b.dataset.id);
    c.sel.clear();
    $$('.pick', cont).forEach((x) => x.classList.toggle('sel', x === b));
    detalleCobro();
  }));
}

async function detalleCobro() {
  const c = state.cobro;
  const cont = $('#c-det');
  if (!cont) return;
  if (!c.tutorId) {
    cont.innerHTML = '<div class="panel"><div class="empty"><b>Elige un tutor</b>Aparecerán sus hijos con los meses pagados y pendientes.</div></div>';
    return;
  }
  const d = await intentar(() => api.call('estadoCuenta', { tutor_id: c.tutorId, anio: c.anio }));
  if (!d) return;
  c.datos = d;
  const hoy = new Date();
  const mesActual = `${hoy.getFullYear()}-${pad(hoy.getMonth() + 1)}`;
  const tutor = d.tutor;
  const emergencia = tutor.emergencia_nombre
    ? `Emergencia: ${esc(tutor.emergencia_nombre)}${tutor.emergencia_parentesco ? ` (${esc(tutor.emergencia_parentesco)})` : ''} · ${telefono(tutor.emergencia_telefono)}`
    : 'Sin contacto de emergencia';

  cont.innerHTML = `
    <div class="panel">
      <div class="det-head">
        <div>
          <h2>${esc(tutor.nombre)}</h2>
          <div class="small muted">Tel. ${telefono(tutor.telefono)} · ${emergencia}</div>
        </div>
        <div class="year">
          <button class="btn sm" data-y="-1" aria-label="Año anterior">‹</button><b>${d.anio}</b><button class="btn sm" data-y="1" aria-label="Año siguiente">›</button>
        </div>
      </div>
      ${d.jugadores.length ? d.jugadores.map((j) => `
        <div class="jrow">
          <div class="jinfo">
            <b>${esc(j.nombre)}</b>${badgeCategoria(j.categoria)}
            <label class="cuota">Cuota mensual <input type="number" min="1" step="50" value="${j.cuota}" data-cuota="${j.id}"></label>
          </div>
          <div class="months">${MESES.map((m, i) => {
            const mes = `${d.anio}-${pad(i + 1)}`;
            const folio = j.pagados[mes];
            if (folio) return `<span class="m paid" title="Pagado · folio ${folio}">${m}<small>${folio}</small></span>`;
            const clave = `${j.id}|${mes}`;
            const vencido = mes < mesActual;
            return `<button class="m ${c.sel.has(clave) ? 'sel' : ''} ${vencido ? 'due' : ''}" data-clave="${clave}" title="${vencido ? 'Adeudo' : 'Pendiente'}">${m}<small>${vencido ? 'adeudo' : ''}</small></button>`;
          }).join('')}</div>
        </div>`).join('') : '<div class="empty">Este tutor no tiene jugadores activos.</div>'}
      <div class="legend"><span><i class="lp"></i>Pagado (folio)</span><span><i class="ld"></i>Adeudo</span><span><i class="ls"></i>Seleccionado para cobrar</span></div>
    </div>
    <div class="paybar">
      <div class="total" id="sel-total">$0<small id="sel-count">Marca los meses a cobrar</small></div>
      <select id="metodo" aria-label="Método de pago">${state.metodos.map((m) => `<option>${esc(m)}</option>`).join('')}</select>
      <input id="ref" placeholder="Referencia" title="Opcional: número de transferencia o nota" aria-label="Referencia (opcional)">
      <button class="btn primary" id="btn-cobrar" disabled>Cobrar y generar recibo</button>
    </div>`;

  $$('[data-y]', cont).forEach((b) => b.addEventListener('click', () => {
    c.anio += Number(b.dataset.y);
    detalleCobro();
  }));
  $$('[data-clave]', cont).forEach((b) => b.addEventListener('click', () => {
    const k = b.dataset.clave;
    if (c.sel.has(k)) c.sel.delete(k); else c.sel.add(k);
    b.classList.toggle('sel', c.sel.has(k));
    totalCobro();
  }));
  $$('[data-cuota]', cont).forEach((i) => i.addEventListener('input', totalCobro));
  $('#btn-cobrar', cont).addEventListener('click', cobrar);
  totalCobro();
}

function itemsSeleccionados() {
  return [...state.cobro.sel].map((k) => {
    const [jugador_id, mes] = k.split('|');
    const input = $(`[data-cuota="${jugador_id}"]`);
    return { jugador_id: Number(jugador_id), mes, monto: Number(input ? input.value : 0) };
  }).filter((it) => $(`[data-cuota="${it.jugador_id}"]`));
}

function totalCobro() {
  const items = itemsSeleccionados();
  const total = items.reduce((s, x) => s + (x.monto || 0), 0);
  const t = $('#sel-total');
  if (!t) return;
  t.firstChild.textContent = dinero(total);
  $('#sel-count').textContent = items.length
    ? `${items.length} mensualidad${items.length === 1 ? '' : 'es'} seleccionada${items.length === 1 ? '' : 's'}`
    : 'Marca los meses a cobrar';
  $('#btn-cobrar').disabled = !items.length;
}

async function cobrar() {
  const c = state.cobro;
  const boton = $('#btn-cobrar');
  boton.disabled = true;
  const recibo = await intentar(() => api.call('cobrar', {
    tutor_id: c.tutorId,
    metodo: $('#metodo').value,
    referencia: $('#ref').value,
    items: itemsSeleccionados(),
  }));
  if (!recibo) { boton.disabled = false; return; }
  c.sel.clear();
  await detalleCobro();
  refrescarResumen();
  mostrarRecibo(recibo);
}

// =====================================================================
// RECIBOS
// =====================================================================
function reciboHTML(r) {
  const porJugador = new Map();
  for (const d of r.detalle) {
    if (!porJugador.has(d.jugador)) porJugador.set(d.jugador, { categoria: d.categoria, lineas: [] });
    porJugador.get(d.jugador).lineas.push(d);
  }
  const mesTxt = (mes) => `${MESES[Number(mes.slice(5)) - 1]} ${mes.slice(0, 4)}`;
  return `<div class="recibo">
    ${r.cancelado ? '<div class="r-stamp">CANCELADO</div>' : ''}
    <div class="r-club"><div class="logo">NA</div><div><div class="r-name">${esc(r.club)}</div><div class="r-sub small">Recibo de pago</div></div></div>
    <hr>
    <div class="r-row"><span>Folio</span><b>${esc(r.folio)}</b></div>
    <div class="r-row r-sub"><span>Fecha</span><span>${fechaCorta(r.fecha)} ${esc(r.fecha.slice(11, 16))}</span></div>
    <hr>
    <div class="r-sub">Tutor</div><div>${esc(r.tutor)}</div>
    <hr>
    ${[...porJugador].map(([jugador, g]) => `
      <div class="r-player">${esc(jugador)} · ${esc(g.categoria)}</div>
      ${g.lineas.map((l) => `<div class="r-row"><span>${esc(l.concepto)} ${mesTxt(l.mes)}</span><span>${dinero(l.monto)}</span></div>`).join('')}`).join('')}
    <hr>
    <div class="r-row r-total"><span>TOTAL</span><span>${dinero(r.total)}</span></div>
    <hr>
    <div class="r-row r-sub"><span>Método</span><span>${esc(r.metodo)}</span></div>
    ${r.referencia ? `<div class="r-row r-sub"><span>Referencia</span><span>${esc(r.referencia)}</span></div>` : ''}
    ${r.cancelado ? `<div class="r-row r-sub"><span>Cancelado</span><span>${fechaCorta(r.fecha_cancelacion)}</span></div><div class="r-sub small">Motivo: ${esc(r.motivo_cancelacion)}</div>` : ''}
    <div class="r-foot">Comprobante interno del club · no es factura fiscal</div>
  </div>`;
}

function mostrarRecibo(r) {
  $('#print-area').innerHTML = reciboHTML(r);
  const card = abrirModal(`
    <h2>Recibo ${esc(r.folio)}</h2>
    <p class="muted small">${r.cancelado ? 'Este recibo está cancelado.' : 'Pago registrado. Imprímelo, guárdalo en PDF o avísale al tutor por WhatsApp.'}</p>
    <div style="padding:12px 0">${reciboHTML(r)}</div>
    <div class="modal-actions">
      <button class="btn" data-close>Cerrar</button>
      <button class="btn" id="r-wa" ${r.cancelado ? 'disabled' : ''}>WhatsApp al tutor</button>
      <button class="btn" id="r-pdf">Guardar PDF</button>
      <button class="btn primary" id="r-print">Imprimir</button>
    </div>`, { alCerrar: () => { $('#print-area').innerHTML = ''; } });
  $('#r-print', card).addEventListener('click', () => window.print());
  $('#r-pdf', card).addEventListener('click', async () => {
    const ruta = await intentar(() => api.pdf(`Recibo ${r.folio.replace('/', '-')} ${r.tutor}`));
    if (ruta) aviso('PDF guardado. Adjúntalo en el chat de WhatsApp si el tutor lo pide.');
  });
  $('#r-wa', card).addEventListener('click', async () => {
    const meses = r.detalle.map((d) => `${MESES[Number(d.mes.slice(5)) - 1]} (${d.jugador.split(' ')[0]})`).join(', ');
    const texto = `Hola ${r.tutor}, le confirmamos su pago de mensualidad.\nFolio: ${r.folio}\nMeses: ${meses}\nTotal: ${dinero(r.total)} (${r.metodo})\n¡Gracias! ${r.club}`;
    const ok = await intentar(() => api.whatsapp({ telefono: r.telefono, texto }));
    if (ok === false) aviso('El tutor no tiene un teléfono válido.', 'error');
  });
}

async function vistaRecibos() {
  $('#view').innerHTML = `
    <header class="page-head">
      <div><h1>Recibos</h1><p class="lead">Todos los recibos emitidos. Uno equivocado se cancela con motivo; nunca se borra.</p></div>
    </header>
    <div class="toolbar"><input id="r-q" type="search" placeholder="Buscar por folio, tutor o jugador" aria-label="Buscar recibos"></div>
    <div id="r-tabla"></div>`;
  let t;
  $('#r-q').addEventListener('input', (e) => { clearTimeout(t); t = setTimeout(() => cargarRecibos(e.target.value), 180); });
  await cargarRecibos('');
}

async function cargarRecibos(q) {
  const rows = await intentar(() => api.call('listRecibos', { q }));
  const cont = $('#r-tabla');
  if (!rows || !cont) return;
  if (!rows.length) {
    cont.innerHTML = `<div class="table-wrap"><div class="empty"><b>${q ? 'Sin resultados' : 'Aún no hay recibos'}</b>${q ? 'Prueba con otro folio o nombre.' : 'Se generan al cobrar mensualidades.'}</div></div>`;
    return;
  }
  cont.innerHTML = `<div class="table-wrap"><table>
    <thead><tr><th>Folio</th><th>Fecha</th><th>Tutor</th><th class="right">Meses</th><th>Método</th><th class="right">Total</th><th>Estatus</th><th></th></tr></thead>
    <tbody>${rows.map((r) => `<tr>
      <td class="num"><b>${esc(r.folio)}</b></td>
      <td class="num">${fechaCorta(r.fecha)} <span class="muted small">${esc(r.fecha.slice(11, 16))}</span></td>
      <td>${esc(r.tutor)}</td>
      <td class="num right">${r.conceptos}</td>
      <td>${esc(r.metodo)}</td>
      <td class="num right"><b>${dinero(r.total)}</b></td>
      <td>${r.cancelado ? '<span class="badge off">Cancelado</span>' : '<span class="badge ok">Vigente</span>'}</td>
      <td class="actions"><button class="btn sm" data-ver="${r.id}">Ver</button>${r.cancelado ? '' : `<button class="btn sm danger" data-cancelar="${r.id}" data-folio="${esc(r.folio)}">Cancelar</button>`}</td>
    </tr>`).join('')}</tbody></table></div>`;
  $$('[data-ver]', cont).forEach((b) => b.addEventListener('click', async () => {
    const r = await intentar(() => api.call('recibo', { id: Number(b.dataset.ver) }));
    if (r) mostrarRecibo(r);
  }));
  $$('[data-cancelar]', cont).forEach((b) => b.addEventListener('click', () => {
    const id = Number(b.dataset.cancelar);
    const card = abrirModal(`
      <h2>Cancelar recibo ${esc(b.dataset.folio)}</h2>
      <p class="muted">El recibo queda marcado como cancelado y sus meses vuelven a quedar pendientes. El folio no se reutiliza.</p>
      <label>Motivo*<textarea id="c-motivo" placeholder="Ej. se cobró el mes equivocado"></textarea></label>
      <div class="modal-actions"><button class="btn" data-close>Volver</button><button class="btn primary" id="c-ok">Cancelar recibo</button></div>`);
    $('#c-ok', card).addEventListener('click', async () => {
      if (await intentar(() => api.call('cancelarRecibo', { id, motivo: $('#c-motivo').value }))) {
        cerrarModal();
        aviso('Recibo cancelado.');
        cargarRecibos($('#r-q').value);
        refrescarResumen();
      }
    });
  }));
}

// =====================================================================
// AJUSTES
// =====================================================================
async function vistaAjustes() {
  await cargarAjustes();
  const info = await api.info();
  $('#view').innerHTML = `
    <header class="page-head">
      <div><h1>Ajustes</h1><p class="lead">Nombre del club y cuota mensual de cada categoría.</p></div>
    </header>
    <div class="settings">
      <section class="card">
        <label>Nombre del club<input id="a-club" value="${esc(state.club)}"></label>
        <h2 style="margin-top:18px">Cuotas por categoría</h2>
        <table><thead><tr><th>Categoría</th><th>Años</th><th>Cuota mensual</th></tr></thead><tbody>
          ${state.categorias.map((c) => `<tr><td>${badgeCategoria(c.nombre)}</td>
            <td class="muted">${c.anio_desde ? (c.anio_desde === c.anio_hasta ? c.anio_desde : `${c.anio_desde}–${c.anio_hasta}`) : 'Se elige a mano'}</td>
            <td><input type="number" min="0" step="50" value="${c.cuota}" data-cat="${c.id}" aria-label="Cuota ${esc(c.nombre)}"></td></tr>`).join('')}
        </tbody></table>
        <div class="modal-actions"><button class="btn primary" id="a-guardar">Guardar ajustes</button></div>
      </section>
      <section class="card">
        <h2>Datos</h2>
        <p class="muted small">La base de datos vive en esta computadora:</p>
        <p class="small" style="word-break:break-all"><code>${esc(info.datos)}</code></p>
        <button class="btn" id="a-carpeta">Abrir carpeta de datos</button>
        <h2 style="margin-top:22px">Demostración</h2>
        <p class="muted small">Carga 5 familias de ejemplo con sus pagos del año para mostrar el sistema. Solo funciona si aún no hay jugadores.</p>
        <button class="btn gold" id="a-ejemplo">Cargar datos de ejemplo</button>
        <p class="small muted" style="margin-top:22px">Versión ${esc(info.version)} (demo)</p>
      </section>
    </div>`;
  $('#a-guardar').addEventListener('click', async () => {
    const cuotas = $$('[data-cat]').map((i) => ({ id: Number(i.dataset.cat), cuota: i.value }));
    if (await intentar(() => api.call('guardarAjustes', { club: $('#a-club').value, cuotas }))) {
      await cargarAjustes();
      aviso('Ajustes guardados.');
    }
  });
  $('#a-carpeta').addEventListener('click', () => api.abrirDatos());
  $('#a-ejemplo').addEventListener('click', async () => {
    if (await intentar(() => api.call('cargarEjemplo'))) {
      aviso('Datos de ejemplo cargados.');
      refrescarResumen();
      ir('jugadores');
    }
  });
}

// ---------- Inicio ----------
(async () => {
  await cargarAjustes();
  const info = await api.info();
  $('#side-foot').textContent = `Demo v${info.version}`;
  await refrescarResumen();
  await ir('jugadores');
})();
