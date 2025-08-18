import requests
import json


url = "https://api.patagoniawms.com/api/v2/Proveedor"
headers = {
    "x-api-key": "97ca7acf-9013-45cf-b287-16cfb2edc826",
    "Content-Type": "application/json",
    "Accept": "application/json",
}

payload = {
    "Codigo": "1389",
}

response = requests.delete(url, headers=headers, json=payload)

if response.status_code == 200:
    data = response.json()
    print(data)
else:
    print(f"Error {response.status_code}: {response.text}")