import psycopg2
conn = psycopg2.connect('postgresql://postgres:password@localhost:5432/emergencias')
cur = conn.cursor()
cur.execute('SELECT id, estado FROM public."Incidente"')
for row in cur.fetchall():
    print(row)
