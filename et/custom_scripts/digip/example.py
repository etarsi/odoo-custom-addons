import requests

url = "https://api.patagoniawms.com/v1/Proveedor"
headers = {
    "x-api-key": "97ca7acf-9013-45cf-b287-16cfb2edc826",
    "Content-Type": "application/json",
    "Accept": "application/json",
}

payload = {
    'Codigo': None,
    'Descripcion': 'EUROPACKAGING S.A2',
    'RequiereControlCiego': True,
    'Activo': True,
}

response = requests.get(url=url, headers=headers)

def update_provider():

    respons2 = requests.put(url=url, headers=headers, json=payload)
    
    data = response.json()
    for d in data:
        if d['Activo']:
            if d['Descripcion'] == 'EUROPACKAGING S.A':
                print(d)

if response.status_code == 200:
    data = response.json()

    for d in data:
        if d['Activo']:
            if not d['Codigo']:
                print(d['Descripcion'])