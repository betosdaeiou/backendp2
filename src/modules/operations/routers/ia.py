from src.core.database import get_db
from src.modules.iam.dependencies import get_current_user
from src.modules.operations.models import Evidencia, Incidente
from src.modules.operations.models import AnalisisIA

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from src.modules.operations.services import ai_service

router = APIRouter(
    prefix="/ia",
    tags=["Inteligencia Artificial"]
)

@router.post("/analizar-evidencia/{incidente_id}")
def analizar_evidencia_endpoint(incidente_id: int, forzar_reanalisis: bool = False, db: Session = Depends(get_db)):
    incidente = db.query(Incidente).filter(Incidente.id == incidente_id).first()
    if not incidente:
        raise HTTPException(status_code=404, detail="Incidente no encontrado")
        
    analisis_record = db.query(AnalisisIA).filter(AnalisisIA.incidente_id == incidente_id).first()
    
    if analisis_record and analisis_record.Clasificacion and not forzar_reanalisis:
        return {
            "incidente_id": incidente_id,
            "analisis_ia": analisis_record.Clasificacion,
            "fuente": "cache_bd"
        }
        
    evidencia = db.query(Evidencia).filter(Evidencia.incidente_id == incidente_id).first()
    if not evidencia:
        raise HTTPException(status_code=404, detail="No hay evidencia asociada a este incidente")
        
    descripcion_usuario = evidencia.descripcion or "El usuario no proporcionó descripción textual."
    analisis = ai_service.analizar_evidencia_visual(descripcion=descripcion_usuario)
    
    if not analisis_record:
        analisis_record = AnalisisIA(incidente_id=incidente_id, Clasificacion=analisis)
        db.add(analisis_record)
    else:
        analisis_record.Clasificacion = analisis
        
    db.commit()
    
    return {
        "incidente_id": incidente_id,
        "analisis_ia": analisis,
        "fuente": "api_gemini"
    }

@router.post("/generar-reporte/{incidente_id}")
def generar_reporte_endpoint(incidente_id: int, forzar_reanalisis: bool = False, db: Session = Depends(get_db)):
    incidente = db.query(Incidente).filter(Incidente.id == incidente_id).first()
    if not incidente:
        raise HTTPException(status_code=404, detail="Incidente no encontrado")
        
    analisis_record = db.query(AnalisisIA).filter(AnalisisIA.incidente_id == incidente_id).first()
    if analisis_record and analisis_record.Resumen and not forzar_reanalisis:
        return {
            "incidente_id": incidente_id,
            "reporte_ejecutivo": analisis_record.Resumen,
            "fuente": "cache_bd"
        }
        
    datos_dict = {
        "id": incidente.id,
        "estado": incidente.estado,
        "fecha": incidente.fecha,
        "taller_id": incidente.taller_id,
        "coordenadagps": incidente.coordenadagps
    }
    
    reporte = ai_service.generar_reporte_enriquecido(datos_dict)
    
    if not analisis_record:
        analisis_record = AnalisisIA(incidente_id=incidente_id, Resumen=reporte)
        db.add(analisis_record)
    else:
        analisis_record.Resumen = reporte
        
    db.commit()
    
    return {
        "incidente_id": incidente_id,
        "reporte_ejecutivo": reporte,
        "fuente": "api_gemini"
    }



