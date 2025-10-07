import requests

headers = {}
params = {}

url = "http://api.patagoniawms.com/v1/ControlCiego"
headers = {
    "X-API-Key": "97ca7acf-9013-45cf-b287-16cfb2edc826",
    "Content-Type": "application/json"
}
params = {
    'DocumentoNumero': 'C14',
}

response = requests.get(url, headers=headers, params=params)

if response.status_code == 200:
    data = response.json()
    print(data)
else:
    print(f"Error {response.status_code}: {response.text}")