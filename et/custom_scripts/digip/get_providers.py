import requests

headers = {}
params = {}

url = "http://api.patagoniawms.com/api/v2/Proveedor"
headers = {
    "X-API-Key": "97ca7acf-9013-45cf-b287-16cfb2edc826",
    "Content-Type": "application/json"
}

response = requests.get(url, headers=headers)

if response.status_code == 200:
    data = response.json()
    # print(data)
    for d in data:
        print(d)
else:
    print(f"Error {response.status_code}: {response.text}")