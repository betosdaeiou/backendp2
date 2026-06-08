import os
import re

path = 'src/modules/operations/routers/incidentes.py'

with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Patch aceptar_cotizacion
old_asignar = """    # Asignar taller al incidente
    incidente.taller_id = cotizacion.taller_id
    incidente.estado = "taller asignado\""""

new_asignar = """    # Asignar taller al incidente
    incidente.taller_id = cotizacion.taller_id
    incidente.estado = "taller asignado"
    incidente.fecha_asignacion = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")"""

content = content.replace(old_asignar, new_asignar)

# 2. Patch actualizar_estado_incidente
old_actualizar = """    incidente.estado = payload.nuevo_estado
    db.commit()"""

new_actualizar = """    incidente.estado = payload.nuevo_estado
    fecha_actual = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    if payload.nuevo_estado.lower() in ["en camino", "en atención", "en atencion"]:
        if not incidente.fecha_llegada:
            incidente.fecha_llegada = fecha_actual
    elif payload.nuevo_estado.lower() == "resuelto":
        incidente.fecha_finalizacion = fecha_actual

    db.commit()"""

content = content.replace(old_actualizar, new_actualizar)


# 3. Patch asignar_taller
old_asignar_2 = """    incidente.taller_id = payload.taller_id
    incidente.estado = "Asignado"
    db.commit()"""

new_asignar_2 = """    incidente.taller_id = payload.taller_id
    incidente.estado = "Asignado"
    incidente.fecha_asignacion = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    db.commit()"""

content = content.replace(old_asignar_2, new_asignar_2)

with open(path, 'w', encoding='utf-8') as f:
    f.write(content)

print("incidentes.py patched")
