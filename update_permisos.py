import psycopg2

conn = psycopg2.connect('postgresql://postgres:password@localhost:5432/emergencias')
cur = conn.cursor()

try:
    # Obtener IDs de Roles
    cur.execute("SELECT \"Id\", \"Nombre\" FROM \"Rol\";")
    roles = {r[1]: r[0] for r in cur.fetchall()}

    # Obtener IDs de Permisos
    cur.execute("SELECT \"Id\", \"Nombre\" FROM \"Permiso\";")
    permisos = {p[1]: p[0] for p in cur.fetchall()}

    id_rol_taller = roles.get('Taller')
    id_rol_mecanico = roles.get('Mecanico')

    # Permisos a otorgar al Taller (los que le faltan para igualar a Admin Tenant)
    permisos_taller = ['Ver Usuarios', 'Gestionar Roles', 'Ver Bitacora', 'Ver Analytics']
    
    # Permisos a otorgar al Mecanico
    permisos_mecanico = ['Ver Bitacora']

    for p in permisos_taller:
        id_perm = permisos.get(p)
        if id_perm and id_rol_taller:
            cur.execute(f"INSERT INTO \"Rol_Permiso\" (\"IdRol\", \"IdPermiso\") VALUES ({id_rol_taller}, {id_perm}) ON CONFLICT DO NOTHING;")

    for p in permisos_mecanico:
        id_perm = permisos.get(p)
        if id_perm and id_rol_mecanico:
            cur.execute(f"INSERT INTO \"Rol_Permiso\" (\"IdRol\", \"IdPermiso\") VALUES ({id_rol_mecanico}, {id_perm}) ON CONFLICT DO NOTHING;")

    conn.commit()
    print("Permisos actualizados correctamente en la base de datos.")

except Exception as e:
    conn.rollback()
    print("Error:", e)

finally:
    cur.close()
    conn.close()
