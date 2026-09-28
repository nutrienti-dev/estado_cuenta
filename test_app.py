"""Prueba la interfaz con un World Office falso (sin red)."""
import pytest
from streamlit.testing.v1 import AppTest

from lib.wo_client import WOClient
from tests.fixtures import PARTIDAS, RENGLONES, TERCERO_CLIENTE, TERCERO_PROVEEDOR

TERCEROS = {"900000001": TERCERO_CLIENTE, "900000002": TERCERO_PROVEEDOR}


@pytest.fixture(autouse=True)
def wo_falso(monkeypatch):
    monkeypatch.setattr(WOClient, "buscar_tercero", lambda self, nit: TERCEROS.get(nit))
    monkeypatch.setattr(WOClient, "rc_mas_reciente", lambda self: 1)
    monkeypatch.setattr(WOClient, "cuentas_por_cobrar", lambda self, enc, tid: PARTIDAS if tid == 77 else [])
    monkeypatch.setattr(WOClient, "renglones_factura", lambda self, doc: RENGLONES)


def correr(nit):
    at = AppTest.from_file("../app.py", default_timeout=30)
    at.secrets["worldoffice"] = {"token": "falso"}
    at.run()
    at.text_input[0].input(nit)
    at.button[0].click()
    at.run()
    return at


def texto(at):
    return " ".join(m.value for m in at.markdown) + " ".join(i.value for i in at.info)


def test_cliente_con_deuda():
    at = correr("900.000.001-5")
    assert not at.exception
    assert at.subheader[0].value == "EMPRESA DE PRUEBA SAS"
    assert "$119.995" in texto(at)            # 57996 + 64996.5 - 2997.7
    tabla = at.dataframe[0].value
    assert list(tabla["Factura"]) == ["RC 42", "FE 480", "FE 500"]


def test_no_cliente_y_nit_inexistente_dan_el_mismo_mensaje():
    a = correr("900000002")   # proveedor
    b = correr("123456789")   # no existe
    assert a.info[0].value == b.info[0].value
    assert not a.subheader and not b.subheader


def test_nit_invalido():
    at = correr("hola")
    assert at.warning


def test_productos_de_factura():
    at = correr("900000001")
    at.selectbox[0].select_index(0).run()
    assert not at.exception
    prod = at.dataframe[1].value
    assert list(prod["Producto"]) == ["Lechuga crespa", "Tomate chonto"]
