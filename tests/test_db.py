import pytest

from app.db import Database, ErrorUsuario


def ids_categorias(base):
    return {c["nombre"]: c["id"] for c in base.categorias()}


def alta_familia(base):
    cat = ids_categorias(base)
    return base.crear_alta(
        {"nombre": "María López", "telefono": "844-123-4567", "emergencia_nombre": "Rosa",
         "emergencia_telefono": "8447654321"},
        [{"nombre": "Diego López", "fecha_nac": "2013-04-12", "categoria_id": cat["2013"], "numero": "10"},
         {"nombre": "Sofía López", "fecha_nac": "2015-08-03", "categoria_id": cat["Femenil"]}])


def test_categorias_iniciales(base):
    nombres = [c["nombre"] for c in base.categorias()]
    assert nombres[0] == "2009-2010" and nombres[-1] == "Femenil" and len(nombres) == 10
    assert base.categoria_por_anio(2010)["nombre"] == "2009-2010"
    assert base.categoria_por_anio(2017)["nombre"] == "2017"
    assert base.categoria_por_anio(2005) is None


@pytest.mark.parametrize("tutor, jugadores, mensaje", [
    ({"nombre": "X", "telefono": "123"}, [{"nombre": "A", "fecha_nac": "2013-01-01", "categoria_id": 1}], "10 dígitos"),
    ({"nombre": "X", "telefono": "8441234567"}, [], "al menos un jugador"),
    ({"nombre": "", "telefono": "8441234567"}, [{"nombre": "A", "fecha_nac": "2013-01-01", "categoria_id": 1}], "nombre del tutor"),
    ({"nombre": "X", "telefono": "8441234567"}, [{"nombre": "A", "fecha_nac": "", "categoria_id": 1}], "fecha de nacimiento"),
    ({"nombre": "X", "telefono": "8441234567"}, [{"nombre": "A", "fecha_nac": "2013-01-01", "categoria_id": None}], "categoría"),
])
def test_validaciones_alta(base, tutor, jugadores, mensaje):
    with pytest.raises(ErrorUsuario, match=mensaje):
        base.crear_alta(tutor, jugadores)


def test_alta_con_hermanos_y_busqueda_sin_acentos(base):
    tutor_id, n = alta_familia(base)
    assert n == 2
    assert base.tutor(tutor_id)["telefono"] == "8441234567"
    assert len(base.buscar_tutores("lopez")) == 1
    assert len(base.buscar_tutores("sofia")) == 1
    assert len(base.jugadores("diego")) == 1
    base.crear_alta({"id": tutor_id}, [{"nombre": "Leo López", "fecha_nac": "2017-02-02",
                                        "categoria_id": ids_categorias(base)["2017"]}])
    assert len(base.jugadores()) == 3


def test_cobro_folio_y_doble_cobro(base):
    tutor_id, _ = alta_familia(base)
    diego, sofia = sorted(base.estado_cuenta(tutor_id, 2026), key=lambda j: j["nombre"])
    pago = base.cobrar(tutor_id, "Efectivo", [(diego["id"], "2026-01", 600), (diego["id"], "2026-02", 600),
                                              (sofia["id"], "2026-01", 500)])
    r = base.recibo(pago)
    assert r["total"] == 1700 and len(r["detalle"]) == 3 and r["folio"].startswith("0001/")
    with pytest.raises(ErrorUsuario, match="ya tiene pagado"):
        base.cobrar(tutor_id, "Efectivo", [(diego["id"], "2026-01", 600)])
    with pytest.raises(ErrorUsuario, match="método"):
        base.cobrar(tutor_id, "Bitcoin", [(diego["id"], "2026-03", 600)])
    with pytest.raises(ErrorUsuario, match="mayor a 0"):
        base.cobrar(tutor_id, "Efectivo", [(diego["id"], "2026-03", 0)])
    edo = {j["id"]: j for j in base.estado_cuenta(tutor_id, 2026)}
    assert edo[diego["id"]]["pagados"]["2026-02"] == r["folio"]


def test_cancelacion_libera_mes_y_no_reutiliza_folio(base):
    tutor_id, _ = alta_familia(base)
    diego = base.estado_cuenta(tutor_id, 2026)[0]
    p1 = base.cobrar(tutor_id, "Transferencia", [(diego["id"], "2026-03", 600)], referencia="SPEI 1")
    with pytest.raises(ErrorUsuario, match="motivo"):
        base.cancelar_recibo(p1, "")
    base.cancelar_recibo(p1, "mes equivocado")
    assert base.recibo(p1)["cancelado"] == 1
    with pytest.raises(ErrorUsuario, match="ya está cancelado"):
        base.cancelar_recibo(p1, "otra vez")
    p2 = base.cobrar(tutor_id, "Efectivo", [(diego["id"], "2026-03", 600)])
    assert base.recibo(p2)["folio"].startswith("0002/")
    assert len(base.recibos("0001")) == 1


def test_baja_y_reactivacion(base):
    tutor_id, _ = alta_familia(base)
    sofia = next(j for j in base.estado_cuenta(tutor_id, 2026) if j["nombre"].startswith("Sofía"))
    with pytest.raises(ErrorUsuario, match="motivo"):
        base.dar_baja(sofia["id"], " ")
    base.dar_baja(sofia["id"], "Cambio de ciudad")
    assert len(base.estado_cuenta(tutor_id, 2026)) == 1
    with pytest.raises(ErrorUsuario, match="baja"):
        base.cobrar(tutor_id, "Efectivo", [(sofia["id"], "2026-02", 500)])
    assert len(base.jugadores(estatus="baja")) == 1
    base.reactivar(sofia["id"])
    assert len(base.estado_cuenta(tutor_id, 2026)) == 2


def test_persistencia_y_ajustes(tmp_path):
    archivo = str(tmp_path / "club.db")
    base = Database(archivo)
    alta_familia(base)
    base.guardar_ajustes("Nido Águila", [(ids_categorias(base)["2013"], 650)])
    base.con.close()
    otra = Database(archivo)
    assert otra.club() == "Nido Águila"
    assert len(otra.buscar_tutores("maria")) == 1
    assert next(c for c in otra.categorias() if c["nombre"] == "2013")["cuota"] == 650
    with pytest.raises(ErrorUsuario):
        otra.guardar_ajustes("", [])
    otra.con.close()


def test_datos_de_ejemplo(base):
    base.cargar_ejemplo()
    assert base.resumen()["activos"] == 7
    assert len(base.recibos()) > 20
    with pytest.raises(ErrorUsuario, match="Ya hay jugadores"):
        base.cargar_ejemplo()
