"""Nutrienti — Estado de cuenta para clientes.

El cliente escribe su NIT y ve cuanto debe HOY, factura por factura, segun
World Office. El cruce facturas/pagos lo hace World Office (endpoint de
cuentas por cobrar), la app solo lo consulta: nunca modifica nada.

Privacidad: no hay lista de clientes en ninguna parte de la app, y el
mensaje es el mismo si el NIT no existe, no es cliente o no debe nada.
"""
from __future__ import annotations

import logging
from datetime import datetime
from zoneinfo import ZoneInfo

import pandas as pd
import streamlit as st

from lib import estado as E
from lib.wo_client import WOClient, WOError

log = logging.getLogger("estado_cuenta")

MAX_CONSULTAS_POR_SESION = 10
TZ = ZoneInfo("America/Bogota")
MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio",
         "agosto", "septiembre", "octubre", "noviembre", "diciembre"]
MSG_SIN_SALDO = ("No encontramos saldo pendiente para el NIT ingresado. "
                 "Si crees que hay un error, comunícate con Nutrienti.")

st.set_page_config(page_title="Estado de cuenta · Nutrienti", page_icon="🥬",
                   layout="centered", initial_sidebar_state="collapsed")
st.markdown("""
<style>
  .block-container {padding-top: 1.5rem; max-width: 720px;}
  .total-box {background:#EAF4EC; border-radius:16px; padding:1.2rem 1.4rem; margin:.6rem 0 1rem 0;}
  .total-box .lbl {font-size:.95rem; color:#2E5E3E; margin:0;}
  .total-box .val {font-size:2.4rem; font-weight:800; color:#1B4D2E; margin:0; line-height:1.2;}
  .total-box .sub {font-size:.9rem; color:#4F6F58; margin:.3rem 0 0 0;}
  div.stFormSubmitButton button {width:100%; min-height:3rem;}
</style>
""", unsafe_allow_html=True)


# ------------------------------------------------------------------ datos
def _secreto(seccion: str, clave: str, defecto=None):
    try:
        return st.secrets[seccion][clave]
    except (KeyError, FileNotFoundError):
        return defecto


@st.cache_resource
def cliente_wo() -> WOClient:
    return WOClient(_secreto("worldoffice", "token", ""),
                    _secreto("worldoffice", "base_url", "https://api.worldoffice.cloud"))


@st.cache_data(ttl=3600, show_spinner=False)
def encabezado_rc() -> int:
    return cliente_wo().rc_mas_reciente()


@st.cache_data(ttl=300, show_spinner=False)
def consultar(nit: str) -> dict | None:
    """None si el NIT no existe o no es cliente. Si es cliente: nombre + partidas."""
    wo = cliente_wo()
    tercero = wo.buscar_tercero(nit)
    if not E.es_cliente(tercero):
        return None
    partidas = wo.cuentas_por_cobrar(encabezado_rc(), int(tercero["id"]))
    return {"nombre": str(tercero.get("nombreCompleto") or "").strip(),
            "df": E.partidas_a_df(partidas)}


@st.cache_data(ttl=3600, show_spinner=False)
def productos(doc_id: int) -> pd.DataFrame:
    return E.renglones_a_df(cliente_wo().renglones_factura(doc_id))


# ------------------------------------------------------------------ UI
ahora = datetime.now(TZ)
hoy_txt = f"{ahora.day} de {MESES[ahora.month - 1]} de {ahora.year}"

st.title("Estado de cuenta")
st.caption(f"Grupo Nutrienti S.A.S · Saldo a hoy, {hoy_txt}")

ss = st.session_state
ss.setdefault("consultas", 0)
ss.setdefault("nit", None)

with st.form("consulta", clear_on_submit=False):
    nit_txt = st.text_input("NIT de tu empresa (sin dígito de verificación)",
                            placeholder="Ej: 900123456", max_chars=20)
    enviar = st.form_submit_button("Consultar", type="primary")

if enviar:
    nit = E.normalizar_nit(nit_txt)
    if not nit:
        st.warning("Escribe un NIT válido, solo números (ej: 900123456).")
        ss.nit = None
    elif ss.consultas >= MAX_CONSULTAS_POR_SESION:
        st.error("Alcanzaste el máximo de consultas. Intenta de nuevo más tarde.")
        ss.nit = None
    else:
        ss.consultas += 1
        ss.nit = nit

if ss.nit:
    try:
        with st.spinner("Consultando en World Office…"):
            res = consultar(ss.nit)
    except WOError as e:
        log.exception("Error consultando WO")
        st.error("No pudimos consultar tu estado de cuenta en este momento. Intenta más tarde.")
        st.stop()

    df = res["df"] if res else pd.DataFrame(columns=E.COLUMNAS)
    info = E.resumen(df, ahora.date())

    if res is None or info["total"] <= 0:
        st.info(MSG_SIN_SALDO)
        st.stop()

    st.subheader(res["nombre"])
    sub = f"{info['facturas_pendientes']} factura(s) pendiente(s)"
    if info["saldo_a_favor"] > 0:
        sub += f" · incluye saldo a favor de {E.pesos(info['saldo_a_favor'])}"
    st.markdown(
        f"<div class='total-box'><p class='lbl'>Total adeudado a hoy</p>"
        f"<p class='val'>{E.pesos(info['total'])}</p><p class='sub'>{sub}</p></div>",
        unsafe_allow_html=True,
    )

    tabla = pd.DataFrame({
        "Factura": df["documento"],
        "Fecha": df["fecha"].dt.strftime("%d/%m/%Y"),
        "Punto": df["punto"],
        "Saldo pendiente": df["saldo"].map(E.pesos),
    })
    st.dataframe(tabla, hide_index=True, width="stretch")

    facturas = df[(df["saldo"] > 0) & df["doc_id"].notna()]
    if not facturas.empty:
        with st.expander("Ver productos de una factura"):
            etiquetas = {f"{r.documento} · {r.fecha:%d/%m/%Y} · {r.punto}": int(r.doc_id)
                         for r in facturas.itertuples()}
            elegida = st.selectbox("Factura", list(etiquetas), index=None,
                                   placeholder="Escoge una factura")
            if elegida:
                try:
                    prod = productos(etiquetas[elegida])
                except WOError:
                    st.error("No pudimos traer los productos de esa factura.")
                else:
                    if prod.empty:
                        st.caption("Esta factura no tiene productos registrados.")
                    else:
                        st.dataframe(pd.DataFrame({
                            "Producto": prod["producto"],
                            "Cantidad": prod["cantidad"].map(lambda x: f"{x:g}"),
                            "Unidad": prod["unidad"],
                            "Valor unitario": prod["valor_unitario"].map(E.pesos),
                            "Total": prod["total"].map(E.pesos),
                        }), hide_index=True, width="stretch")
                        st.caption("Valores de la factura original. El saldo pendiente puede ser menor "
                                   "si la factura tiene abonos.")

    contacto = _secreto("app", "contacto")
    if contacto:
        st.caption(contacto)
