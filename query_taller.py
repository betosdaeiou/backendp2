import psycopg2
conn = psycopg2.connect('postgresql://postgres:password@localhost:5432/emergencias')
cur = conn.cursor()
cur.execute('SELECT "Id", "IdUsuario", "Nombre" FROM public."Taller" WHERE "IdUsuario" = 1')
print("Taller for user 1:", cur.fetchall())
