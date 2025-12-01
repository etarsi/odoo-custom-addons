import csv
import psycopg2
from datetime import datetime

# Configuración de la base de datos
DB_NAME = "one"
DB_USER = "external_query"
DB_PASSWORD = "odoo"
DB_HOST = "localhost"
DB_PORT = "5432"

# Archivo CSV con los resultados
archivo_entrada = "coincidencias_agip.csv"

# Constantes
TAG_ID = 19
COMPANY_IDS = [2, 3, 4]
FROM_DATETIME = datetime(2025, 12, 1, 0, 0, 0)
TO_DATETIME = datetime(2025, 12, 31, 23, 59, 59)

try:
    # Conexión
    conn = psycopg2.connect(
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD,
        host=DB_HOST,
        port=DB_PORT
    )
    cursor = conn.cursor()

    # Leer CSV y preparar inserts
    with open(archivo_entrada, newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        inserts = []

        for row in reader:
            partner_id = int(row['partner_id'])
            percepcion = float(row['percepcion'])
            retencion = float(row['retencion'])

            for company_id in COMPANY_IDS:
                inserts.append((
                    partner_id,
                    TAG_ID,
                    company_id,
                    percepcion,
                    retencion,
                    FROM_DATETIME,
                    TO_DATETIME
                ))

    print(f"🧾 Total de registros a insertar: {len(inserts)}")

    # Ejecutar insert
    cursor.executemany("""
        INSERT INTO res_partner_arba_alicuot
        (partner_id, tag_id, company_id, alicuota_percepcion, alicuota_retencion, from_date, to_date)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
    """, inserts)

    conn.commit()
    cursor.close()
    conn.close()
    print("✅ Inserción completa en res_partner_arba_alicuot")

except Exception as e:
    print("❌ Error:", e)