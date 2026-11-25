# Club Nido Águila — demo

Programa de escritorio para Windows (un solo `NidoAguila.exe`, sin instalar nada) con tres partes de la cotización:

1. **Alta de jugadores**: un tutor con uno o varios hijos, teléfono principal (WhatsApp) y contacto de emergencia. La categoría se sugiere por año de nacimiento (2009-2010 a 2018) y Femenil se elige a mano. Bajas con motivo y reactivación.
2. **Cobro de mensualidades**: se busca al tutor, se marcan los meses de cada hijo (en rojo los que adeuda) y se cobra todo en un solo pago. Cada pago genera un **recibo con folio consecutivo** (`0001/26`) que se imprime, se guarda en PDF o se avisa al tutor por WhatsApp. Un recibo se cancela con motivo, nunca se borra.
3. **Ejecutable para PC**: `dist/NidoAguila.exe`.

En **Ajustes** se cambian el nombre del club y la cuota de cada categoría, y se pueden cargar datos de ejemplo para la demostración.

## Tecnología

- Python 3.12 + PySide6 (Qt) para la interfaz.
- SQLite (`sqlite3` de Python). La base vive en `%LOCALAPPDATA%\NidoAguila\club.db`, nunca junto al programa.
- `app/db.py` tiene toda la lógica y validaciones; `app/ventana.py` y `app/dialogos.py` son la interfaz; `app/recibo.py` arma el recibo (vista, impresión y PDF).

## Uso

| Archivo | Para qué |
| --- | --- |
| `Iniciar Nido Aguila.bat` | Abre el programa desde el código (la primera vez instala lo necesario). |
| `Crear EXE.bat` | Genera `dist\NidoAguila.exe` con PyInstaller. |

## Desarrollo

```bash
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt pytest pyinstaller
.venv\Scripts\python -m pytest -q                 # pruebas de datos e interfaz (sin abrir ventanas)
.venv\Scripts\python herramientas\capturas.py out  # capturas de cada pantalla con datos de ejemplo
```

`NIDO_CARPETA=<carpeta>` hace que el programa use otra carpeta de datos (pruebas y capturas no tocan los datos reales).
