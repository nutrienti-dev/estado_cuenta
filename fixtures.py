"""Datos de prueba FICTICIOS con la misma forma que responde World Office."""


def partida(id_, numero, fecha, saldo, punto, cuenta="13050501", tipo="FV", prefijo="FE", doc_id=None):
    return {
        "id": id_,
        "cuentaContable": {"id": 106, "codigo": cuenta, "nombre": "x"},
        "concepto": punto, "saldo": str(saldo), "fecha": fecha,
        "abona": f"{tipo}  - {prefijo} {numero} GRUPO NUTRIENTI S.A.S",
        "documentoEncabezadoAbonaA": {
            "id": doc_id or id_ + 1000,
            "prefijo": {"nombre": prefijo},
            "documentoTipo": {"codigoDocumento": tipo},
            "numero": numero, "fecha": fecha,
        },
    }


PARTIDAS = [
    partida(1, 500, "2026-09-25", 57996, "Punto Norte"),
    partida(2, 480, "2026-09-18", 64996.5, "Punto Sur"),
    partida(3, 300, "2026-06-04", 0.5, "Punto Sur"),                        # residuo redondeo -> se oculta
    partida(4, 42, "2026-04-14", -2997.7, "saldo a favor", cuenta="280505", tipo="RC", prefijo="RC"),
    partida(5, 7, "2026-05-01", 999999, "Prestamo socio", cuenta="13300501"),  # otra cuenta -> NO se muestra
]

TERCERO_CLIENTE = {"id": 77, "nombreCompleto": "EMPRESA DE PRUEBA SAS", "identificacion": "900000001",
                   "terceroTipos": [{"id": 4, "codigo": "2", "nombre": "Cliente"}]}
TERCERO_PROVEEDOR = {"id": 88, "nombreCompleto": "PROVEEDOR SAS", "identificacion": "900000002",
                     "terceroTipos": [{"id": 5, "codigo": "3", "nombre": "Proveedor"}]}

RENGLONES = [
    {"inventario": {"descripcion": "Lechuga crespa"}, "unidadMedida": {"nombre": "Kilogramo"},
     "cantidad": 2, "valorUnitario": 10000, "valorTotalRenglon": 20000},
    {"inventario": {"descripcion": "Tomate chonto"}, "unidadMedida": {"nombre": "Kilogramo"},
     "cantidad": 1.5, "valorUnitario": 8000, "valorTotalRenglon": 12000},
]
