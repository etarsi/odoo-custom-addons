import psycopg2
import csv

# 🔧 Configuración de la base de datos
DB_NAME = "one"
DB_USER = "external_query"      # tu usuario postgres/odoo
DB_PASSWORD = "odoo"
DB_HOST = "localhost"
DB_PORT = "5432"

# 📂 Archivo de salida
archivo_contactos = "contactos_odoo.csv"

try:
    # Conectar a PostgreSQL
    conn = psycopg2.connect(
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD,
        host=DB_HOST,
        port=DB_PORT
    )
    cursor = conn.cursor()

    # Consultar los contactos con CUIT (vat no vacío)
    cursor.execute("""
        SELECT id, name, vat
        FROM res_partner
        WHERE vat IS NOT NULL AND vat != '';
    """)

    resultados = cursor.fetchall()

    # Guardar en CSV
    with open(archivo_contactos, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(["id", "name", "vat"])
        for row in resultados:
            writer.writerow(row)

    print(f"Se exportaron {len(resultados)} contactos a {archivo_contactos}")

    cursor.close()
    conn.close()

except Exception as e:
    print("❌ Error al conectar a la base de datos:", e)
