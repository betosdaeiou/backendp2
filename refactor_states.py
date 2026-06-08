import os
import glob

replacements = {
    '"Reportado"': '"pendiente"',
    '"Asignado"': '"taller asignado"',
    '"En proceso"': '"en atención"',
    '"En Camino"': '"en camino"',
    '"Resuelto"': '"finalizado"',
    '"Cancelado"': '"cancelado"',
    '"Pagado"': '"finalizado"' # Assuming pagado is end of life for the scope of the incident UI state
}

def process_file(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    new_content = content
    for old, new in replacements.items():
        new_content = new_content.replace(old, new)
        # Also handle single quotes if any
        new_content = new_content.replace(old.replace('"', "'"), new.replace('"', "'"))
        
    if new_content != content:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(new_content)
        print(f"Updated {filepath}")

for root, _, files in os.walk('src'):
    for file in files:
        if file.endswith('.py'):
            process_file(os.path.join(root, file))

print("Done.")
