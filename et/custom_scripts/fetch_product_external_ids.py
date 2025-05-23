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

default_codes = [12221,12248,12249,12222,12227,12245,12220,12223,12251,12252,12225,12226,12246,12230,12231,12247,12255,12256,12232,12257,10117,12211,12217,12151,
12202,12204,12152,12205,12207,12241,12259,12154,12153,10119,10118,12027,12028,12064,12065,12026,12150,12260,10106,12011,12014,12013,12015,12243,12262,12066,12067,
12214,12200,12016,12017,12216,12106,12018,12244,12264,10109,12208,12215,12201,12019,12020,12021,12104,10120,12022,12023,12024,12105,10111,10112,12265,12266,12267,
12238,12239,12209,12240,12268,12269,12270,12210,12203,12233,12206,12234,12242,12235,12236,12272,12212,12213,12237,12273,12274,10100,12000,12001,12050,12051,10102,
12003,12004,10124,12008,12007,12002,12052,12053,12100,12005,12006,10104,12010,12009,12275,12276,12277,12278]

results = []
for code in default_codes:
    # Buscar el product.product por default_code
    product_ids = models.execute_kw(db, uid, password, 'product.product', 'search', [[('default_code', '=', code)]])
    
    if product_ids:
        product_id = product_ids[0]
        
        # Buscar el External ID en ir.model.data para product.product
        external_id = models.execute_kw(db, uid, password, 'ir.model.data', 'search_read', [
            [('model', '=', 'product.product'), ('res_id', '=', product_id)],
            ['complete_name']
        ])
        
        if not external_id:
            # Si no tiene External ID en product.product, buscar en product.template
            template_data = models.execute_kw(db, uid, password, 'product.product', 'read', [[product_id]], {'fields': ['product_tmpl_id']})
            
            if template_data and 'product_tmpl_id' in template_data[0]:
                template_id = template_data[0]['product_tmpl_id'][0]
                external_id = models.execute_kw(db, uid, password, 'ir.model.data', 'search_read', [
                    [('model', '=', 'product.template'), ('res_id', '=', template_id)],
                    ['complete_name']
                ])
        
        external_id_value = external_id[0]['complete_name'] if external_id else "Sin External ID"
        results.append(f"{external_id_value}")

output_file = "/opt/odoo15/odoo-custom-addons/et/custom_scripts/product_external_ids.txt"

with open(output_file, "w") as f:
    for line in results:
        f.write(line + "\n")

print(f"Archivo guardado en {output_file}")
