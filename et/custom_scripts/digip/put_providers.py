import requests
import json


url = "https://api.patagoniawms.com/v1/Proveedor"
headers = {
    "x-api-key": "97ca7acf-9013-45cf-b287-16cfb2edc826",
    "Content-Type": "application/json",
    "Accept": "application/json",
}

payload = {
    "Codigo": "1388",
    "Descripcion": "EUROPACKAGING S.A",
    "RequiereControlCiego": True,
    "Activo": True,
}

response = requests.put(url, headers=headers, json=payload)

if response.status_code == 200:
    data = response.json()
    print(data)
    # for d in data:
    #     print(d)
else:
    print(f"Error {response.status_code}: {response.text}")