import os

# SCHEMAS
path_schemas = 'src/modules/operations/schemas.py'

with open(path_schemas, 'r', encoding='utf-8') as f:
    content_schemas = f.read()

old_schema_base = """class CotizacionBase(BaseModel):
    monto: int
    mensaje: str"""

new_schema_base = """class CotizacionBase(BaseModel):
    monto: int
    mensaje: str
    tiempo_estimado: Optional[str] = None"""

content_schemas = content_schemas.replace(old_schema_base, new_schema_base)

with open(path_schemas, 'w', encoding='utf-8') as f:
    f.write(content_schemas)


# ROUTERS
path_routers = 'src/modules/operations/routers/incidentes.py'
with open(path_routers, 'r', encoding='utf-8') as f:
    content_routers = f.read()

old_cotizacion = """    nueva_cotizacion = Cotizacion(
        monto=payload.monto,
        mensaje=payload.mensaje,
        fecha_creacion=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        incidente_id=incidente_id,
        taller_id=taller.Id,
        tenant_id=current_user.tenant_id
    )"""

new_cotizacion = """    nueva_cotizacion = Cotizacion(
        monto=payload.monto,
        mensaje=payload.mensaje,
        tiempo_estimado=payload.tiempo_estimado,
        fecha_creacion=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        incidente_id=incidente_id,
        taller_id=taller.Id,
        tenant_id=current_user.tenant_id
    )"""

content_routers = content_routers.replace(old_cotizacion, new_cotizacion)

with open(path_routers, 'w', encoding='utf-8') as f:
    f.write(content_routers)

print("schemas.py and incidentes.py patched")
