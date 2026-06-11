import os
import sys
from sqlalchemy.orm import Session
from src.core.database import SessionLocal
from src.models import Incidente

def revert_fix():
    db = SessionLocal()
    try:
        # Revert incidents that were created recently and we changed from Reportado to pendiente
        incs = db.query(Incidente).filter(Incidente.id.in_([43, 44])).all()
        for i in incs:
            i.estado = 'Reportado'
        db.commit()
        print("Reverted latest incidents back to Reportado.")
    finally:
        db.close()

if __name__ == "__main__":
    revert_fix()
