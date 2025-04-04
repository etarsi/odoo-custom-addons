import xmlrpc.client

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

for p in products_ids:
    print(p)