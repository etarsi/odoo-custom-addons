import xmlrpc.client
import re

url = 'http://localhost:8069'
url2 = 'http://192.168.249.4:5432'
db = 'one'
username = 'ezequiel.tarsitano@sebigus.com.ar' 
password = '1234'


common = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/common")
uid = common.authenticate(db, username, password, {})

if not uid:
    raise Exception("Error de autenticación en Odoo")

models = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/object")

results = []

products_ids = models.execute_kw(db, uid, password, 'product.template', 'search', [[('detailed_type', '=', 'product')]])
products_data = models.execute_kw(db, uid, password, 'product.template', 'read', [products_ids], {'fields': ['name']})

output_file = "/opt/odoo15/odoo-custom-addons/et/custom_scripts/products_ids.txt"

cleaned_names = []
for p in products_data:
    raw_name = p['name']
    cleaned_name = " ".join(raw_name.splitlines()).strip()
    cleaned_name = re.sub(r'\s+', ' ', cleaned_name)
    cleaned_names.append(cleaned_name)

# Imprimir los nombres limpios
for name in cleaned_names:
    print(name)
    