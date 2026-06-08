import psycopg2

try:
    conn = psycopg2.connect('postgresql://postgres:password@localhost:5432/emergencias')
    conn.autocommit = True
    cursor = conn.cursor()
    cursor.execute('ALTER TABLE "Cotizacion" ADD COLUMN tiempo_estimado VARCHAR(100);')
    print('Column added successfully')
    conn.close()
except Exception as e:
    print('Error:', e)
