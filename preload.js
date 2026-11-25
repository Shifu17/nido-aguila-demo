'use strict';
const { contextBridge, ipcRenderer } = require('electron');

async function call(metodo, args) {
  const r = await ipcRenderer.invoke('api', metodo, args);
  if (!r.ok) throw new Error(r.error);
  return r.data;
}

contextBridge.exposeInMainWorld('api', {
  call,
  pdf: (nombre) => ipcRenderer.invoke('pdf', nombre),
  whatsapp: (datos) => ipcRenderer.invoke('whatsapp', datos),
  abrirDatos: () => ipcRenderer.invoke('abrirDatos'),
  info: () => ipcRenderer.invoke('info'),
});
