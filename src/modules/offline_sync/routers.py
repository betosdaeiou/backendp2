from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlalchemy.orm import Session
from typing import List, Optional
from pydantic import BaseModel

from src.core.database import get_db
from src.modules.iam.dependencies import get_current_user
from src.modules.iam.models import Usuario
from src.modules.operations.models import Incidente, Evidencia, AnalisisIA
from src.modules.catalog.models import VehiculoConductor
from src.modules.operations.services.ai_service import analizar_incidente
from src.shared.notificacion_util import crear_notificacion
from src.modules.catalog.models import Taller

router = APIRouter(prefix="/offline-sync", tags=["Offline Synchronization"])

# ─── MODELOS PARA SYNC BÁSICO (legacy) ────────────────────────────────────────

class IncidenteOfflineSync(BaseModel):
    local_id: str
    coordenadagps: str
    fecha: str
    descripcion: str

class SyncPayload(BaseModel):
    incidentes: List[IncidenteOfflineSync]

class SyncResponse(BaseModel):
    local_id: str
    server_id: int
    status: str


# ─── MODELO PARA SYNC COMPLETO (con fotos, audio, vehículo) ───────────────────

class IncidenteCompletoSync(BaseModel):
    local_id: str
    coordenadagps: str
    fecha: str
    descripcion: str = ""
    vehiculo_id: Optional[int] = None
    fotos: str = ""       # Base64 separado por '|||'
    audio: str = ""       # Base64 completo del audio

class SyncCompletoResponse(BaseModel):
    local_id: str
    server_id: int
    status: str


# ─── ENDPOINT LEGACY: SYNC BÁSICO (sin fotos/audio) ───────────────────────────

@router.post("/incidentes", response_model=List[SyncResponse])
def sincronizar_incidentes(
    payload: SyncPayload,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user)
):
    """Sincroniza un lote de incidentes creados offline en Flutter (sin multimedia)."""
    if not current_user.conductor:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, 
            detail="Solo conductores pueden sincronizar incidentes."
        )

    # Obtenemos el vehículo activo del conductor (o asumimos el primero para este ejemplo)
    if not current_user.conductor.vehiculo_conductores:
        raise HTTPException(status_code=400, detail="El conductor no tiene vehículos registrados.")
        
    vc_id = current_user.conductor.vehiculo_conductores[0].id
    tenant_id = current_user.tenant_id

    respuestas = []

    for item in payload.incidentes:
        try:
            # 1. Crear el incidente
            nuevo_incidente = Incidente(
                coordenadagps=item.coordenadagps,
                estado="pendiente",
                fecha=item.fecha,
                vehiculoconductor_id=vc_id,
                tenant_id=tenant_id
            )
            db.add(nuevo_incidente)
            db.commit()
            db.refresh(nuevo_incidente)

            # 2. Guardar la descripción en la Evidencia
            nueva_evidencia = Evidencia(
                descripcion=item.descripcion,
                incidente_id=nuevo_incidente.id
            )
            db.add(nueva_evidencia)
            db.commit()

            respuestas.append(SyncResponse(
                local_id=item.local_id,
                server_id=nuevo_incidente.id,
                status="synchronized"
            ))

        except Exception as e:
            db.rollback()
            respuestas.append(SyncResponse(
                local_id=item.local_id,
                server_id=-1,
                status=f"error: {str(e)}"
            ))

    return respuestas


# ─── ENDPOINT COMPLETO: SYNC CON FOTOS, AUDIO Y VEHÍCULO ─────────────────────

@router.post("/incidente-completo", response_model=SyncCompletoResponse)
def sincronizar_incidente_completo(
    payload: IncidenteCompletoSync,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user)
):
    """
    Sincroniza un incidente offline COMPLETO con fotos, audio y vehículo.
    Procesa las fotos y audio base64 igual que el endpoint /incidentes/reportar.
    """
    if not current_user.conductor:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, 
            detail="Solo conductores pueden sincronizar incidentes."
        )

    if not current_user.conductor.vehiculo_conductores:
        raise HTTPException(status_code=400, detail="El conductor no tiene vehículos registrados.")

    tenant_id = current_user.tenant_id

    # Determinar el vehiculoconductor_id
    vc_id = None
    if payload.vehiculo_id:
        vc = db.query(VehiculoConductor).filter(
            VehiculoConductor.conductor_id == current_user.conductor.IdUsuario,
            VehiculoConductor.vehiculo_id == payload.vehiculo_id
        ).first()
        if vc:
            vc_id = vc.id

    # Fallback al primer vehículo si no se encontró
    if vc_id is None:
        vc_id = current_user.conductor.vehiculo_conductores[0].id

    try:
        # 1. Crear Incidente
        nuevo_incidente = Incidente(
            coordenadagps=payload.coordenadagps,
            estado="pendiente",
            fecha=payload.fecha,
            vehiculoconductor_id=vc_id,
            tenant_id=tenant_id
        )
        db.add(nuevo_incidente)
        db.commit()
        db.refresh(nuevo_incidente)

        # 2. Procesar fotos base64 → archivos en disco
        fotos_urls = []
        fotos_final = ""
        if payload.fotos and len(payload.fotos) > 100:
            import base64, uuid, os
            upload_dir = os.path.join("uploads", "incidentes", str(nuevo_incidente.id))
            os.makedirs(upload_dir, exist_ok=True)

            partes = payload.fotos.split('|||') if '|||' in payload.fotos else [payload.fotos]
            for parte in partes:
                parte = parte.strip()
                if not parte:
                    continue
                try:
                    img_bytes = base64.b64decode(parte)
                    filename = f"{uuid.uuid4().hex}.jpg"
                    filepath = os.path.join(upload_dir, filename)
                    with open(filepath, 'wb') as f:
                        f.write(img_bytes)
                    fotos_urls.append(f"/uploads/incidentes/{nuevo_incidente.id}/{filename}")
                except Exception:
                    continue

            fotos_final = '|||'.join(fotos_urls) if fotos_urls else ""

        # 3. Procesar audio base64 → archivo en disco
        audio_url = None
        if payload.audio and len(payload.audio) > 50:
            try:
                import base64, uuid, os
                upload_dir = os.path.join("uploads", "incidentes", str(nuevo_incidente.id))
                os.makedirs(upload_dir, exist_ok=True)

                audio_bytes = base64.b64decode(payload.audio)
                audio_filename = f"audio_{uuid.uuid4().hex}.m4a"
                audio_filepath = os.path.join(upload_dir, audio_filename)
                with open(audio_filepath, 'wb') as f:
                    f.write(audio_bytes)
                audio_url = f"/uploads/incidentes/{nuevo_incidente.id}/{audio_filename}"
            except Exception as e_audio:
                print(f"[Offline-Sync] Error guardando audio: {e_audio}")

        # 4. Crear Evidencia completa
        nueva_evidencia = Evidencia(
            audio=audio_url,
            descripcion=payload.descripcion,
            fotos=fotos_final,
            incidente_id=nuevo_incidente.id
        )
        db.add(nueva_evidencia)
        db.commit()

        # 5. Ejecutar análisis IA (best-effort, no falla el sync)
        try:
            resultado_ia = analizar_incidente(
                descripcion=payload.descripcion,
                audio_url=audio_url,
                fotos_urls=fotos_urls if fotos_urls else None,
            )
            analisis = AnalisisIA(
                incidente_id=nuevo_incidente.id,
                Clasificacion=resultado_ia.get("Clasificacion"),
                NivelPrioridad=resultado_ia.get("NivelPrioridad"),
                Resumen=resultado_ia.get("Resumen"),
                TranscripcionAudio=resultado_ia.get("Transcripcion"),
                informacion_valida=resultado_ia.get("informacion_valida", True),
            )
            db.add(analisis)
            db.commit()
            print(f"[Offline-Sync] AnalisisIA guardado para incidente #{nuevo_incidente.id}")
        except Exception as e_ia:
            print(f"[Offline-Sync] IA falló para incidente #{nuevo_incidente.id}: {e_ia}")
            db.rollback()

        # 6. Notificar talleres
        try:
            talleres = db.query(Taller).all()
            for t in talleres:
                crear_notificacion(
                    db,
                    t.IdUsuario,
                    "Nuevo Siniestro (Sync Offline)",
                    f"Se sincronizó el incidente #{nuevo_incidente.id} desde un reporte offline."
                )
        except Exception as e_notif:
            print(f"[Offline-Sync] Error notificando talleres: {e_notif}")

        return SyncCompletoResponse(
            local_id=payload.local_id,
            server_id=nuevo_incidente.id,
            status="synchronized"
        )

    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al sincronizar incidente offline: {str(e)}"
        )
