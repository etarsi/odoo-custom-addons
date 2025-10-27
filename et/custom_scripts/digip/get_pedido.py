import requests

headers = {}
params = {}

url = "https://api.v2.digipwms.com/api/v2/Pedidos"
headers = {
    "X-API-Key": "97ca7acf-9013-45cf-b287-16cfb2edc826",
    "Content-Type": "application/json"
}

params = {
    'PedidoCodigo': 'P8347',
}

response = requests.get(url, headers=headers, params=params)

if response.status_code == 200:
    data = response.json()
    for info in data:
        for key in info:
            print(f'{key}: {info[key]}')
            # print(info[key])
            if key == 'items':
                for item in info[key]:
                    for i in item:
                        print(f'---- {i}: {item[i]}')
                        # print(f'{i}')
else:
    print(f"Error {response.status_code}: {response.text}")