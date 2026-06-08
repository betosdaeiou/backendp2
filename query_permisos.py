import psycopg2

conn = psycopg2.connect('postgresql://postgres:password@localhost:5432/emergencias')
cur = conn.cursor()
cur.execute('SELECT r."Nombre", p."Nombre" FROM "Rol" r JOIN "Rol_Permiso" rp ON r."Id" = rp."IdRol" JOIN "Permiso" p ON p."Id" = rp."IdPermiso";')
print(cur.fetchall())
