import os

with open('src/modules/operations/routers/incidentes.py', 'r', encoding='utf-8') as f:
    content = f.read()

from_schema = 'from src.modules.operations.schemas import ReintentarAnalisisPayload'
to_schema = 'from src.modules.operations.schemas import ReintentarAnalisisPayload, ActualizarEstadoIncidente'
content = content.replace(from_schema, to_schema)

new_endpoint = '''
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
    db.commit()
    db.refresh(incidente)

    # Notificar al conductor
    if incidente.vehiculoconductor and incidente.vehiculoconductor.conductor:
        crear_notificacion(
            db,
            incidente.vehiculoconductor.conductor.IdUsuario,
            "Estado Actualizado",
            f"Tu incidente #{incidente.id} cambió de estado a: {payload.nuevo_estado}"
        )

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
'''

content += new_endpoint

with open('src/modules/operations/routers/incidentes.py', 'w', encoding='utf-8') as f:
    f.write(content)
