import os

path = 'src/modules/operations/models.py'

with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

old_fields = """    id = Column(Integer, primary_key=True, autoincrement=True)
    coordenadagps = Column(String(255))
    estado = Column(String(50))
    fecha = Column(String(50))
    vehiculoconductor_id = Column(Integer, ForeignKey('VehiculoConductor.id', ondelete="CASCADE"), nullable=False)
    taller_id = Column(Integer, ForeignKey('Taller.Id', ondelete="SET NULL"), nullable=True)
    tenant_id = Column(Integer, ForeignKey('Tenant.Id', ondelete="CASCADE"), nullable=True)"""

new_fields = """    id = Column(Integer, primary_key=True, autoincrement=True)
    coordenadagps = Column(String(255))
    estado = Column(String(50))
    fecha = Column(String(50))
    fecha_asignacion = Column(String(50), nullable=True)
    fecha_llegada = Column(String(50), nullable=True)
    fecha_finalizacion = Column(String(50), nullable=True)
    vehiculoconductor_id = Column(Integer, ForeignKey('VehiculoConductor.id', ondelete="CASCADE"), nullable=False)
    taller_id = Column(Integer, ForeignKey('Taller.Id', ondelete="SET NULL"), nullable=True)
    tenant_id = Column(Integer, ForeignKey('Tenant.Id', ondelete="CASCADE"), nullable=True)"""

content = content.replace(old_fields, new_fields)

with open(path, 'w', encoding='utf-8') as f:
    f.write(content)

print("models.py patched for Incidente timestamps")
