from src.core.database import get_db
from sqlalchemy import or_
from src.modules.iam.dependencies import get_current_user
from src.modules.operations.models import Evidencia, Incidente, MensajeChat
from src.modules.operations.models import AnalisisIA
from src.modules.catalog.models import Mecanico, ServicioTaller, Taller, VehiculoConductor, Conductor
from src.modules.operations.models import Cotizacion
from src.modules.iam.models import Usuario
from src.modules.catalog.schemas import ServicioTallerCreate, ServicioTallerOut, TallerDisponible
from src.modules.operations.schemas import AsignarMecanicos, AsignarTaller, IncidenteOut, IncidenteCreate, IncidenteDetalle, IncidentePendiente, MensajeChatCreate, MensajeChatOut
from src.modules.operations.schemas import CotizacionCreate, CotizacionOfrecer, CotizacionOut
from src.modules.operations.schemas import ReintentarAnalisisPayload, ActualizarEstadoIncidente
from src.modules.operations.services.ai_service import analizar_incidente
from src.shared.notificacion_util import crear_notificacion

from fastapi import APIRouter, Depends, HTTPException, status, Query, BackgroundTasks
from src.broker.manager import manager
import asyncio

async def broadcast_ws_event(tenant_id: int | None, room_id: str, payload: dict):
    """Emite el evento a la sala indicada Y a las salas complementarias (talleres, conductores, mecanicos)."""
    all_rooms = {"talleres", "conductores", "mecanicos", room_id}
    for room in all_rooms:
        if tenant_id is None:
            await manager.broadcast_all_tenants(payload, room)
        else:
            await manager.broadcast(payload, tenant_id, room)

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session, joinedload
from pydantic import BaseModel
from typing import List, Optional
import datetime
import math


router = APIRouter(
    prefix="/incidentes",
    tags=["Incidentes y Emergencias"]
)


def get_taller_para_usuario(current_user: Usuario, db: Session):
    """Obtiene el taller asociado al usuario (Admin de Taller) o el primer taller del tenant (Admin Tenant)."""
    if hasattr(current_user, 'talleres') and current_user.talleres:
        if isinstance(current_user.talleres, list) and len(current_user.talleres) > 0:
            return current_user.talleres[0]
        elif not isinstance(current_user.talleres, list):
            return current_user.talleres
            
    is_admin = current_user.rol and current_user.rol.Nombre == "Admin Tenant"
    if is_admin and current_user.tenant_id:
        return db.query(Taller).filter(Taller.tenant_id == current_user.tenant_id).first()
        
    return None

@router.get("/solicitudes-pendientes", response_model=List[IncidentePendiente])
def solicitudes_pendientes(
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user)
):
    """Devuelve todos los incidentes con estado 'pendiente' para que los talleres puedan ofrecer cotización, con distancia calculada."""
    taller_usuario = get_taller_para_usuario(current_user, db)
    if not taller_usuario:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Solo talleres o administradores pueden ver solicitudes pendientes")

    # Obtener coordenadas del taller del usuario
    taller_lat, taller_lng = None, None
    if taller_usuario and taller_usuario.Coordenadas:
        try:
            parts = taller_usuario.Coordenadas.replace(" ", "").split(",")
            taller_lat = float(parts[0])
            taller_lng = float(parts[1])
        except (ValueError, IndexError):
            pass

    incidentes = (
        db.query(Incidente)
        .options(
            joinedload(Incidente.evidencias), 
            joinedload(Incidente.taller), 
            joinedload(Incidente.analisis_ia),
            joinedload(Incidente.vehiculoconductor).joinedload(VehiculoConductor.vehiculo),
            joinedload(Incidente.cotizaciones)
        )
        .filter(
            Incidente.estado.in_(["pendiente", "Reportado"]),
            or_(
                Incidente.tenant_id == current_user.tenant_id,
                Incidente.tenant_id == None
            )
        )
        .order_by(Incidente.id.desc())
        .all()
    )

    # Calcular distancia para cada incidente
    resultado = []
    for inc in incidentes:
        distancia = None
        if taller_lat is not None and taller_lng is not None and inc.coordenadagps:
            try:
                inc_parts = inc.coordenadagps.replace(" ", "").split(",")
                inc_lat = float(inc_parts[0])
                inc_lng = float(inc_parts[1])
                distancia = round(_haversine(taller_lat, taller_lng, inc_lat, inc_lng), 1)
            except (ValueError, IndexError):
                pass

        # Convertir ORM a dict para agregar el campo extra
        inc_data = IncidentePendiente.model_validate(inc)
        inc_data.distancia_km = distancia
        resultado.append(inc_data)

    # Ordenar por distancia (los más cercanos primero, sin distancia al final)
    resultado.sort(key=lambda x: x.distancia_km if x.distancia_km is not None else 99999)

    return resultado



def _haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calcula la distancia en km entre dos coordenadas GPS usando la fórmula de Haversine."""
    R = 6371  # Radio de la Tierra en km
    d_lat = math.radians(lat2 - lat1)
    d_lon = math.radians(lon2 - lon1)
    a = (math.sin(d_lat / 2) ** 2 +
         math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) *
         math.sin(d_lon / 2) ** 2)
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return round(R * c, 2)


@router.post("/reportar", response_model=IncidenteOut)
def reportar_incidente(
    payload: IncidenteCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user)
):
    if not current_user.conductor:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Solo conductores pueden reportar siniestros")

    # Verificar que el conductor sí tiene registrado ese vehículo (y tomar el VehiculoConductor)
    vehiculo_conductor = db.query(VehiculoConductor).filter(
        VehiculoConductor.conductor_id == current_user.conductor.IdUsuario,
        VehiculoConductor.vehiculo_id == payload.vehiculo_id
    ).first()

    if not vehiculo_conductor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail="No tienes registrado este vehículo para reportarlo en un siniestro"
        )

    # Crear Incidente
    fecha_actual = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    nuevo_incidente = Incidente(
        coordenadagps=payload.coordenadagps,
        estado=payload.estado or "pendiente",
        fecha=payload.fecha or fecha_actual,
        vehiculoconductor_id=vehiculo_conductor.id,
        tenant_id=current_user.tenant_id
    )

    db.add(nuevo_incidente)
    db.commit()
    db.refresh(nuevo_incidente)

    # Crear Evidencia ligada al Incidente
    evidencia_data = payload.evidencia.model_dump() if hasattr(payload.evidencia, 'model_dump') else payload.evidencia.dict()
    fotos_raw = evidencia_data.get('fotos', '') or ''
    
    # Procesar fotos Base64 → archivos en disco
    fotos_urls = []
    if fotos_raw and '|||' in fotos_raw or (fotos_raw and len(fotos_raw) > 200):
        import base64, uuid, os
        upload_dir = os.path.join("uploads", "incidentes", str(nuevo_incidente.id))
        os.makedirs(upload_dir, exist_ok=True)
        
        partes = fotos_raw.split('|||') if '|||' in fotos_raw else [fotos_raw]
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
        fotos_final = '|||'.join(fotos_urls) if fotos_urls else fotos_raw
    else:
        fotos_final = fotos_raw

    # Decodificar y guardar audio si existe
    audio_raw = evidencia_data.get('audio')
    audio_url = None
    if audio_raw and len(audio_raw) > 50: # Evitar strings vacíos o cortos
        try:
            audio_bytes = base64.b64decode(audio_raw)
            audio_filename = f"audio_{uuid.uuid4().hex}.m4a"
            audio_filepath = os.path.join(upload_dir, audio_filename)
            with open(audio_filepath, 'wb') as f:
                f.write(audio_bytes)
            audio_url = f"/uploads/incidentes/{nuevo_incidente.id}/{audio_filename}"
        except Exception as e_audio:
            print(f"[Audio] Error guardando archivo: {e_audio}")

    nueva_evidencia = Evidencia(
        audio=audio_url or audio_raw, # Guardamos la URL si se creó el archivo
        descripcion=evidencia_data.get('descripcion'),
        fotos=fotos_final,
        incidente_id=nuevo_incidente.id
    )
    
    db.add(nueva_evidencia)
    db.commit()

    # ── Análisis IA ────────────────────────────────────────────────────────────
    # Generamos y persistimos el análisis justo después de guardar la evidencia.
    # Si la IA falla, el incidente ya está guardado y no se pierde nada.
    try:
        descripcion_incidente = evidencia_data.get('descripcion') or ""
        audio_raw = evidencia_data.get('audio') or None
        audio_disponible = bool(audio_raw)

        # Pasar las URLs de fotos y audio guardadas en disco para análisis multimodal
        resultado_ia = analizar_incidente(
            descripcion=descripcion_incidente,
            audio_url=audio_url,
            fotos_urls=fotos_urls if fotos_urls else None,
        )

        analisis = AnalisisIA(
            incidente_id=nuevo_incidente.id,
            Clasificacion=resultado_ia.get("Clasificacion"),
            NivelPrioridad=resultado_ia.get("NivelPrioridad"),
            Resumen=resultado_ia.get("Resumen"),
            TranscripcionAudio=resultado_ia.get("Transcripcion", audio_raw),
            informacion_valida=resultado_ia.get("informacion_valida", True),
        )
        db.add(analisis)
        db.commit()
        print(f"[AI] AnalisisIA guardado para incidente #{nuevo_incidente.id}: {resultado_ia}")
    except Exception as e_ia:
        print(f"[AI] Error al generar/guardar AnalisisIA para incidente #{nuevo_incidente.id}: {e_ia}")
        db.rollback()  # revertir sólo el commit del análisis; el incidente ya está guardado
    # ──────────────────────────────────────────────────────────────────────────


    db.refresh(nuevo_incidente)

    # Notificar a todos los talleres sobre el nuevo incidente
    try:
        talleres = db.query(Taller).all()
        for t in talleres:
            crear_notificacion(
                db, 
                t.IdUsuario, 
                "Nuevo Siniestro Reportado", 
                f"Se ha reportado un incidente #{nuevo_incidente.id}. Revisa las solicitudes pendientes para ofrecer una cotización."
            , background_tasks=background_tasks)
    except Exception as e_notif:
        print(f"[Notificación] Error al notificar talleres: {e_notif}")

    background_tasks.add_task(
        broadcast_ws_event,
        current_user.tenant_id,
        "talleres",
        {"action": "nuevo_incidente", "incidente_id": nuevo_incidente.id}
    )

    return nuevo_incidente




@router.post("/{incidente_id}/reintentar-analisis", response_model=IncidenteDetalle)
def reintentar_analisis(
    incidente_id: int,
    payload: ReintentarAnalisisPayload,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user)
):
    """Permite al conductor agregar más descripción y volver a ejecutar el análisis IA."""
    if not current_user.conductor:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Solo conductores pueden reintentar el análisis")

    incidente = (
        db.query(Incidente)
        .options(
            joinedload(Incidente.evidencias),
            joinedload(Incidente.taller),
            joinedload(Incidente.analisis_ia),
            joinedload(Incidente.cotizaciones).joinedload(Cotizacion.taller)
        )
        .join(VehiculoConductor, Incidente.vehiculoconductor_id == VehiculoConductor.id)
        .filter(
            Incidente.id == incidente_id,
            VehiculoConductor.conductor_id == current_user.conductor.IdUsuario
        )
        .first()
    )

    if not incidente:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Incidente no encontrado o no te pertenece")

    nueva_desc = payload.nueva_descripcion.strip()
    if not nueva_desc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="La descripción no puede estar vacía")

    # Actualizar la descripción en la evidencia existente
    if incidente.evidencias:
        incidente.evidencias[0].descripcion = nueva_desc
        db.commit()

    # Re-ejecutar análisis IA (incluir las fotos ya guardadas)
    fotos_existentes = []
    if incidente.evidencias and incidente.evidencias[0].fotos:
        fotos_str = incidente.evidencias[0].fotos
        fotos_existentes = [f for f in fotos_str.split('|||') if f.startswith('/uploads/')]
    audio_disponible = bool(incidente.evidencias and incidente.evidencias[0].audio)
    resultado_ia = analizar_incidente(
        descripcion=nueva_desc,
        audio_disponible=audio_disponible,
        fotos_urls=fotos_existentes if fotos_existentes else None,
    )

    # Actualizar o crear AnalisisIA
    if incidente.analisis_ia:
        analisis = incidente.analisis_ia
        analisis.Clasificacion = resultado_ia.get("Clasificacion")
        analisis.NivelPrioridad = resultado_ia.get("NivelPrioridad")
        analisis.Resumen = resultado_ia.get("Resumen")
        analisis.informacion_valida = resultado_ia.get("informacion_valida", True)
    else:
        analisis = AnalisisIA(
            incidente_id=incidente_id,
            Clasificacion=resultado_ia.get("Clasificacion"),
            NivelPrioridad=resultado_ia.get("NivelPrioridad"),
            Resumen=resultado_ia.get("Resumen"),
            informacion_valida=resultado_ia.get("informacion_valida", True),
        )
        db.add(analisis)

    db.commit()
    print(f"[AI] Análisis re-ejecutado para incidente #{incidente_id}: valido={resultado_ia.get('informacion_valida')}")

    # Recargar y devolver
    return db.query(Incidente).options(
        joinedload(Incidente.evidencias),
        joinedload(Incidente.taller),
        joinedload(Incidente.analisis_ia),
        joinedload(Incidente.cotizaciones).joinedload(Cotizacion.taller)
    ).filter(Incidente.id == incidente_id).first()


@router.get("/mis-incidentes", response_model=List[IncidenteDetalle])
def mis_incidentes(
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user)
):
    """Devuelve todos los incidentes del conductor actual con evidencias y taller asignado."""
    if not current_user.conductor:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Solo conductores pueden ver sus incidentes")

    # Obtener todos los VehiculoConductor del conductor
    vc_ids = [vc.id for vc in current_user.conductor.vehiculo_conductores]

    if not vc_ids:
        return []

    incidentes = (
        db.query(Incidente)
        .options(
            joinedload(Incidente.evidencias), 
            joinedload(Incidente.taller), 
            joinedload(Incidente.analisis_ia),
            joinedload(Incidente.cotizaciones).joinedload(Cotizacion.taller),
            joinedload(Incidente.pagos)
        )
        .filter(Incidente.vehiculoconductor_id.in_(vc_ids))
        .order_by(Incidente.id.desc())
        .all()
    )

    return incidentes


@router.get("/talleres-disponibles", response_model=List[TallerDisponible])
def talleres_disponibles(
    lat: Optional[float] = Query(None, description="Latitud del conductor"),
    lng: Optional[float] = Query(None, description="Longitud del conductor"),
    incidente_id: Optional[int] = Query(None, description="ID del incidente para recomendación IA"),
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user)
):
    """Lista talleres con capacidad disponible, ordenados por recomendación IA y cercanía si se proveen coordenadas."""
    from sqlalchemy.orm import joinedload as jl
    # Si el conductor es global (sin tenant), mostrar todos los talleres
    if current_user.tenant_id is not None:
        talleres = db.query(Taller).options(jl(Taller.servicios)).filter(Taller.tenant_id == current_user.tenant_id).all()
    else:
        talleres = db.query(Taller).options(jl(Taller.servicios)).all()

    ai_clasificacion = None
    if incidente_id:
        incidente = db.query(Incidente).options(jl(Incidente.analisis_ia)).filter(Incidente.id == incidente_id).first()
        if incidente and incidente.analisis_ia:
            ai_clasificacion = incidente.analisis_ia.Clasificacion

    resultado = []
    for t in talleres:
        cap = t.Cap or 0
        capmax = t.Capmax or 0
        if capmax > 0 and cap >= capmax:
            continue

        distancia = None
        if lat is not None and lng is not None and t.Coordenadas:
            try:
                parts = t.Coordenadas.replace(" ", "").split(",")
                t_lat = float(parts[0])
                t_lng = float(parts[1])
                distancia = _haversine(lat, lng, t_lat, t_lng)
            except (ValueError, IndexError):
                distancia = None

        recomendado = False
        if ai_clasificacion:
            for svc in t.servicios:
                svc_nombre = svc.nombre.lower()
                ai_clase = ai_clasificacion.lower()
                # Verificar palabras clave de coincidencia para hacer el matching más robusto
                if svc_nombre in ai_clase or ai_clase in svc_nombre:
                    recomendado = True
                    break
                # Extra coincidencia por palabras clave
                if "eléctrico" in ai_clase and ("eléctrico" in svc_nombre or "diagnóstico" in svc_nombre):
                    recomendado = True
                    break
                if ("llanta" in ai_clase or "neumático" in ai_clase) and "vulcaniz" in svc_nombre:
                    recomendado = True
                    break
                if ("choque" in ai_clase or "pintura" in ai_clase) and "chapa" in svc_nombre:
                    recomendado = True
                    break
                if ("mecánico" in ai_clase or "motor" in ai_clase) and "mecánica general" in svc_nombre:
                    recomendado = True
                    break

        resultado.append(TallerDisponible(
            Id=t.Id,
            Nombre=t.Nombre,
            Direccion=t.Direccion,
            Coordenadas=t.Coordenadas,
            Cap=cap,
            Capmax=capmax,
            IdUsuario=t.IdUsuario,
            distancia_km=distancia,
            recomendado_ia=recomendado,
            servicios=[ServicioTallerOut(id=s.id, nombre=s.nombre, taller_id=s.taller_id) for s in t.servicios],
        ))

    # Ordenar: primero los recomendados por IA (True antes que False), luego por distancia
    resultado.sort(key=lambda x: (
        0 if x.recomendado_ia else 1,
        x.distancia_km if x.distancia_km is not None else 99999
    ))
    return resultado


# ─── ENDPOINTS DE GESTIÓN DE SERVICIOS DEL TALLER ────────────────────────────

@router.get("/servicios/catalogo")
def catalogo_servicios():
    """Devuelve el catálogo de tipos de servicio disponibles."""
    return [
        "Mecánica General",
        "Auxilio Eléctrico",
        "Vulcanización Móvil",
        "Remolque",
        "Chapa y Pintura",
        "Diagnóstico a Domicilio",
        "Cerrajero Automotriz",
        "Cambio de Aceite",
    ]


@router.get("/mis-servicios", response_model=List[ServicioTallerOut])
def mis_servicios(
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user)
):
    """Devuelve los servicios configurados por el taller autenticado."""
    taller = get_taller_para_usuario(current_user, db)
    if not taller:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Solo talleres o administradores pueden ver sus servicios")
    servicios = db.query(ServicioTaller).filter(ServicioTaller.taller_id == taller.Id).all()
    return servicios


@router.post("/mis-servicios", response_model=ServicioTallerOut, status_code=201)
def agregar_servicio(
    payload: ServicioTallerCreate,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user)
):
    """Permite al taller agregar un servicio a su perfil."""
    taller = get_taller_para_usuario(current_user, db)
    if not taller:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Solo talleres o administradores pueden gestionar servicios")
    nombre = payload.nombre.strip()
    if not nombre:
        raise HTTPException(status_code=400, detail="El nombre del servicio no puede estar vacío")
    # Evitar duplicados
    existente = db.query(ServicioTaller).filter(
        ServicioTaller.taller_id == taller.Id,
        ServicioTaller.nombre == nombre
    ).first()
    if existente:
        raise HTTPException(status_code=409, detail="Este servicio ya está registrado")
    nuevo = ServicioTaller(nombre=nombre, taller_id=taller.Id)
    db.add(nuevo)
    db.commit()
    db.refresh(nuevo)
    return nuevo


@router.delete("/mis-servicios/{servicio_id}", status_code=204)
def eliminar_servicio(
    servicio_id: int,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user)
):
    """Permite al taller eliminar uno de sus servicios."""
    taller = get_taller_para_usuario(current_user, db)
    if not taller:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Solo talleres o administradores pueden gestionar servicios")
    svc = db.query(ServicioTaller).filter(
        ServicioTaller.id == servicio_id,
        ServicioTaller.taller_id == taller.Id
    ).first()
    if not svc:
        raise HTTPException(status_code=404, detail="Servicio no encontrado")
    db.delete(svc)
    db.commit()
    return None


@router.patch("/{incidente_id}/asignar-taller", response_model=IncidenteDetalle)
def asignar_taller(
    incidente_id: int,
    payload: AsignarTaller,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user)
):
    """Permite al conductor seleccionar un taller para su incidente."""
    if not current_user.conductor:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Solo conductores pueden asignar talleres")

    # Verificar que el incidente pertenece al conductor
    vc_ids = [vc.id for vc in current_user.conductor.vehiculo_conductores]
    incidente = (
        db.query(Incidente)
        .options(joinedload(Incidente.evidencias), joinedload(Incidente.taller), joinedload(Incidente.analisis_ia))
        .filter(Incidente.id == incidente_id, Incidente.vehiculoconductor_id.in_(vc_ids))
        .first()
    )

    if not incidente:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Incidente no encontrado o no te pertenece")

    # Verificar que el taller existe
    taller = db.query(Taller).filter(Taller.Id == payload.taller_id).first()
    if not taller:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Taller no encontrado")

    # Asignar taller y cambiar estado
    incidente.taller_id = payload.taller_id
    incidente.estado = "taller asignado"

    # Incrementar la capacidad usada del taller
    if taller.Cap is not None:
        taller.Cap = (taller.Cap or 0) + 1

    db.commit()
    db.refresh(incidente)

    background_tasks.add_task(
        broadcast_ws_event,
        current_user.tenant_id,
        "talleres",
        {"action": "estado_actualizado", "incidente_id": incidente.id, "estado": incidente.estado}
    )

    return incidente


@router.patch("/{incidente_id}/cancelar", response_model=IncidenteDetalle)
def cancelar_incidente(
    incidente_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user)
):
    """Permite al conductor cancelar una solicitud pendiente (Reportado o Asignado)."""
    if not current_user.conductor:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Solo conductores pueden cancelar incidentes")

    # Verificar que el incidente pertenece al conductor
    vc_ids = [vc.id for vc in current_user.conductor.vehiculo_conductores]
    incidente = (
        db.query(Incidente)
        .options(joinedload(Incidente.evidencias), joinedload(Incidente.taller), joinedload(Incidente.analisis_ia))
        .filter(Incidente.id == incidente_id, Incidente.vehiculoconductor_id.in_(vc_ids))
        .first()
    )

    if not incidente:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Incidente no encontrado o no te pertenece")

    # Solo se puede cancelar si está en estado Reportado o Asignado
    if incidente.estado not in ("pendiente", "taller asignado"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"No se puede cancelar un incidente en estado '{incidente.estado}'. Solo se permiten cancelaciones en estado Reportado o Asignado."
        )

    # Si tenía taller asignado, liberar la capacidad
    if incidente.taller_id:
        taller = db.query(Taller).filter(Taller.Id == incidente.taller_id).first()
        if taller and taller.Cap is not None and taller.Cap > 0:
            taller.Cap = taller.Cap - 1

    incidente.estado = "cancelado"
    db.commit()
    db.refresh(incidente)

    background_tasks.add_task(
        broadcast_ws_event,
        current_user.tenant_id,
        "talleres",
        {"action": "estado_actualizado", "incidente_id": incidente.id, "estado": incidente.estado}
    )

    return incidente

@router.post("/{incidente_id}/solicitar-cotizacion", response_model=CotizacionOut)
def solicitar_cotizacion(
    incidente_id: int,
    payload: CotizacionCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user)
):
    """El conductor solicita una cotización a un taller específico."""
    if not current_user.conductor:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Solo conductores pueden solicitar cotizaciones")

    # Verificar incidente
    # Verificar incidente usando JOIN explícito con VehiculoConductor
    incidente = db.query(Incidente)\
        .join(VehiculoConductor, Incidente.vehiculoconductor_id == VehiculoConductor.id)\
        .filter(
            Incidente.id == incidente_id,
            VehiculoConductor.conductor_id == current_user.conductor.IdUsuario
        ).first()
    if not incidente:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Incidente no encontrado")

    # Verificar si ya existe una cotización de este taller para este incidente
    existente = db.query(Cotizacion).filter(Cotizacion.incidente_id == incidente_id, Cotizacion.taller_id == payload.taller_id).first()
    if existente:
        return existente

    nueva_cotizacion = Cotizacion(
        incidente_id=incidente_id,
        taller_id=payload.taller_id,
        estado="Solicitada",
        fecha_creacion=datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        tenant_id=current_user.tenant_id
    )
    db.add(nueva_cotizacion)
    db.commit()
    db.refresh(nueva_cotizacion)

    background_tasks.add_task(
        broadcast_ws_event,
        current_user.tenant_id,
        "talleres",
        {"action": "nueva_solicitud_cotizacion", "incidente_id": incidente_id, "taller_id": payload.taller_id}
    )

    try:
        from src.shared.notificacion_util import crear_notificacion
        taller = db.query(Taller).filter(Taller.Id == payload.taller_id).first()
        if taller and taller.IdUsuario:
            crear_notificacion(
                db,
                taller.IdUsuario,
                "Solicitud de Cotización Directa",
                f"El conductor {current_user.Nombre or 'Conductor'} te ha solicitado una cotización para el incidente #{incidente_id}."
            , background_tasks=background_tasks)
            
        if current_user.tenant_id:
            from src.modules.saas.models import Tenant
            tenant = db.query(Tenant).filter(Tenant.Id == current_user.tenant_id).first()
            if tenant and tenant.IdUsuario:
                crear_notificacion(
                    db,
                    tenant.IdUsuario,
                    "Solicitud de Cotización Directa",
                    f"El conductor {current_user.Nombre or 'Conductor'} ha solicitado una cotización al taller {taller.Nombre if taller else 'desconocido'}."
                , background_tasks=background_tasks)

        # Enviar también un mensaje de chat automático al dueño del taller
        if taller and taller.IdUsuario:
            from src.modules.operations.models import MensajeChat
            mensaje_auto = MensajeChat(
                contenido=f"Hola, he solicitado una cotización para mi incidente #{incidente_id}. ¿Podrías revisarlo y enviarme una oferta?",
                fecha=datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                usuario_id=current_user.Id,
                destinatario_id=taller.IdUsuario,
                incidente_id=None
            )
            db.add(mensaje_auto)
            db.commit()

            # Emitir evento WS para el chat personal
            background_tasks.add_task(
                broadcast_ws_event,
                current_user.tenant_id,
                f"user_{taller.IdUsuario}",
                {"action": "nuevo_mensaje", "remitente_id": current_user.Id}
            )
    except Exception as e:
        print(f"[Notificación] Error al notificar solicitud de cotización: {e}")

    return nueva_cotizacion

@router.post("/{incidente_id}/ofrecer-cotizacion", response_model=CotizacionOut)
def ofrecer_cotizacion(
    incidente_id: int,
    payload: CotizacionOfrecer,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user)
):
    """El taller ofrece un monto por un incidente."""
    taller = get_taller_para_usuario(current_user, db)
    if not taller:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Solo un taller o administrador puede ofrecer cotizaciones")
    taller_id = taller.Id

    # Buscar si ya había una solicitud o cotización previa
    cotizacion = db.query(Cotizacion).filter(Cotizacion.incidente_id == incidente_id, Cotizacion.taller_id == taller_id).first()

    if not cotizacion:
        cotizacion = Cotizacion(
            incidente_id=incidente_id,
            taller_id=taller_id,
            fecha_creacion=datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            tenant_id=current_user.tenant_id
        )
        db.add(cotizacion)

    cotizacion.monto = payload.monto
    cotizacion.mensaje = payload.mensaje
    cotizacion.estado = "Ofrecida"
    
    db.commit()
    db.refresh(cotizacion)

    # Notificar al conductor sobre la nueva oferta
    try:
        conductor_user_id = cotizacion.incidente.vehiculoconductor.conductor.IdUsuario
        crear_notificacion(
            db,
            conductor_user_id,
            "Nueva Cotización Recibida",
            f"El taller {cotizacion.taller.Nombre} ha enviado una oferta de Bs. {cotizacion.monto} para tu incidente #{incidente_id}."
        , background_tasks=background_tasks)
    except Exception as e_notif:
        print(f"[Notificación] Error al notificar conductor: {e_notif}")

    background_tasks.add_task(
        broadcast_ws_event,
        current_user.tenant_id,
        f"conductor_{conductor_user_id}",
        {"action": "nueva_cotizacion", "incidente_id": incidente_id}
    )

    return cotizacion

@router.post("/{incidente_id}/rechazar-cotizacion")
def rechazar_cotizacion(
    incidente_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user)
):
    """El taller rechaza una solicitud de cotización."""
    taller = get_taller_para_usuario(current_user, db)
    if not taller:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Solo un taller o administrador puede rechazar incidentes")
    taller_id = taller.Id

    # Buscar la cotización solicitada
    cotizacion = db.query(Cotizacion).filter(
        Cotizacion.incidente_id == incidente_id, 
        Cotizacion.taller_id == taller_id,
        Cotizacion.estado == "Solicitada"
    ).first()

    if not cotizacion:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Solicitud de cotización no encontrada o ya procesada")

    cotizacion.estado = "Rechazada"
    db.commit()

    # Notificar al conductor
    try:
        from src.shared.notificacion_util import crear_notificacion
        conductor_user_id = cotizacion.incidente.vehiculoconductor.conductor.IdUsuario
        crear_notificacion(
            db,
            conductor_user_id,
            "Cotización Rechazada",
            f"El taller {cotizacion.taller.Nombre} no está disponible para atender tu incidente #{incidente_id}."
        , background_tasks=background_tasks)
    except Exception as e_notif:
        print(f"[Notificación] Error al notificar conductor de rechazo: {e_notif}")

    if 'conductor_user_id' in locals():
        background_tasks.add_task(
            broadcast_ws_event,
            current_user.tenant_id,
            f"conductor_{conductor_user_id}",
            {"action": "cotizacion_rechazada", "incidente_id": incidente_id}
        )

    return {"detail": "Cotización rechazada exitosamente"}

@router.post("/cotizaciones/{cotizacion_id}/aceptar", response_model=IncidenteDetalle)
def aceptar_cotizacion(
    cotizacion_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user)
):
    """El conductor acepta una cotización, asignando el taller al incidente."""
    if not current_user.conductor:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Solo conductores pueden aceptar cotizaciones")

    cotizacion = db.query(Cotizacion).filter(Cotizacion.id == cotizacion_id).first()
    if not cotizacion:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cotización no encontrada")

    # Verificar que el incidente pertenece al conductor
    incidente = db.query(Incidente)\
        .join(VehiculoConductor, Incidente.vehiculoconductor_id == VehiculoConductor.id)\
        .filter(
            Incidente.id == cotizacion.incidente_id,
            VehiculoConductor.conductor_id == current_user.conductor.IdUsuario
        ).first()
    if not incidente:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="El incidente asociado no te pertenece")

    # Actualizar cotización
    cotizacion.estado = "Aceptada"

    # Rechazar el resto de cotizaciones del incidente
    db.query(Cotizacion).filter(
        Cotizacion.incidente_id == incidente.id, 
        Cotizacion.id != cotizacion_id
    ).update({"estado": "Rechazada"})

    # Asignar taller al incidente
    incidente.taller_id = cotizacion.taller_id
    incidente.estado = "taller asignado"
    incidente.fecha_asignacion = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Incrementar capacidad del taller
    taller = db.query(Taller).filter(Taller.Id == cotizacion.taller_id).first()
    if taller and taller.Cap is not None:
        taller.Cap = (taller.Cap or 0) + 1

    db.commit()
    db.refresh(incidente)
    
    # Notificar al taller que su cotización fue aceptada
    try:
        taller_user_id = cotizacion.taller.IdUsuario
        crear_notificacion(
            db,
            taller_user_id,
            "Cotización Aceptada",
            f"¡Felicidades! Tu oferta para el incidente #{incidente.id} ha sido aceptada. El conductor te espera."
        , background_tasks=background_tasks)
    except Exception as e_notif:
        print(f"[Notificación] Error al notificar taller: {e_notif}")

    background_tasks.add_task(
        broadcast_ws_event,
        current_user.tenant_id,
        "talleres",
        {"action": "estado_actualizado", "incidente_id": incidente.id}
    )

    # Recargar con relaciones para la respuesta
    return db.query(Incidente).options(
        joinedload(Incidente.evidencias),
        joinedload(Incidente.taller),
        joinedload(Incidente.analisis_ia),
        joinedload(Incidente.cotizaciones).joinedload(Cotizacion.taller)
    ).filter(Incidente.id == incidente.id).first()

class EstadoUpdate(BaseModel):
    estado: str

@router.get("/mantenimientos", response_model=List[IncidenteDetalle])
def mantenimientos_taller(
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user)
):
    """Devuelve los incidentes asignados al taller del usuario (sea Taller o Mecanico)."""
    taller = get_taller_para_usuario(current_user, db)
    taller_id = taller.Id if taller else None
    is_mecanico = False
    is_admin = current_user.rol and current_user.rol.Nombre == "Admin Tenant"

    if not taller_id and not is_admin and hasattr(current_user, 'mecanico') and current_user.mecanico:
        taller_id = current_user.mecanico.taller_id
        is_mecanico = True

    if not taller_id and not is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No perteneces a ningún taller ni eres administrador")

    query = db.query(Incidente).options(
        joinedload(Incidente.evidencias), 
        joinedload(Incidente.taller), 
        joinedload(Incidente.analisis_ia),
        joinedload(Incidente.vehiculoconductor).options(
            joinedload(VehiculoConductor.conductor).joinedload(Conductor.usuario),
            joinedload(VehiculoConductor.vehiculo)
        ),
        joinedload(Incidente.cotizaciones).joinedload(Cotizacion.taller),
        joinedload(Incidente.mecanicos),
        joinedload(Incidente.pagos)
    )

    if is_admin:
        talleres_ids = [t.Id for t in db.query(Taller).filter(Taller.tenant_id == current_user.tenant_id).all()]
        query = query.filter(
            or_(
                Incidente.tenant_id == current_user.tenant_id,
                Incidente.taller_id.in_(talleres_ids) if talleres_ids else False
            ),
            Incidente.estado.in_(["taller asignado", "en camino", "en reparacion", "resuelto", "finalizado"])
        )
    else:
        query = query.filter(
            Incidente.taller_id == taller_id,
            Incidente.estado.in_(["taller asignado", "en camino", "en reparacion", "resuelto", "finalizado"])
        )

    # Si es mecánico, solo ver los que le fueron asignados
    if is_mecanico and hasattr(current_user, 'mecanico') and current_user.mecanico:
        query = query.filter(Incidente.mecanicos.any(Mecanico.id == current_user.mecanico.id))


    incidentes = query.order_by(Incidente.id.desc()).all()
    return incidentes

@router.post("/{incidente_id}/asignar-mecanicos", response_model=IncidenteDetalle)
def asignar_mecanicos_incidente(
    incidente_id: int,
    payload: AsignarMecanicos,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user)
):
    """Asigna múltiples mecánicos a un incidente. Exclusivo para Taller."""
    taller = get_taller_para_usuario(current_user, db)
    if not taller:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Solo un taller o administrador puede agregar mecánicos")
    taller_id = taller.Id

    incidente = db.query(Incidente).filter(
        Incidente.id == incidente_id,
        Incidente.taller_id == taller_id
    ).first()

    if not incidente:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Incidente no encontrado o no pertenece a tu taller")

    # Obtener los mecánicos válidos
    mecanicos = db.query(Mecanico).filter(
        Mecanico.id.in_(payload.mecanico_ids),
        Mecanico.taller_id == taller_id
    ).all()

    # Reemplazar la lista de mecánicos asignados
    incidente.mecanicos = mecanicos
    db.commit()
    db.refresh(incidente)

    # Notificar a los mecánicos asignados
    try:
        for m in mecanicos:
            crear_notificacion(
                db,
                m.id, # El id de Mecanico es el IdUsuario
                "Nuevo Trabajo Asignado",
                f"Se te ha asignado al incidente #{incidente.id}. Revisa tus mantenimientos."
            , background_tasks=background_tasks)
    except Exception as e_notif:
        print(f"[Notificación] Error al notificar mecánicos: {e_notif}")

    return db.query(Incidente).options(
        joinedload(Incidente.evidencias),
        joinedload(Incidente.taller),
        joinedload(Incidente.analisis_ia),
        joinedload(Incidente.vehiculoconductor).joinedload(VehiculoConductor.conductor),
        joinedload(Incidente.cotizaciones).joinedload(Cotizacion.taller),
        joinedload(Incidente.mecanicos)
    ).filter(Incidente.id == incidente.id).first()

@router.patch("/{incidente_id}/estado-taller", response_model=IncidenteDetalle)
def actualizar_estado_mantenimiento(
    incidente_id: int,
    payload: EstadoUpdate,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user)
):
    """Actualiza el estado de un incidente (En Camino, Resuelto). Taller y Mecanico."""
    taller = get_taller_para_usuario(current_user, db)
    taller_id = taller.Id if taller else None
    
    if not taller_id and hasattr(current_user, 'mecanico') and current_user.mecanico:
        taller_id = current_user.mecanico.taller_id

    if not taller_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No perteneces a ningún taller")

    incidente = db.query(Incidente).filter(
        Incidente.id == incidente_id,
        Incidente.taller_id == taller_id
    ).first()

    if not incidente:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Incidente no encontrado o no asignado a tu taller")

    if payload.estado not in ["en camino", "finalizado"]:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Estado no válido")

    # Si se marca como Resuelto, liberamos cupo del taller
    if payload.estado == "finalizado" and incidente.estado != "finalizado":
        taller = db.query(Taller).filter(Taller.Id == taller_id).first()
        if taller and taller.Cap is not None and taller.Cap > 0:
            taller.Cap -= 1
            
    incidente.estado = payload.estado
    db.commit()
    db.refresh(incidente)

    # Notificar al conductor sobre el cambio de estado
    try:
        conductor_user_id = incidente.vehiculoconductor.conductor.IdUsuario
        msg = f"Tu vehículo ahora está en estado: {payload.estado}."
        if payload.estado == "finalizado":
            msg = "¡Tu vehículo ha sido reparado! Ya puedes pasar a recogerlo o confirmar el servicio."
            
        crear_notificacion(
            db,
            conductor_user_id,
            f"Actualización de tu Incidente #{incidente.id}",
            msg
        , background_tasks=background_tasks)
    except Exception as e_notif:
        print(f"[Notificación] Error al notificar conductor: {e_notif}")

    return db.query(Incidente).options(
        joinedload(Incidente.evidencias),
        joinedload(Incidente.taller),
        joinedload(Incidente.analisis_ia),
        joinedload(Incidente.vehiculoconductor).joinedload(VehiculoConductor.conductor),
        joinedload(Incidente.cotizaciones).joinedload(Cotizacion.taller),
        joinedload(Incidente.mecanicos)
    ).filter(Incidente.id == incidente.id).first()


# ─── CHAT POR INCIDENTE ─────────────────────────────────────────

def _get_nombre_y_rol(usuario: Usuario):
    """Devuelve (nombre_display, rol) para un usuario."""
    rol_obj = getattr(usuario, 'rol', None)
    rol = rol_obj.Nombre if rol_obj else "Usuario"

    if usuario.conductor:
        nombre = f"{usuario.Nombre or ''} {usuario.Apellidos or ''}".strip() or "Conductor"
        if not rol_obj: rol = "Conductor"
    elif usuario.mecanico:
        nombre = f"{usuario.Nombre or ''} {usuario.Apellidos or ''}".strip() or "Mecánico"
        if not rol_obj: rol = "Mecánico"
    elif usuario.talleres:
        nombre = usuario.talleres[0].Nombre
        if not rol_obj: rol = "Taller"
    elif usuario.administrador:
        nombre = usuario.administrador.Usuario
        if not rol_obj: rol = "Admin Tenant"
    else:
        nombre = usuario.Correo
    return nombre, rol


def _usuario_puede_chatear(db: Session, incidente: Incidente, user: Usuario) -> bool:
    """Verifica si el usuario es participante del incidente (conductor, taller o mecánico asignado)."""
    # Es conductor dueño del incidente
    if user.conductor:
        if db.query(VehiculoConductor).filter(VehiculoConductor.id == incidente.vehiculoconductor_id, VehiculoConductor.conductor_id == user.conductor.IdUsuario).first():
            return True
    # Permitir a cualquier taller participar en el chat (ej. para negociar cotizaciones)
    if user.talleres:
        return True
    # Es un mecánico asignado al incidente
    if user.mecanico:
        for mec in incidente.mecanicos:
            if mec.id == user.mecanico.id:
                return True
    return False


@router.get("/{incidente_id}/chat", response_model=List[MensajeChatOut])
def obtener_chat(
    incidente_id: int,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user)
):
    """Obtiene los mensajes del chat de un incidente."""
    incidente = db.query(Incidente).options(
        joinedload(Incidente.mecanicos)
    ).filter(Incidente.id == incidente_id).first()

    if not incidente:
        raise HTTPException(status_code=404, detail="Incidente no encontrado.")

    if not _usuario_puede_chatear(db, incidente, current_user):
        raise HTTPException(status_code=403, detail="No tienes acceso al chat de este incidente.")

    mensajes = (
        db.query(MensajeChat)
        .options(
            joinedload(MensajeChat.usuario).joinedload(Usuario.conductor),
            joinedload(MensajeChat.usuario).joinedload(Usuario.mecanico),
            joinedload(MensajeChat.usuario).joinedload(Usuario.talleres),
            joinedload(MensajeChat.usuario).joinedload(Usuario.administrador)
        )
        .filter(MensajeChat.incidente_id == incidente_id)
        .order_by(MensajeChat.id.asc())
        .all()
    )

    resultado = []
    for m in mensajes:
        nombre, rol = _get_nombre_y_rol(m.usuario)
        resultado.append(MensajeChatOut(
            id=m.id,
            contenido=m.contenido,
            fecha=m.fecha,
            incidente_id=m.incidente_id,
            usuario_id=m.usuario_id,
            nombre_usuario=nombre,
            rol_usuario=rol,
        ))

    return resultado


@router.post("/{incidente_id}/chat", response_model=MensajeChatOut)
def enviar_mensaje_chat(
    incidente_id: int,
    payload: MensajeChatCreate,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user)
):
    """Envía un mensaje al chat de un incidente."""
    incidente = db.query(Incidente).options(
        joinedload(Incidente.mecanicos),
        joinedload(Incidente.vehiculoconductor).joinedload(VehiculoConductor.conductor),
    ).filter(Incidente.id == incidente_id).first()

    if not incidente:
        raise HTTPException(status_code=404, detail="Incidente no encontrado.")

    if not _usuario_puede_chatear(db, incidente, current_user):
        raise HTTPException(status_code=403, detail="No tienes acceso al chat de este incidente.")

    nombre_remitente, rol_remitente = _get_nombre_y_rol(current_user)

    nuevo_msg = MensajeChat(
        contenido=payload.contenido.strip(),
        fecha=datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        incidente_id=incidente_id,
        usuario_id=current_user.Id,
    )
    db.add(nuevo_msg)
    db.commit()
    db.refresh(nuevo_msg)

    # Notificar a los demás participantes
    participantes_ids = set()
    # Conductor
    if incidente.vehiculoconductor and incidente.vehiculoconductor.conductor:
        participantes_ids.add(incidente.vehiculoconductor.conductor.IdUsuario)
    # Taller asignado
    if incidente.taller_id:
        taller = db.query(Taller).filter(Taller.Id == incidente.taller_id).first()
        if taller:
            participantes_ids.add(taller.IdUsuario)
    # Mecánicos asignados
    for mec in incidente.mecanicos:
        participantes_ids.add(mec.id)
        
    # Otros usuarios que hayan chateado en este incidente (para notificar a talleres negociando)
    historial = db.query(MensajeChat.usuario_id).filter(MensajeChat.incidente_id == incidente_id).distinct().all()
    for (u_id,) in historial:
        participantes_ids.add(u_id)

    # Quitar al remitente
    participantes_ids.discard(current_user.Id)

    for uid in participantes_ids:
        try:
            crear_notificacion(
                db, uid,
                f"Nuevo mensaje - Incidente #{incidente_id}",
                f"{nombre_remitente} ({rol_remitente}): {payload.contenido[:80]}",
                background_tasks=background_tasks
            )
        except Exception:
            pass

    return MensajeChatOut(
        id=nuevo_msg.id,
        contenido=nuevo_msg.contenido,
        fecha=nuevo_msg.fecha,
        incidente_id=nuevo_msg.incidente_id,
        usuario_id=nuevo_msg.usuario_id,
        nombre_usuario=nombre_remitente,
        rol_usuario=rol_remitente,
    )

@router.patch("/{incidente_id}/estado", response_model=IncidenteDetalle)
def actualizar_estado_incidente(
    incidente_id: int,
    payload: ActualizarEstadoIncidente,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user)
):
    """Permite actualizar el estado de un incidente y retransmitir la actualización."""
    incidente = db.query(Incidente).options(joinedload(Incidente.evidencias), joinedload(Incidente.taller), joinedload(Incidente.analisis_ia)).filter(Incidente.id == incidente_id).first()
    if not incidente:
        raise HTTPException(status_code=404, detail="Incidente no encontrado")

    incidente.estado = payload.nuevo_estado
    fecha_actual = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    if payload.nuevo_estado.lower() in ["en camino", "en atención", "en atencion"]:
        if not incidente.fecha_llegada:
            incidente.fecha_llegada = fecha_actual
    elif payload.nuevo_estado.lower() == "resuelto":
        incidente.fecha_finalizacion = fecha_actual

    db.commit()
    db.refresh(incidente)

    # Notificar al conductor
    if incidente.vehiculoconductor and incidente.vehiculoconductor.conductor:
        crear_notificacion(
            db,
            incidente.vehiculoconductor.conductor.IdUsuario,
            "Estado Actualizado",
            f"Tu incidente #{incidente.id} cambió de estado a: {payload.nuevo_estado}"
        , background_tasks=background_tasks)

    # Broadcast via WS a la sala del incidente
    background_tasks.add_task(
        broadcast_ws_event,
        incidente.tenant_id,
        f"incidente_{incidente.id}",
        {"action": "estado_actualizado", "incidente_id": incidente.id, "estado": incidente.estado, "lat": payload.lat, "lng": payload.lng}
    )
    
    # Broadcast general al tenant para el dashboard
    if incidente.tenant_id is not None:
        background_tasks.add_task(
            broadcast_ws_event,
            incidente.tenant_id,
            "talleres",
            {"action": "estado_actualizado", "incidente_id": incidente.id, "estado": incidente.estado}
        )

    return incidente
