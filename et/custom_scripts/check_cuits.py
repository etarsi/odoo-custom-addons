import csv

# Archivos de entrada y salida
archivo_contactos = 'contactos_odoo.csv'
archivo_txt = '/opt/odoo15/odoo-custom-addons/et/custom_scripts/ARDJU008012026.TXT'
archivo_salida = 'coincidencias_agip.csv'

def parse_float(valor):
    try:
        return float(valor.replace(',', '.'))
    except:
        return 0.0

# 1️⃣ Leer contactos de Odoo (CSV)
contactos = {}
with open(archivo_contactos, newline='', encoding='utf-8') as f:
    reader = csv.DictReader(f)
    for row in reader:
        cuit = row['vat'].replace('-', '').strip()
        if cuit:
            contactos[cuit] = row['id']  # Solo nos interesa el ID en este caso

print(f"📥 Contactos cargados: {len(contactos)}")

# 2️⃣ Leer el padrón AGIP y cruzar
coincidencias = []
with open(archivo_txt, encoding='latin-1') as f:
    for i, linea in enumerate(f):
        partes = linea.strip().split(';')
        if len(partes) < 10:
            continue

        cuit_txt = partes[3].strip()
        percepcion = parse_float(partes[7])
        retencion = parse_float(partes[8])

        if cuit_txt in contactos:
            coincidencias.append({
                'partner_id': contactos[cuit_txt],
                'cuit': cuit_txt,
                'percepcion': percepcion,
                'retencion': retencion
            })

        if i > 0 and i % 100000 == 0:
            print(f"⏳ Procesadas {i} líneas...")

# 3️⃣ Guardar coincidencias en archivo nuevo
with open(archivo_salida, 'w', newline='', encoding='utf-8') as f:
    fieldnames = ['partner_id', 'cuit', 'percepcion', 'retencion']
    writer = csv.DictWriter(f, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(coincidencias)

print(f"✅ Coincidencias encontradas: {len(coincidencias)}")
print(f"📝 Archivo generado: {archivo_salida}")
