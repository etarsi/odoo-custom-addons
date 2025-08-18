import requests
import json

url = "https://api.patagoniawms.com/v1/DocumentoRecepcion"  # probá HTTPS
headers = {
    "x-api-key": "97ca7acf-9013-45cf-b287-16cfb2edc826",
    "Content-Type": "application/json",
    "Accept": "application/json",
}

payload = {
    "Numero": "R1",
    "Factura": "",
    "Fecha": "2025-08-07T16:12:00Z",
    "CodigoProveedor": "1388",
    "Proveedor": "EL MUNDO DEL JUGUETE SA",
    "Observacion": "Prueba de Odoo",
    "DocumentoRecepcionTipo": "remito",
    "RecepcionTipo": "devolucion",
    "DocumentoRecepcionDetalleRequest": [
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
