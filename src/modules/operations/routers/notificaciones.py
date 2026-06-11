from src.core.database import get_db
from src.modules.iam.dependencies import get_current_user

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from datetime import datetime

from src.modules.operations.models import Notificacion
from src.modules.iam.models import Usuario
from src.modules.operations.schemas import NotificacionOut, NotificacionCreate
from src.modules.iam.schemas import FCMTokenUpdate

router = APIRouter(
    prefix="/notificaciones",
    tags=["Notificaciones"]
)

@router.get("/mis-notificaciones", response_model=List[NotificacionOut])
def get_mis_notificaciones(
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user)
):
    """
    Obtiene todas las notificaciones del usuario logueado.
    """
    notificaciones = db.query(Notificacion).filter(Notificacion.usuario_id == current_user.Id).order_by(Notificacion.id.desc()).all()
    return notificaciones

@router.post("/estado/{notificacion_id}", response_model=NotificacionOut)
def marcar_como_leida(
    notificacion_id: int,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user)
):
    """
    Marca una notificación como leída.
    """
    notificacion = db.query(Notificacion).filter(
        Notificacion.id == notificacion_id,
        Notificacion.usuario_id == current_user.Id
    ).first()

    if not notificacion:
        raise HTTPException(status_code=404, detail="Notificación no encontrada")

    notificacion.estado = "Leída"
    db.commit()
    db.refresh(notificacion)
    return notificacion

@router.post("/simular", response_model=NotificacionOut)
def simular_notificacion(
    notificacion: NotificacionCreate,
    usuario_id: int,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    """
    Crea una notificación para un usuario (Simulador de eventos Backend para disparar a un móvil).
    """
    usuario = db.query(Usuario).filter(Usuario.Id == usuario_id).first()
    if not usuario:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")

    fecha_actual = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    nueva_notificacion = Notificacion(
        descripcion=notificacion.descripcion,
        estado=notificacion.estado or "No leída",
        fecha=notificacion.fecha or fecha_actual,
        titulo=notificacion.titulo,
        usuario_id=usuario.Id
    )

    db.add(nueva_notificacion)
    db.commit()
    db.refresh(nueva_notificacion)

    return nueva_notificacion

@router.post("/token")
def update_fcm_token(
    fcm_data: FCMTokenUpdate,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user)
):
    """
    Actualiza el FCM token del dispositivo para notificaciones push.
    """
    current_user.fcm_token = fcm_data.fcm_token
    db.commit()
    return {"message": "FCM token actualizado correctamente"}

