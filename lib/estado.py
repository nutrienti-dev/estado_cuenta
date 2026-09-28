"""Logica pura (sin red ni Streamlit) del estado de cuenta."""
from __future__ import annotations

import re
from datetime import date

import pandas as pd

# Cuentas que se muestran al cliente: deudores/clientes (1305) y anticipos o
# saldos a favor del cliente (2805). Cualquier otra cuenta que WO devuelva
# (prestamos, cuentas de socios, etc.) NO se expone en la app.
PREFIJOS_CUENTAS_VISIBLES = ("1305", "2805")
SALDO_MINIMO = 1.0  # ignora residuos de redondeo (p.ej. $0,50)

COLUMNAS = ["documento", "tipo", "fecha", "punto", "saldo", "doc_id"]


def normalizar_nit(texto: str | None) -> str | None:
    """'901.399.110-3' -> '901399110'. Devuelve None si no parece un NIT/cedula."""
    if not texto:
        return None
    t = str(texto).strip()
    t = t.split("-")[0]  # quita digito de verificacion si viene con guion
    t = re.sub(r"[\s\.,]", "", t)
    if not t.isdigit() or not (5 <= len(t) <= 12):
        return None
    return t.lstrip("0") or None


def es_cliente(tercero: dict | None) -> bool:
    if not tercero:
        return False
    tipos = tercero.get("terceroTipos") or []
    return any(str(t.get("nombre", "")).strip().lower() == "cliente" for t in tipos)


def _num(v) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return 0.0


def partidas_a_df(partidas: list[dict]) -> pd.DataFrame:
    """Convierte la respuesta de cuentasPorCobrar en una tabla limpia."""
    filas = []
    for p in partidas or []:
        cuenta = str(((p.get("cuentaContable") or {}).get("codigo")) or "")
        if not cuenta.startswith(PREFIJOS_CUENTAS_VISIBLES):
            continue
        saldo = _num(p.get("saldo"))
        if abs(saldo) < SALDO_MINIMO:
            continue
        doc = p.get("documentoEncabezadoAbonaA") or {}
        tipo = str(((doc.get("documentoTipo") or {}).get("codigoDocumento")) or "").strip()
        prefijo = str(((doc.get("prefijo") or {}).get("nombre")) or "").strip()
        numero = doc.get("numero")
        if numero is not None:
            documento = f"{prefijo} {numero}".strip()
        else:  # respaldo: "FV  - FE 19229 GRUPO NUTRIENTI S.A.S" -> "FE 19229"
            m = re.search(r"-\s*([A-Z]+\s*\d+)", str(p.get("abona") or ""))
            documento = m.group(1) if m else "—"
        fecha = pd.to_datetime(doc.get("fecha") or p.get("fecha"), errors="coerce")
        punto = str(p.get("concepto") or "").strip()
        if saldo < 0:
            punto = "Saldo a favor"
        filas.append({
            "documento": documento, "tipo": tipo, "fecha": fecha,
            "punto": punto, "saldo": saldo, "doc_id": doc.get("id"),
        })
    df = pd.DataFrame(filas, columns=COLUMNAS)
    if not df.empty:
        df = df.sort_values(["fecha", "documento"], ascending=[True, True]).reset_index(drop=True)
    return df


def resumen(df: pd.DataFrame, hoy: date | None = None) -> dict:
    hoy = pd.Timestamp(hoy or date.today())
    facturas = df[df["saldo"] > 0] if not df.empty else df
    favor = df[df["saldo"] < 0]["saldo"].sum() if not df.empty else 0.0
    mas_antigua = facturas["fecha"].min() if not facturas.empty else None
    return {
        "total": float(df["saldo"].sum()) if not df.empty else 0.0,
        "facturas_pendientes": int(len(facturas)),
        "saldo_a_favor": float(-favor),
        "fecha_mas_antigua": mas_antigua,
        "dias_mas_antigua": int((hoy - mas_antigua).days) if mas_antigua is not None and pd.notna(mas_antigua) else None,
    }


def renglones_a_df(renglones: list[dict]) -> pd.DataFrame:
    filas = []
    for r in renglones or []:
        inv = r.get("inventario") or {}
        filas.append({
            "producto": str(inv.get("descripcion") or r.get("concepto") or "—").strip(),
            "cantidad": _num(r.get("cantidad")),
            "unidad": str(((r.get("unidadMedida") or {}).get("nombre")) or "").strip(),
            "valor_unitario": _num(r.get("valorUnitario")),
            "total": _num(r.get("valorTotalRenglon")),
        })
    return pd.DataFrame(filas, columns=["producto", "cantidad", "unidad", "valor_unitario", "total"])


def pesos(valor: float) -> str:
    """Formato colombiano: $1.234.567"""
    signo = "-" if valor < 0 else ""
    return f"{signo}${abs(round(valor)):,.0f}".replace(",", ".")
