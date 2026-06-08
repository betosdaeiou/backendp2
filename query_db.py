import psycopg2

try:
    conn = psycopg2.connect('postgresql://postgres:password@localhost:5432/emergencias')
    cur = conn.cursor()
    
    print("--- Incidentes ---")
    cur.execute('SELECT id, estado, fecha FROM "Incidente" LIMIT 10;')
    for row in cur.fetchall():
        print(row)
        
    print("\n--- Bitacora ---")
    cur.execute('SELECT id, accion, descripcion, fecha FROM "Bitacora" LIMIT 10;')
    for row in cur.fetchall():
        print(row)
        
    conn.close()
except Exception as e:
    print(e)
