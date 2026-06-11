from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload
from typing import List
from sqlalchemy import or_, and_

from src.core.database import get_db
from src.modules.iam.models import Usuario
from src.modules.iam.dependencies import get_current_user
from src.modules.operations.models import MensajeChat, Incidente
from src.modules.operations.schemas import ChatSummaryOut, MensajeChatOut, MensajeChatCreate
import datetime
from src.modules.operations.routers.incidentes import _get_nombre_y_rol
from src.shared.notificacion_util import crear_notificacion

router = APIRouter(prefix="/chats", tags=["chats"])

@router.get("/mis-chats", response_model=List[ChatSummaryOut])
def obtener_mis_chats(
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user)
):
    """
    Retorna la lista de todos los chats del usuario (por incidente y personales),
    ordenados por la fecha del último mensaje.
    """
    res = []
    
    # --- 1. Chats de Incidentes ---
    incidentes = []
    if current_user.conductor:
        vc_ids = [vc.id for vc in current_user.conductor.vehiculo_conductores]
        incidentes_cond = db.query(Incidente).filter(Incidente.vehiculoconductor_id.in_(vc_ids)).all()
        incidentes.extend(incidentes_cond)
    if current_user.talleres:
        for t in current_user.talleres:
            incidentes_taller = db.query(Incidente).filter(Incidente.taller_id == t.Id).all()
            incidentes.extend(incidentes_taller)
    if current_user.mecanico:
        incidentes_mec = db.query(Incidente).filter(Incidente.mecanicos.any(id=current_user.mecanico.id)).all()
        incidentes.extend(incidentes_mec)
        
    # Also incidentes where the user has sent a message
    mensajes_incidentes = db.query(MensajeChat.incidente_id).filter(
        MensajeChat.usuario_id == current_user.Id, 
        MensajeChat.incidente_id.isnot(None)
    ).distinct().all()
    inc_ids_chateados = [m[0] for m in mensajes_incidentes if m[0] is not None]
    
    if inc_ids_chateados:
        incidentes_extras = db.query(Incidente).filter(Incidente.id.in_(inc_ids_chateados)).all()
        for ie in incidentes_extras:
            if not any(i.id == ie.id for i in incidentes):
                incidentes.append(ie)
                
    for inc in incidentes:
        ultimo_msg = db.query(MensajeChat).filter(MensajeChat.incidente_id == inc.id).order_by(MensajeChat.id.desc()).first()
        if ultimo_msg:
            res.append(ChatSummaryOut(
                is_incidente=True,
                incidente_id=inc.id,
                destinatario_id=None,
                titulo=f"Incidente #{inc.id}",
                subtitulo=inc.estado,
                ultimo_mensaje=ultimo_msg.contenido,
                fecha_ultimo_mensaje=ultimo_msg.fecha,
                no_leidos=0
            ))
            
    # --- 2. Chats Personales ---
    mensajes_personales = db.query(MensajeChat).filter(
        MensajeChat.incidente_id.is_(None),
        or_(
            MensajeChat.usuario_id == current_user.Id,
            MensajeChat.destinatario_id == current_user.Id
        )
    ).order_by(MensajeChat.id.desc()).all()
    
    dict_personales = {}
    for m in mensajes_personales:
        otro_id = m.destinatario_id if m.usuario_id == current_user.Id else m.usuario_id
        if otro_id not in dict_personales:
            dict_personales[otro_id] = m

    for otro_id, ultimo_msg in dict_personales.items():
        otro_user = db.query(Usuario).filter(Usuario.Id == otro_id).first()
        nombre, rol = _get_nombre_y_rol(otro_user) if otro_user else ("Usuario Desconocido", "")
        res.append(ChatSummaryOut(
            is_incidente=False,
            incidente_id=None,
            destinatario_id=otro_id,
            titulo=nombre,
            subtitulo=rol,
            ultimo_mensaje=ultimo_msg.contenido,
            fecha_ultimo_mensaje=ultimo_msg.fecha,
            no_leidos=0
        ))
        
    res.sort(key=lambda x: x.fecha_ultimo_mensaje, reverse=True)
    return res

@router.get("/personal/{destinatario_id}", response_model=List[MensajeChatOut])
def obtener_chat_personal(
    destinatario_id: int,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user)
):
    mensajes = (
        db.query(MensajeChat)
        .options(
            joinedload(MensajeChat.usuario).joinedload(Usuario.conductor),
            joinedload(MensajeChat.usuario).joinedload(Usuario.mecanico),
            joinedload(MensajeChat.usuario).joinedload(Usuario.talleres),
            joinedload(MensajeChat.usuario).joinedload(Usuario.administrador)
        )
        .filter(
            MensajeChat.incidente_id.is_(None),
            or_(
                and_(MensajeChat.usuario_id == current_user.Id, MensajeChat.destinatario_id == destinatario_id),
                and_(MensajeChat.usuario_id == destinatario_id, MensajeChat.destinatario_id == current_user.Id)
            )
        )
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
            destinatario_id=m.destinatario_id,
            usuario_id=m.usuario_id,
            nombre_usuario=nombre,
            rol_usuario=rol,
        ))

    return resultado

@router.post("/personal/{destinatario_id}", response_model=MensajeChatOut)
def enviar_mensaje_personal(
    destinatario_id: int,
    payload: MensajeChatCreate,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user)
):
    destinatario = db.query(Usuario).filter(Usuario.Id == destinatario_id).first()
    if not destinatario:
        raise HTTPException(status_code=404, detail="Usuario destinatario no encontrado.")

    nuevo_msg = MensajeChat(
        contenido=payload.contenido.strip(),
        fecha=datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        incidente_id=None,
        usuario_id=current_user.Id,
        destinatario_id=destinatario_id
    )
    db.add(nuevo_msg)
    db.commit()
    db.refresh(nuevo_msg)
    
    nombre_remitente, rol_remitente = _get_nombre_y_rol(current_user)
    
    try:
        crear_notificacion(
            db, destinatario_id,
            "Nuevo mensaje personal",
            f"{nombre_remitente}: {payload.contenido[:80]}"
        , background_tasks=background_tasks)
    except Exception:
        pass

    return MensajeChatOut(
        id=nuevo_msg.id,
        contenido=nuevo_msg.contenido,
        fecha=nuevo_msg.fecha,
        incidente_id=nuevo_msg.incidente_id,
        destinatario_id=nuevo_msg.destinatario_id,
        usuario_id=nuevo_msg.usuario_id,
        nombre_usuario=nombre_remitente,
        rol_usuario=rol_remitente,
    )
