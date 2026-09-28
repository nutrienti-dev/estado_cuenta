# Nutrienti — Estado de cuenta para clientes

App de Streamlit donde cada cliente escribe su **NIT** y ve cuánto le debe a
Grupo Nutrienti **a hoy**, factura por factura, con el punto de venta y los
productos de cada factura.

## De dónde salen los datos

Todo sale en vivo de **World Office Cloud** (solo consultas, la app nunca
modifica nada):

| Paso | Endpoint |
|---|---|
| Buscar cliente por NIT | `GET /api/v1/terceros/identificacion/{nit}` |
| Facturas abiertas con saldo (WO ya cruzó pagos, anticipos y notas) | `POST /api/v1/contabilidad/cuentasPorCobrar/{rcId}/{terceroId}` |
| Productos de una factura | `POST /api/v1/documentos/getRenglonesByDocumentoEncabezado/{facturaId}` |

`cuentasPorCobrar` exige el id de un documento contable como "encabezado";
la app usa el recibo de caja más reciente (sirve para cualquier tercero).
Verificado el 2026-09-28: la suma de las partidas coincide exactamente con
`consultarSaldoCliente` de WO.

Reglas de la app (`lib/estado.py`):
- Solo terceros de tipo **Cliente**.
- Solo cuentas `1305*` (clientes) y `2805*` (anticipos / saldo a favor);
  cualquier otra cuenta que WO devuelva no se muestra.
- Se ocultan residuos de redondeo menores a $1.
- El mismo mensaje neutro si el NIT no existe, no es cliente o no debe nada
  (no se revela quién es cliente de Nutrienti).
- Máximo 10 consultas por sesión del navegador.

## Estructura

```
app.py              interfaz Streamlit
lib/wo_client.py    llamadas a World Office (solo lectura)
lib/estado.py       lógica pura: NIT, filtrado, totales, formato de pesos
tests/              pruebas con datos ficticios (+ una contra la exploración real, solo local)
exploracion/        script con el que se descubrió el cruce en WO
.streamlit/         config.toml (tema) y secrets.toml.example
```

## Correr localmente

```
pip install -r requirements.txt
streamlit run app.py
```

Necesita `.streamlit/secrets.toml` (ver `secrets.toml.example`). Pruebas:
`pip install pytest` y luego `python -m pytest -q`.

## Publicar en Streamlit Community Cloud

1. Subir este repo a GitHub (`secrets.toml` y los `.json` están en `.gitignore`).
2. En share.streamlit.io → *New app* → escoger el repo, rama `main`, archivo `app.py`.
3. *Advanced settings → Secrets*: pegar el contenido de `.streamlit/secrets.toml`.

## Mantenimiento

- **El token de World Office vence el 2027-02-06.** Antes de esa fecha, generar
  uno nuevo en WO y reemplazarlo en los Secrets de Streamlit Cloud.
- Acceso solo con NIT: cualquiera que conozca el NIT de un cliente puede ver su
  saldo. Si se necesita más privacidad, agregar PIN por cliente.
