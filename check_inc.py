import os
import sys
from sqlalchemy.orm import Session
from src.core.database import SessionLocal
from src.models import Incidente

def check():
    db = SessionLocal()
    try:
        count = db.query(Incidente).count()
        pendientes = db.query(Incidente).filter(Incidente.estado == 'pendiente').count()
        print(f"Total incidentes: {count}")
        print(f"Incidentes pendientes: {pendientes}")
        
        incs = db.query(Incidente).order_by(Incidente.id.desc()).all()
        for i in incs:
            print(f"ID: {i.id}, estado: {i.estado}, tenant: {i.tenant_id}")
    finally:
        db.close()

if __name__ == "__main__":
    check()
