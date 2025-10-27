import requests
import json

url = "https://api.v2.digipwms.com/api/v2/Pedidos"  # probá HTTPS
headers = {
    "x-api-key": "97ca7acf-9013-45cf-b287-16cfb2edc826",
    "Content-Type": "application/json",
    "Accept": "application/json",
}

payload = {
    "codigo": "P987654322",
    "clienteUbicacionCodigo": "509",
    "fecha": "2025-10-16T20:51:29.019Z",
    "fechaEstimadaEntrega": "2025-10-16T20:51:29.019Z",
    "estado": "Pendiente",
    "observacion": "Pedido de Prueba!",
    "importe": 0,
    "codigoDespacho": "Reparto Propio",
    "codigoDeEnvio": "S54321 - P",
    "servicioDeEnvioTipo": "Propio",
    "ordenPreparacion": 0,
    "items": [
        {
        "linea": "",
        "articuloCodigo": "50231",
        "unidades": 1,
        "minimoDiasVencimiento": 0,
        "lote": "",
        "fechaVencimiento": None
        },
        {
        "linea": "",
        "articuloCodigo": "54320",
        "unidades": 2,
        "minimoDiasVencimiento": 0,
        "lote": "",
        "fechaVencimiento": None
        },
        {
        "linea": "",
        "articuloCodigo": "52502",
        "unidades": 3,
        "minimoDiasVencimiento": 0,
        "lote": "",
        "fechaVencimiento": None
        }
    ],
    "tags": [
        "string"
    ]
}



try:
    resp = requests.post(url, headers=headers, json=payload, timeout=20)
except requests.RequestException as e:
    print(f"Error de red: {e}")
    raise

# Log básico para ver qué volvió
ct = (resp.headers.get("Content-Type") or "").lower()
print("STATUS:", resp.status_code, "| CT:", ct)

if not resp.ok:
    # Devolvé el mensaje “crudo” del server para ver el error real
    print(f"Error {resp.status_code}: {resp.text}")
else:
    # Solo parseá JSON si realmente vino JSON y no está vacío
    body = resp.content or b""
    if body.strip() and "json" in ct:
        try:
            data = resp.json()
        except json.JSONDecodeError:
            print("El servidor dijo 200 pero no devolvió JSON válido.")
            print("Snippet:", body[:500].decode(errors="replace"))
        else:
            print("OK:", data)
    else:
        # 200 sin body o body no-JSON
        print("Respuesta OK pero vacía o no-JSON.")
        print("Texto:", resp.text[:500])
