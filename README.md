# Club Nido Águila — demo

Programa de escritorio para Windows con tres partes de la cotización:

1. **Alta de jugadores**: un tutor con uno o varios hijos, teléfono principal (WhatsApp) y contacto de emergencia. La categoría se sugiere por año de nacimiento (2009-2010 a 2018) y Femenil se elige a mano. Bajas con motivo y reactivación.
2. **Cobro de mensualidades**: se busca al tutor, se marcan los meses de cada hijo (en rojo los que adeuda) y se cobra todo en un solo pago. Cada pago genera un **recibo con folio consecutivo** (`0001/26`) que se imprime, se guarda en PDF o se avisa al tutor por WhatsApp. Un recibo se cancela con motivo, nunca se borra.
3. **Instalador** para Windows (`dist/ClubNidoAguila-Setup-<versión>.exe`).

En **Ajustes** se cambian el nombre del club y la cuota de cada categoría, y se pueden cargar datos de ejemplo para la demostración.

## Tecnología

- Electron 33 + HTML/CSS/JS sin framework (`renderer/`).
- SQLite con `sql.js` (sin compilación nativa). La base vive en `%APPDATA%\Club Nido Aguila\club.sqlite`.
- `src/db.js` tiene toda la lógica y validaciones; la ventana solo llama a métodos permitidos por IPC (`preload.js`).

## Comandos

```bash
npm install
npm start        # abrir en modo desarrollo
npm test         # pruebas de la base de datos
npm run dist     # generar el instalador en dist/
```

### Si `npm run dist` falla con "Cannot create symbolic link"

Es un problema conocido de electron-builder en Windows sin modo desarrollador. Se arregla una vez extrayendo el paquete de firma sin la carpeta de macOS:

```bash
7za x winCodeSign-2.6.0.7z -o%LOCALAPPDATA%\electron-builder\Cache\winCodeSign\winCodeSign-2.6.0 -xr!darwin
```

(`7za.exe` está en `node_modules/7zip-bin/win/x64/`; el `.7z` se descarga de las releases de `electron-userland/electron-builder-binaries`.)

## Capturas automáticas

`CLUB_DATA_DIR=<carpeta temporal> CLUB_CAPTURAS=<pasos.json> npx electron .` ejecuta los pasos del JSON (`{"js": "...", "espera": ms, "archivo": "captura.png"}`) y guarda una imagen de cada uno sin tocar los datos reales.
