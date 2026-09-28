import json
from datetime import date
from pathlib import Path

import pytest

from lib import estado as E
from tests.fixtures import PARTIDAS, RENGLONES, TERCERO_CLIENTE, TERCERO_PROVEEDOR


@pytest.mark.parametrize("entrada,esperado", [
    ("901.399.110-3", "901399110"), (" 901399110 ", "901399110"), ("901 399 110", "901399110"),
    ("900,120,216", "900120216"), ("abc", None), ("", None), (None, None), ("12", None),
])
def test_normalizar_nit(entrada, esperado):
    assert E.normalizar_nit(entrada) == esperado


def test_es_cliente():
    assert E.es_cliente(TERCERO_CLIENTE)
    assert not E.es_cliente(TERCERO_PROVEEDOR)
    assert not E.es_cliente(None)


def test_partidas_filtra_y_ordena():
    df = E.partidas_a_df(PARTIDAS)
    assert list(df["documento"]) == ["RC 42", "FE 480", "FE 500"]  # sin residuo ni otra cuenta, por fecha
    assert "Prestamo socio" not in set(df["punto"])
    assert df.loc[df["documento"] == "RC 42", "punto"].item() == "Saldo a favor"


def test_resumen():
    df = E.partidas_a_df(PARTIDAS)
    r = E.resumen(df, date(2026, 9, 28))
    assert r["total"] == pytest.approx(57996 + 64996.5 - 2997.7)
    assert r["facturas_pendientes"] == 2
    assert r["saldo_a_favor"] == pytest.approx(2997.7)
    assert r["dias_mas_antigua"] == 10


def test_resumen_vacio():
    r = E.resumen(E.partidas_a_df([]), date(2026, 9, 28))
    assert r["total"] == 0 and r["facturas_pendientes"] == 0


def test_documento_desde_texto_abona_si_falta_numero():
    p = dict(PARTIDAS[0], documentoEncabezadoAbonaA=None)
    assert E.partidas_a_df([p])["documento"].item() == "FE 500"


def test_renglones():
    df = E.renglones_a_df(RENGLONES)
    assert list(df["producto"]) == ["Lechuga crespa", "Tomate chonto"]
    assert df["total"].sum() == 32000


def test_pesos():
    assert E.pesos(2143867.5) == "$2.143.868"
    assert E.pesos(-2997.7) == "-$2.998"


# --- Solo local: valida contra la respuesta real de WO si existe (no se sube a GitHub)
REAL = Path(__file__).resolve().parent.parent / "exploracion" / "salida_exploracion.json"


@pytest.mark.skipif(not REAL.exists(), reason="salida_exploracion.json no disponible")
def test_datos_reales_cuadran_con_saldo_total_wo():
    d = json.loads(REAL.read_text(encoding="utf-8"))
    for nit, bloque in d.items():
        if not isinstance(bloque, dict) or "cuentas_por_cobrar" not in bloque:
            continue
        partidas = bloque["cuentas_por_cobrar"]["body"]["data"]["documentosMovimientosContablesCruces"]["content"]
        saldo_wo = float(bloque["saldo"]["body"]["data"]["saldoTotal"])
        total = E.resumen(E.partidas_a_df(partidas))["total"]
        assert total == pytest.approx(saldo_wo, abs=5), nit  # solo difiere por residuos < $1 ocultos
