import csv

# Archivos de entrada y salida
archivo_contactos = 'contactos_odoo.csv'
archivo_txt_perc = '/opt/odoo15/odoo-custom-addons/et/custom_scripts/ARBA/PadronRGSPer022026.TXT'
archivo_txt_ret = '/opt/odoo15/odoo-custom-addons/et/custom_scripts/ARBA/PadronRGSRet022026.TXT'
archivo_salida = 'coincidencias_arba.csv'

def limpiar_cuit(valor):
    # deja solo dígitos (sirve si viene con guiones)
    return ''.join([c for c in (valor or '') if c.isdigit()]).strip()

def parse_float(valor):
    try:
        # ARBA viene "3,00"
        return float((valor or '0').replace(',', '.'))
    except:
        return 0.0

# 1️⃣ Leer contactos de Odoo (CSV)
contactos = {}
with open(archivo_contactos, newline='', encoding='utf-8') as f:
    reader = csv.DictReader(f)
    for row in reader:
        cuit = limpiar_cuit(row.get('vat'))
        if cuit:
            contactos[cuit] = row.get('id')  # Solo nos interesa el ID en este caso

print(f"📥 Contactos cargados: {len(contactos)}")

# 2️⃣ Leer padrones ARBA (P y R) y cruzar
# Vamos a acumular por CUIT para unir percepción + retención aunque estén en archivos distintos
coincidencias_por_cuit = {}

def procesar_padron(archivo_txt, tipo):
    """
    tipo = 'P' (percepción) o 'R' (retención)
    Layout real:
    TIPO;FECHA_PUB;VIG_DESDE;VIG_HASTA;CUIT;TIPO_CONTRIB;M1;M2;ALICUOTA;GRUPO;
    """
    if not archivo_txt:
        return

    with open(archivo_txt, encoding='latin-1') as f:
        for i, linea in enumerate(f):
            partes = linea.strip().split(';')
            # Ej: termina con ; entonces split trae un "" al final -> no molesta
            if len(partes) < 10:
                continue

            tipo_linea = (partes[0] or '').strip().upper()
            if tipo_linea != tipo:
                continue

            cuit_txt = limpiar_cuit(partes[4])
            alicuota = parse_float(partes[8])   # 0,00 / 3,00 / 5,00 etc.
            grupo = (partes[9] or '').strip()

            if cuit_txt in contactos:
                if cuit_txt not in coincidencias_por_cuit:
                    coincidencias_por_cuit[cuit_txt] = {
                        'partner_id': contactos[cuit_txt],
                        'cuit': cuit_txt,
                        'percepcion': 0.0,
                        'retencion': 0.0,
                        'grupo_percepcion': '',
                        'grupo_retencion': '',
                    }

                if tipo == 'P':
                    coincidencias_por_cuit[cuit_txt]['percepcion'] = alicuota
                    coincidencias_por_cuit[cuit_txt]['grupo_percepcion'] = grupo
                else:
                    coincidencias_por_cuit[cuit_txt]['retencion'] = alicuota
                    coincidencias_por_cuit[cuit_txt]['grupo_retencion'] = grupo

            if i > 0 and i % 100000 == 0:
                print(f"⏳ [{tipo}] Procesadas {i} líneas...")

# Procesamos primero percepciones y luego retenciones
procesar_padron(archivo_txt_perc, 'P')
procesar_padron(archivo_txt_ret, 'R')

# Pasamos a lista final
coincidencias = list(coincidencias_por_cuit.values())

# 3️⃣ Guardar coincidencias en archivo nuevo
with open(archivo_salida, 'w', newline='', encoding='utf-8') as f:
    fieldnames = ['partner_id', 'cuit', 'percepcion', 'retencion', 'grupo_percepcion', 'grupo_retencion']
    writer = csv.DictWriter(f, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(coincidencias)

print(f"✅ Coincidencias encontradas: {len(coincidencias)}")
print(f"📝 Archivo generado: {archivo_salida}")