from src.core.database import get_db
from src.modules.iam.dependencies import get_current_user
from src.modules.operations.models import Incidente
from src.modules.catalog.models import Taller
from src.modules.operations.models import Cotizacion, Pago
from src.modules.iam.models import Usuario
from src.modules.operations.schemas import PagoOut
from src.shared.notificacion_util import crear_notificacion

import os
import stripe
from fastapi import APIRouter, Depends, HTTPException, status, Request, BackgroundTasks
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
import datetime


router = APIRouter(
    prefix="/pagos",
    tags=["Pagos y Comisiones"]
)

# Se usará una clave de prueba por defecto si no existe en el entorno
stripe.api_key = os.getenv("STRIPE_SECRET_KEY", "sk_test_51MockTestKeyForDemoAppNoRealMoney123456789")

@router.post("/{incidente_id}/stripe")
def create_stripe_checkout(
    incidente_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user)
):
    """Genera un link de Checkout de Stripe para pagar el incidente (100%)."""
    if not current_user.conductor:
        raise HTTPException(status_code=403, detail="Solo los conductores pueden pagar.")

    # Verificar incidente
    vc_ids = [vc.id for vc in current_user.conductor.vehiculo_conductores]
    incidente = db.query(Incidente).filter(
        Incidente.id == incidente_id, 
        Incidente.vehiculoconductor_id.in_(vc_ids)
    ).first()

    if not incidente:
        raise HTTPException(status_code=404, detail="Incidente no encontrado.")
    
    if incidente.estado not in ["finalizado", "resuelto"]:
        raise HTTPException(status_code=400, detail="El incidente aún no está resuelto.")

    # Obtener monto de la cotización aceptada
    cotizacion = db.query(Cotizacion).filter(
        Cotizacion.incidente_id == incidente.id,
        Cotizacion.estado == "Aceptada"
    ).first()

    if not cotizacion or not cotizacion.monto:
        raise HTTPException(status_code=400, detail="No hay una cotización aceptada con monto válido.")

    monto_total = cotizacion.monto
    
    # Crear sesión de stripe
    backend_url = str(request.base_url).rstrip('/')
    
    try:
        session = stripe.checkout.Session.create(
            payment_method_types=['card'],
            line_items=[{
                'price_data': {
                    'currency': 'usd',
                    'product_data': {
                        'name': f'Servicio de Mantenimiento - Incidente #{incidente_id}',
                        'description': f'Pago por servicio prestado en el taller',
                    },
                    'unit_amount': monto_total * 100, # Stripe usa centavos
                },
                'quantity': 1,
            }],
            mode='payment',
            success_url=f'{backend_url}/pagos/stripe-success?session_id={{CHECKOUT_SESSION_ID}}&incidente_id={incidente_id}',
            cancel_url=f'{backend_url}/pagos/stripe-cancel?incidente_id={incidente_id}',
        )
        
        # Registrar el pago como pendiente en la BD
        nuevo_pago = Pago(
            monto_total=monto_total,
            metodo="Stripe",
            estado="Pendiente",
            stripe_session_id=session.id,
            fecha=datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            incidente_id=incidente_id,
            tenant_id=current_user.tenant_id
        )
        db.add(nuevo_pago)
        db.commit()
        
        return {"checkout_url": session.url}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

from src.broker.manager import manager

async def broadcast_ws_event(tenant_id: int | None, room_id: str, payload: dict):
    """Emite el evento a la sala indicada Y a las salas complementarias (talleres, conductores, mecanicos)."""
    all_rooms = {"talleres", "conductores", "mecanicos", room_id}
    for room in all_rooms:
        if tenant_id is None:
            await manager.broadcast_all_tenants(payload, room)
        else:
            await manager.broadcast(payload, tenant_id, room)

@router.post("/{incidente_id}/directo", response_model=PagoOut)
def pago_directo(
    incidente_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user)
):
    """Registra que el conductor pagó directamente al taller. Queda pendiente de confirmación por el taller."""
    if not current_user.conductor:
        raise HTTPException(status_code=403, detail="Solo los conductores pueden pagar.")

    # Verificar incidente
    vc_ids = [vc.id for vc in current_user.conductor.vehiculo_conductores]
    incidente = db.query(Incidente).filter(
        Incidente.id == incidente_id, 
        Incidente.vehiculoconductor_id.in_(vc_ids)
    ).first()

    if not incidente:
        raise HTTPException(status_code=404, detail="Incidente no encontrado.")
    
    if incidente.estado not in ["finalizado", "resuelto"]:
        raise HTTPException(status_code=400, detail="El incidente aún no está resuelto.")

    cotizacion = db.query(Cotizacion).filter(
        Cotizacion.incidente_id == incidente.id,
        Cotizacion.estado == "Aceptada"
    ).first()

    if not cotizacion or not cotizacion.monto:
        raise HTTPException(status_code=400, detail="Cotización no válida.")

    # Validar si ya hay un pago completado o pendiente
    pago_previo = db.query(Pago).filter(
        Pago.incidente_id == incidente.id,
        Pago.estado.in_(["Completado", "Pendiente Confirmación"])
    ).first()
    if pago_previo:
        if pago_previo.estado == "Completado":
            raise HTTPException(status_code=400, detail="Este servicio ya ha sido pagado.")
        raise HTTPException(status_code=400, detail="Ya existe un pago pendiente de confirmación por el taller.")

    monto_total = cotizacion.monto
    
    nuevo_pago = Pago(
        monto_total=monto_total,
        metodo="Directo",
        estado="Pendiente Confirmación",
        fecha=datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        incidente_id=incidente_id,
        tenant_id=current_user.tenant_id
    )
    db.add(nuevo_pago)
    
    # El incidente se queda en "finalizado" hasta que el taller confirme
    db.commit()
    db.refresh(nuevo_pago)
    
    # Notificar al taller para que confirme la recepción del pago
    try:
        taller_user_id = incidente.taller.IdUsuario
        crear_notificacion(
            db,
            taller_user_id,
            "Confirmar Recepción de Pago",
            f"El conductor indica que realizó el pago directo de Bs. {monto_total} por el incidente #{incidente_id}. Por favor confirma la recepción.",
            background_tasks=background_tasks
        )
    except Exception as e_notif:
        print(f"[Notificación] Error al notificar taller: {e_notif}")

    # Notificar por WebSockets a los talleres
    background_tasks.add_task(
        broadcast_ws_event,
        current_user.tenant_id,
        "talleres",
        {"action": "estado_actualizado", "incidente_id": incidente.id, "estado": incidente.estado}
    )

    return nuevo_pago

@router.post("/{incidente_id}/confirmar-directo", response_model=PagoOut)
def confirmar_pago_directo(
    incidente_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user)
):
    """El taller confirma que recibió el pago en efectivo/transferencia del conductor."""
    # Verificar que el usuario sea Admin Tenant, o el Taller asignado, o el Mecánico asignado
    incidente = db.query(Incidente).filter(Incidente.id == incidente_id).first()
    if not incidente:
        raise HTTPException(status_code=404, detail="Incidente no encontrado.")

    is_authorized = False

    # 1. Admin Tenant
    if current_user.tenant_id == incidente.tenant_id:
        if current_user.administrador:
            is_authorized = True
        else:
            # Check roles if any
            membresia = next((ut for ut in current_user.tenants if ut.tenant_id == incidente.tenant_id), None)
            if membresia and membresia.rol and membresia.rol.Nombre == "Admin Tenant":
                is_authorized = True

    # 2. Taller
    if not is_authorized and current_user.talleres:
        taller_asignado = next((t for t in current_user.talleres if t.Id == incidente.taller_id), None)
        if taller_asignado:
            is_authorized = True

    # 3. Mecanico
    if not is_authorized and current_user.mecanico:
        es_mecanico_asignado = any(m.id == current_user.Id for m in incidente.mecanicos)
        if es_mecanico_asignado:
            is_authorized = True

    if not is_authorized:
        raise HTTPException(status_code=403, detail="No tienes permiso para confirmar este pago.")

    # Buscar pago pendiente de confirmación
    pago = db.query(Pago).filter(
        Pago.incidente_id == incidente_id,
        Pago.estado == "Pendiente Confirmación",
        Pago.metodo == "Directo"
    ).first()

    if not pago:
        raise HTTPException(status_code=404, detail="No hay un pago pendiente de confirmación para este incidente.")

    # Confirmar el pago
    pago.estado = "Completado"

    # Aplicar comisión: Pago Directo -> Taller cobra 100%, debe 10% a plataforma (descontado al tenant)
    comision = int(pago.monto_total * 0.10)
    from src.modules.saas.models import Tenant
    tenant = db.query(Tenant).filter(Tenant.Id == incidente.tenant_id).first()
    if tenant:
        tenant.balance = (tenant.balance or 0) - comision

    # Marcar incidente como Pagado
    incidente.estado = "pagado"

    db.commit()
    db.refresh(pago)

    # Notificar al conductor que el taller confirmó
    try:
        vc = incidente.vehiculoconductor
        if vc and vc.conductor:
            conductor_user_id = vc.conductor.IdUsuario
            crear_notificacion(
                db,
                conductor_user_id,
                "Pago Confirmado",
                f"El taller ha confirmado la recepción de tu pago de Bs. {pago.monto_total} por el incidente #{incidente_id}. ¡Servicio finalizado!",
                background_tasks=background_tasks
            )
    except Exception as e_notif:
        print(f"[Notificación] Error al notificar conductor: {e_notif}")

    # Notificar por WebSockets al conductor
    background_tasks.add_task(
        broadcast_ws_event,
        current_user.tenant_id,
        "conductores",
        {"action": "estado_actualizado", "incidente_id": incidente.id, "estado": incidente.estado}
    )

    return pago

@router.post("/success", response_model=PagoOut)
def confirmar_pago_stripe(
    session_id: str,
    incidente_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user)
):
    """El frontend llama aquí después del redireccionamiento exitoso de Stripe."""
    pago = db.query(Pago).filter(
        Pago.stripe_session_id == session_id,
        Pago.incidente_id == incidente_id
    ).first()

    if not pago:
        raise HTTPException(status_code=404, detail="Pago no encontrado.")
        
    if pago.estado == "Completado":
        return pago # Ya estaba verificado

    try:
        # Verificar con la API de Stripe
        session = stripe.checkout.Session.retrieve(session_id)
        if session.payment_status == 'paid':
            pago.estado = "Completado"
            
            # Lógica de Comisión
            # Pago Stripe -> Plataforma cobra 100%, se queda 10%, debe 90% a tenant -> balance positivo para tenant
            monto_taller = int(pago.monto_total * 0.90)
            
            incidente = db.query(Incidente).filter(Incidente.id == pago.incidente_id).first()
            if incidente:
                incidente.estado = "pagado"
                from src.modules.saas.models import Tenant
                tenant = db.query(Tenant).filter(Tenant.Id == incidente.tenant_id).first()
                if tenant:
                    tenant.balance = (tenant.balance or 0) + monto_taller

            db.commit()
            db.refresh(pago)

            # Notificar al taller sobre el pago por Stripe
            try:
                taller_user_id = incidente.taller.IdUsuario
                crear_notificacion(
                    db,
                    taller_user_id,
                    "Pago Recibido (Stripe)",
                    f"Se ha procesado exitosamente el pago de Bs. {pago.monto_total} por el incidente #{pago.incidente_id}.",
                    background_tasks=background_tasks
                )
            except Exception as e_notif:
                print(f"[Notificación] Error al notificar taller: {e_notif}")

            # Notificar por WebSockets a los talleres
            background_tasks.add_task(
                broadcast_ws_event,
                current_user.tenant_id,
                "talleres",
                {"action": "estado_actualizado", "incidente_id": incidente.id, "estado": incidente.estado}
            )

            return pago
        else:
            raise HTTPException(status_code=400, detail="El pago en Stripe no fue completado exitosamente.")
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/stripe-success", response_class=HTMLResponse)
def stripe_success_page(
    session_id: str,
    incidente_id: int,
    db: Session = Depends(get_db)
):
    """Página de éxito mostrada directamente por el backend."""
    # Intentar confirmar el pago automáticamente al entrar a la página
    pago = db.query(Pago).filter(
        Pago.stripe_session_id == session_id,
        Pago.incidente_id == incidente_id
    ).first()

    status_msg = "Procesando..."
    if pago:
        try:
            session = stripe.checkout.Session.retrieve(session_id)
            if session.payment_status == 'paid':
                pago.estado = "Completado"
                incidente = db.query(Incidente).filter(Incidente.id == pago.incidente_id).first()
                if incidente:
                    incidente.estado = "pagado"
                    from src.modules.saas.models import Tenant
                    tenant = db.query(Tenant).filter(Tenant.Id == incidente.tenant_id).first()
                    if tenant:
                        monto_taller = int(pago.monto_total * 0.90)
                        tenant.balance = (tenant.balance or 0) + monto_taller
                db.commit()
                status_msg = "¡Pago Completado Exitosamente!"
            else:
                status_msg = "El pago no fue completado."
        except:
            status_msg = "Error al verificar el pago."
    else:
        status_msg = "Pago no encontrado."

    return f"""
    <html>
        <head>
            <title>Pago Exitoso</title>
            <meta name="viewport" content="width=device-width, initial-scale=1">
            <style>
                body {{ font-family: sans-serif; display: flex; justify-content: center; align-items: center; height: 100vh; margin: 0; background-color: #0F1523; color: white; }}
                .card {{ background: #1A2236; padding: 40px; border-radius: 20px; text-align: center; box-shadow: 0 10px 30px rgba(0,0,0,0.5); max-width: 90%; }}
                .icon {{ font-size: 60px; color: #4CAF50; margin-bottom: 20px; }}
                h1 {{ margin: 0 0 10px 0; color: #4CAF50; }}
                p {{ color: #ccc; line-height: 1.5; }}
                .btn {{ display: inline-block; margin-top: 30px; padding: 12px 24px; background: #42A5F5; color: white; text-decoration: none; border-radius: 10px; font-weight: bold; }}
            </style>
        </head>
        <body>
            <div class="card">
                <div class="icon">✓</div>
                <h1>{status_msg}</h1>
                <p>Tu pago ha sido procesado. Ya puedes cerrar esta ventana y volver a la aplicación de conductores.</p>
                <a href="#" onclick="window.close();" class="btn">Volver a la App</a>
            </div>
        </body>
    </html>
    """

@router.get("/stripe-cancel", response_class=HTMLResponse)
def stripe_cancel_page():
    return """
    <html>
        <head>
            <title>Pago Cancelado</title>
            <meta name="viewport" content="width=device-width, initial-scale=1">
            <style>
                body { font-family: sans-serif; display: flex; justify-content: center; align-items: center; height: 100vh; margin: 0; background-color: #0F1523; color: white; }
                .card { background: #1A2236; padding: 40px; border-radius: 20px; text-align: center; box-shadow: 0 10px 30px rgba(0,0,0,0.5); max-width: 90%; }
                .icon { font-size: 60px; color: #E53935; margin-bottom: 20px; }
                h1 { margin: 0 0 10px 0; color: #E53935; }
                p { color: #ccc; line-height: 1.5; }
                .btn { display: inline-block; margin-top: 30px; padding: 12px 24px; background: #78909C; color: white; text-decoration: none; border-radius: 10px; font-weight: bold; }
            </style>
        </head>
        <body>
            <div class="card">
                <div class="icon">✕</div>
                <h1>Pago Cancelado</h1>
                <p>Has cancelado el proceso de pago. Puedes volver a intentarlo desde la aplicación.</p>
                <a href="#" onclick="window.close();" class="btn">Cerrar</a>
            </div>
        </body>
    </html>
    """
