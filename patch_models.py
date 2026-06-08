import os

path = 'src/modules/operations/models.py'

with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

old_model = """    id = Column(Integer, primary_key=True, autoincrement=True)
    monto = Column(Integer)
    mensaje = Column(String(500))
    estado = Column(String(50), default="Pendiente")"""

new_model = """    id = Column(Integer, primary_key=True, autoincrement=True)
    monto = Column(Integer)
    mensaje = Column(String(500))
    tiempo_estimado = Column(String(100), nullable=True)
    estado = Column(String(50), default="Pendiente")"""

content = content.replace(old_model, new_model)

with open(path, 'w', encoding='utf-8') as f:
    f.write(content)

print("models.py patched")
