import psycopg2
conn = psycopg2.connect('postgresql://postgres:password@localhost:5432/emergencias')
cur = conn.cursor()
cur.execute('SELECT "Id", "Correo", "tenant_id", "rol_id" FROM public."Usuario" WHERE "Correo" = \'admin.autofix@demo.com\'')
print("Admin Tenant Usuario:", cur.fetchall())

cur.execute('SELECT "Id", "Nombre" FROM public."Rol"')
print("Roles:", cur.fetchall())
