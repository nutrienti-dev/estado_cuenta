"""Cliente minimo (solo lectura) para la API de World Office Cloud.

Solo usa endpoints de consulta. Nunca crea, edita ni cruza documentos.
"""
from __future__ import annotations

import requests

BASE_URL = "https://api.worldoffice.cloud"
TIMEOUT = 30

_FILTRO_RC = [{
    "atributo": "documentoTipo.codigoDocumento", "valor": "RC", "valor2": None,
    "tipoFiltro": 0, "tipoDato": 0, "nombreColumna": None, "valores": None,
    "clase": None, "operador": 0, "subGrupo": "filtro",
}]


class WOError(RuntimeError):
    """Error al consultar World Office (red, token vencido, respuesta inesperada)."""


def _paginacion(pagina: int = 0, por_pagina: int = 200, filtros=None) -> dict:
    return {
        "columnaOrdenar": "id", "pagina": pagina, "registrosPorPagina": por_pagina,
        "orden": "DESC", "filtros": filtros or [], "canal": 0,
        "registroInicial": pagina * por_pagina,
    }


class WOClient:
    def __init__(self, token: str, base_url: str = BASE_URL, session: requests.Session | None = None):
        if not token:
            raise WOError("Falta el token de World Office.")
        self.base_url = base_url.rstrip("/")
        self.session = session or requests.Session()
        self.headers = {"Authorization": f"WO {token}", "Content-Type": "application/json"}

    # ------------------------------------------------------------ bajo nivel
    def _request(self, method: str, path: str, body: dict | None = None) -> dict | None:
        """Devuelve el campo `data` de la respuesta, o None si WO responde 404 (sin resultados)."""
        try:
            r = self.session.request(method, self.base_url + path, headers=self.headers,
                                     json=body, timeout=TIMEOUT)
        except requests.RequestException as e:
            raise WOError(f"No se pudo conectar con World Office: {e}") from e
        if r.status_code == 404:
            return None
        if r.status_code in (401, 403):
            raise WOError(f"World Office rechazó la consulta ({r.status_code}). ¿Token vencido?")
        if r.status_code >= 400:
            raise WOError(f"World Office respondió {r.status_code} en {path}")
        try:
            return r.json().get("data")
        except ValueError as e:
            raise WOError(f"Respuesta no válida de World Office en {path}") from e

    # ------------------------------------------------------------ consultas
    def buscar_tercero(self, nit: str) -> dict | None:
        """Tercero por numero de identificacion (NIT sin DV o cedula)."""
        data = self._request("GET", f"/api/v1/terceros/identificacion/{nit}")
        return data if isinstance(data, dict) and data.get("id") else None

    def rc_mas_reciente(self) -> int:
        """ID de un recibo de caja cualquiera: el endpoint de cuentas por cobrar
        lo exige como 'encabezado', pero sirve para consultar cualquier tercero."""
        data = self._request("POST", "/api/v1/contabilidad/listarDocContable",
                             _paginacion(por_pagina=1, filtros=_FILTRO_RC))
        try:
            return int(data["content"][0]["id"])
        except (TypeError, KeyError, IndexError, ValueError) as e:
            raise WOError("No se encontró ningún recibo de caja en World Office.") from e

    def cuentas_por_cobrar(self, encabezado_id: int, tercero_id: int, max_paginas: int = 20) -> list[dict]:
        """Partidas abiertas (facturas con saldo, anticipos...) del tercero, ya cruzadas por WO."""
        partidas: list[dict] = []
        for pagina in range(max_paginas):
            data = self._request("POST", f"/api/v1/contabilidad/cuentasPorCobrar/{encabezado_id}/{tercero_id}",
                                 _paginacion(pagina=pagina))
            bloque = (data or {}).get("documentosMovimientosContablesCruces") or {}
            content = bloque.get("content") or []
            partidas.extend(content)
            if bloque.get("last", True) or not content:
                break
        return partidas

    def renglones_factura(self, documento_id: int) -> list[dict]:
        """Productos (renglones) de una factura de venta."""
        data = self._request("POST", f"/api/v1/documentos/getRenglonesByDocumentoEncabezado/{documento_id}",
                             _paginacion())
        return (data or {}).get("content") or []
