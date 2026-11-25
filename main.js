'use strict';
const { app, BrowserWindow, ipcMain, dialog, shell, Menu } = require('electron');
const path = require('path');
const fs = require('fs');
const { Store, ErrorUsuario } = require('./src/db');

// Permite usar otra carpeta de datos (pruebas y capturas) sin tocar la del usuario.
if (process.env.CLUB_DATA_DIR) app.setPath('userData', process.env.CLUB_DATA_DIR);

const API = new Set([
  'ajustes', 'guardarAjustes', 'buscarTutores', 'crearAlta', 'listJugadores', 'darBaja', 'reactivar',
  'estadoCuenta', 'cobrar', 'recibo', 'listRecibos', 'cancelarRecibo', 'resumen', 'cargarEjemplo',
]);

let store;
let win;

function crearVentana() {
  win = new BrowserWindow({
    width: 1320,
    height: 860,
    minWidth: 1100,
    minHeight: 700,
    title: 'Club Nido Águila',
    backgroundColor: '#f4f6f9',
    icon: path.join(__dirname, 'build', 'icon.png'),
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true,
    },
  });
  win.loadFile(path.join(__dirname, 'renderer', 'index.html'));
  // Los enlaces externos (WhatsApp) se abren en el navegador, nunca dentro de la app.
  win.webContents.setWindowOpenHandler(() => ({ action: 'deny' }));
  win.webContents.on('will-navigate', (e) => e.preventDefault());
  if (process.env.CLUB_CAPTURAS) win.webContents.on('console-message', (_e, _l, msg) => console.log('[renderer]', msg));
  if (process.env.CLUB_CAPTURAS) win.webContents.once('did-finish-load', () => capturas(process.env.CLUB_CAPTURAS));
}

// Modo de capturas: ejecuta pasos de un JSON y guarda una imagen de cada uno (para documentar la demo).
async function capturas(archivo) {
  const pasos = JSON.parse(fs.readFileSync(archivo, 'utf8'));
  const espera = (ms) => new Promise((r) => setTimeout(r, ms));
  try {
    await espera(800);
    for (const paso of pasos) {
      if (paso.js) await win.webContents.executeJavaScript(paso.js);
      await espera(paso.espera ?? 600);
      if (paso.archivo) fs.writeFileSync(paso.archivo, (await win.webContents.capturePage()).toPNG());
    }
  } catch (e) {
    console.error('Captura falló:', e);
    process.exitCode = 1;
  }
  app.quit();
}

app.whenReady().then(async () => {
  Menu.setApplicationMenu(null);
  store = await Store.open(path.join(app.getPath('userData'), 'club.sqlite'));

  ipcMain.handle('api', (_e, metodo, args) => {
    if (!API.has(metodo)) return { ok: false, error: 'Operación no permitida.' };
    try {
      return { ok: true, data: store[metodo](args ?? {}) };
    } catch (e) {
      if (!(e instanceof ErrorUsuario)) console.error(e);
      return { ok: false, error: e instanceof ErrorUsuario ? e.message : `Error inesperado: ${e.message}` };
    }
  });

  ipcMain.handle('pdf', async (_e, nombre) => {
    const limpio = String(nombre || 'recibo').replace(/[^\w.-]+/g, '_');
    const { canceled, filePath } = await dialog.showSaveDialog(win, {
      title: 'Guardar recibo en PDF',
      defaultPath: path.join(app.getPath('documents'), `${limpio}.pdf`),
      filters: [{ name: 'PDF', extensions: ['pdf'] }],
    });
    if (canceled || !filePath) return null;
    const pdf = await win.webContents.printToPDF({ pageSize: 'Letter', printBackground: true });
    fs.writeFileSync(filePath, pdf);
    shell.showItemInFolder(filePath);
    return filePath;
  });

  ipcMain.handle('whatsapp', (_e, { telefono, texto }) => {
    const digitos = String(telefono || '').replace(/\D/g, '');
    if (digitos.length < 10) return false;
    const numero = digitos.length === 10 ? `52${digitos}` : digitos;
    shell.openExternal(`https://wa.me/${numero}?text=${encodeURIComponent(String(texto || ''))}`);
    return true;
  });

  ipcMain.handle('abrirDatos', () => shell.openPath(app.getPath('userData')));
  ipcMain.handle('info', () => ({ version: app.getVersion(), datos: app.getPath('userData') }));

  crearVentana();
});

app.on('window-all-closed', () => app.quit());
