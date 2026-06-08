import psycopg2

try:
    conn = psycopg2.connect('postgresql://postgres:password@localhost:5432/emergencias')
    conn.autocommit = True
    cur = conn.cursor()
    
    cur.execute('ALTER TABLE "Incidente" ADD COLUMN IF NOT EXISTS fecha_asignacion VARCHAR(50);')
    cur.execute('ALTER TABLE "Incidente" ADD COLUMN IF NOT EXISTS fecha_llegada VARCHAR(50);')
    cur.execute('ALTER TABLE "Incidente" ADD COLUMN IF NOT EXISTS fecha_finalizacion VARCHAR(50);')
    print("Columnas añadidas a Incidente")
    
    conn.close()
except Exception as e:
    print("Error:", e)
