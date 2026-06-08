import os
import sys

# Asegurar que el directorio raíz esté en el path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.core.database import Base, engine
from src.seed import main

if __name__ == "__main__":
    print("Borrando todas las tablas de la base de datos...")
    Base.metadata.drop_all(bind=engine)
    
    print("Recreando las tablas y ejecutando el seeder...")
    main()
    
    print("¡Base de datos recreada y poblada con éxito!")
