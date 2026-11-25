"""Recibo de pago en HTML (lo usan la vista previa, la impresión y el PDF)."""
from html import escape

from app.db import MESES, dinero
from app.estilos import BORDE, DORADO, MARINO, ROJO, SUAVE


def _fecha(iso):
    y, m, d = iso[:10].split("-")
    return f"{d}/{m}/{y} {iso[11:16]}"


def html_recibo(r):
    """r: diccionario de Database.recibo()."""
    grupos = {}
    for d in r["detalle"]:
        grupos.setdefault((d["jugador"], d["categoria"]), []).append(d)

    filas = []
    for (jugador, categoria), lineas in grupos.items():
        filas.append(f'<tr><td colspan="2" style="padding-top:6px"><b>{escape(jugador)}</b>'
                     f' <span style="color:{SUAVE}">· {escape(categoria)}</span></td></tr>')
        for l in lineas:
            mes = f"{MESES[int(l['mes'][5:]) - 1]} {l['mes'][:4]}"
            filas.append(f"<tr><td>{escape(l['concepto'])} {mes}</td><td align=\"right\">{dinero(l['monto'])}</td></tr>")

    hr = f'<tr><td colspan="2"><hr style="border:0;border-top:1px dashed {BORDE}"></td></tr>'
    cancelado = ""
    if r["cancelado"]:
        cancelado = (f'<tr><td colspan="2" align="center" style="color:{ROJO};font-size:15pt;font-weight:800;'
                     f'padding:6px">CANCELADO</td></tr>'
                     f'<tr><td colspan="2" style="color:{SUAVE}">{escape(_fecha(r["fecha_cancelacion"]))} · '
                     f'Motivo: {escape(r["motivo_cancelacion"] or "")}</td></tr>{hr}')
    referencia = (f'<tr><td style="color:{SUAVE}">Referencia</td><td align="right" style="color:{SUAVE}">'
                  f'{escape(r["referencia"])}</td></tr>') if r["referencia"] else ""

    return f"""
<html><body style="font-family:'Segoe UI'; font-size:10pt; color:#14202e">
<table width="100%" cellspacing="0" cellpadding="0"><tr><td align="center">
<table width="380" cellspacing="0" cellpadding="3" style="border:1px solid {BORDE}">
  <tr><td colspan="2" style="background:{MARINO}; padding:12px 14px">
    <span style="color:{DORADO}; font-size:13pt; font-weight:800">{escape(r['club'].upper())}</span><br>
    <span style="color:#c9d6e3; font-size:9pt">Recibo de pago</span></td></tr>
  <tr><td colspan="2" style="padding:4px 12px">
  <table width="100%" cellspacing="0" cellpadding="2" style="font-family:Consolas; font-size:9.5pt">
    {cancelado}
    <tr><td>Folio</td><td align="right"><b>{escape(r['folio'])}</b></td></tr>
    <tr><td style="color:{SUAVE}">Fecha</td><td align="right" style="color:{SUAVE}">{escape(_fecha(r['fecha']))}</td></tr>
    {hr}
    <tr><td colspan="2" style="color:{SUAVE}">Tutor</td></tr>
    <tr><td colspan="2">{escape(r['tutor'])}</td></tr>
    {hr}
    {''.join(filas)}
    {hr}
    <tr><td style="font-size:12pt"><b>TOTAL</b></td><td align="right" style="font-size:12pt; color:{MARINO}"><b>{dinero(r['total'])}</b></td></tr>
    {hr}
    <tr><td style="color:{SUAVE}">Método</td><td align="right" style="color:{SUAVE}">{escape(r['metodo'])}</td></tr>
    {referencia}
    <tr><td colspan="2" align="center" style="color:{SUAVE}; font-size:8pt; padding-top:8px">
      Comprobante interno del club · no es factura fiscal</td></tr>
  </table></td></tr>
</table>
</td></tr></table>
</body></html>"""


def texto_whatsapp(r):
    meses = ", ".join(f"{MESES[int(d['mes'][5:]) - 1]} ({d['jugador'].split()[0]})" for d in r["detalle"])
    return (f"Hola {r['tutor']}, le confirmamos su pago de mensualidad.\n"
            f"Folio: {r['folio']}\nMeses: {meses}\nTotal: {dinero(r['total'])} ({r['metodo']})\n"
            f"¡Gracias! {r['club']}")
