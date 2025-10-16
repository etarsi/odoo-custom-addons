import requests

headers = {}
params = {}

url = "https://api.v2.digipwms.com/api/v2/Pedidos"
headers = {
    "X-API-Key": "97ca7acf-9013-45cf-b287-16cfb2edc826",
    "Content-Type": "application/json"
}

params = {
    'PedidoCodigo': 'P8346',
}

response = requests.get(url, headers=headers, params=params)

if response.status_code == 200:
    data = response.json()
    print(data)
else:
    print(f"Error {response.status_code}: {response.text}")