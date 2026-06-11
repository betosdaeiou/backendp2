import re

files = [
    r'c:\Users\aober\OneDrive\Documents\GitHub\lin\backendp2\src\modules\operations\routers\incidentes.py',
    r'c:\Users\aober\OneDrive\Documents\GitHub\lin\backendp2\src\modules\operations\routers\chat.py',
    r'c:\Users\aober\OneDrive\Documents\GitHub\lin\backendp2\src\modules\offline_sync\routers.py'
]

pattern = r'(crear_notificacion\([^)]+)\)'

def replacer(match):
    text = match.group(1)
    if 'background_tasks' in text:
        return text + ')'
    # We assume the last character is whitespace or string quote
    return text + ', background_tasks=background_tasks)'

for file_path in files:
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    new_content = re.sub(pattern, replacer, content)
    
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(new_content)

print("Done")
