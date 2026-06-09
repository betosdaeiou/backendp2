import psycopg2
conn = psycopg2.connect('postgresql://postgres:password@localhost:5432/emergencias')
cur = conn.cursor()
cur.execute('SELECT "Id", "Nombre", "tenant_id" FROM public."Taller"')
print("Talleres:", cur.fetchall())
