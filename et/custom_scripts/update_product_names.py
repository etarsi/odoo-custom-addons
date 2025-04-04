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

context = {'lang': 'es_AR'}

products_ids = models.execute_kw(db, uid, password, 'product.template', 'search', [[('detailed_type', '=', 'product')]], {'context': context})
products_data = models.execute_kw(db, uid, password, 'product.template', 'read', [products_ids], {'fields': ['name'], 'context': context})

# output_file = "/opt/odoo15/odoo-custom-addons/et/custom_scripts/products_ids.txt"

for p in products_data:
    product_id = p['id']
    raw_name = p['name']
    
    cleaned_name = " ".join(raw_name.splitlines()).strip()
    cleaned_name = re.sub(r'\s+', ' ', cleaned_name)

    print(f"raw_name: {p['name']}")
    if raw_name != cleaned_name:
        models.execute_kw(db, uid, password, 'product.template', 'write', [[product_id], {'name': cleaned_name}], {'context': context})
        print(f"Producto {product_id} actualizado: {raw_name} -> {cleaned_name}")
    else:
        print("Los nombres no coinciden")