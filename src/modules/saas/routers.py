from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from typing import List
from datetime import datetime
import os
import stripe

from src.core.database import get_db
from src.modules.iam.dependencies import get_current_user
from src.modules.iam.models import Usuario, Rol, UsuarioTenant
from src.modules.catalog.models import Administrador
from src.modules.saas.models import Tenant, PlanSaaS, Suscripcion
from src.core.security import get_password_hash
from src.modules.saas.schemas import (
    TenantCreate, TenantUpdate, TenantOut,
    PlanSaaSCreate, PlanSaaSOut,
    SuscripcionCreate, SuscripcionOut,
    TenantRegistrationRequest, CheckoutSessionResponse,
    UpgradeCheckoutRequest, PortalSessionResponse
)
from src.modules.saas.dependencies import require_super_admin


router = APIRouter(
    prefix="/saas",
    tags=["SaaS Multi-Tenant"]
)


# ─── TENANTS ──────────────────────────────────────────────────────────────────

@router.get("/tenants", response_model=List[TenantOut])
def listar_tenants(
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(require_super_admin)
):
    """Lista todos los tenants registrados en la plataforma (solo super admin)."""
    return db.query(Tenant).all()


@router.get("/public-tenants", response_model=List[TenantOut])
def listar_tenants_publicos(
    db: Session = Depends(get_db)
):
    """Lista los tenants activos para mostrarlos de forma pública (ej. landing page)."""
    return db.query(Tenant).filter(Tenant.SuscripcionActiva == 1).all()


@router.post("/tenants", response_model=TenantOut, status_code=status.HTTP_201_CREATED)
def crear_tenant(
    payload: TenantCreate,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(require_super_admin)
):
    """Registra un nuevo tenant en la plataforma."""
    tenant = Tenant(
        Nombre=payload.Nombre,
        Dominio=payload.Dominio,
        LogoUrl=payload.LogoUrl,
        SuscripcionActiva=1,
        CreatedAt=datetime.utcnow()
    )
    db.add(tenant)
    db.commit()
    db.refresh(tenant)
    return tenant


@router.put("/tenants/{tenant_id}", response_model=TenantOut)
def actualizar_tenant(
    tenant_id: int,
    payload: TenantUpdate,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(require_super_admin)
):
    """Actualiza los datos de un tenant."""
    tenant = db.query(Tenant).filter(Tenant.Id == tenant_id).first()
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant no encontrado")

    if payload.Nombre is not None:
        tenant.Nombre = payload.Nombre
    if payload.SuscripcionActiva is not None:
        tenant.SuscripcionActiva = payload.SuscripcionActiva
    if payload.Dominio is not None:
        tenant.Dominio = payload.Dominio
    if payload.LogoUrl is not None:
        tenant.LogoUrl = payload.LogoUrl

    db.commit()
    db.refresh(tenant)
    return tenant


@router.delete("/tenants/{tenant_id}", status_code=status.HTTP_204_NO_CONTENT)
def eliminar_tenant(
    tenant_id: int,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(require_super_admin)
):
    """Elimina un tenant y todos sus datos asociados."""
    tenant = db.query(Tenant).filter(Tenant.Id == tenant_id).first()
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant no encontrado")
    db.delete(tenant)
    db.commit()
    return None


# ─── PLANES ───────────────────────────────────────────────────────────────────

@router.get("/planes", response_model=List[PlanSaaSOut])
def listar_planes(db: Session = Depends(get_db)):
    """Lista todos los planes SaaS disponibles (público)."""
    return db.query(PlanSaaS).filter(PlanSaaS.Activo == True, PlanSaaS.Nombre.in_(["Básico", "Pro", "Premium"])).all()


@router.post("/planes", response_model=PlanSaaSOut, status_code=status.HTTP_201_CREATED)
def crear_plan(
    payload: PlanSaaSCreate,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(require_super_admin)
):
    """Crea un nuevo plan SaaS."""
    plan = PlanSaaS(**payload.model_dump())
    db.add(plan)
    db.commit()
    db.refresh(plan)
    return plan


# ─── SUSCRIPCIONES ────────────────────────────────────────────────────────────

@router.get("/suscripciones", response_model=List[SuscripcionOut])
def listar_suscripciones(
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user)
):
    """Lista suscripciones del tenant del usuario, o todas si es super admin."""
    if current_user.tenant_id is None:
        return db.query(Suscripcion).all()
    return db.query(Suscripcion).filter(Suscripcion.tenant_id == current_user.tenant_id).all()


@router.post("/suscripciones", response_model=SuscripcionOut, status_code=status.HTTP_201_CREATED)
def crear_suscripcion(
    payload: SuscripcionCreate,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(require_super_admin)
):
    """Crea una nueva suscripción para un tenant."""
    # Validar tenant y plan
    tenant = db.query(Tenant).filter(Tenant.Id == payload.tenant_id).first()
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant no encontrado")

    plan = db.query(PlanSaaS).filter(PlanSaaS.Id == payload.plan_id).first()
    if not plan:
        raise HTTPException(status_code=404, detail="Plan no encontrado")

    suscripcion = Suscripcion(
        tenant_id=payload.tenant_id,
        plan_id=payload.plan_id,
        FechaInicio=datetime.utcnow(),
        Estado="Activa"
    )
    db.add(suscripcion)

    # Activar el tenant
    tenant.SuscripcionActiva = 1

    db.commit()
    db.refresh(suscripcion)
    return suscripcion

# ─── REGISTRO Y CHECKOUT (STRIPE) ─────────────────────────────────────────────

stripe.api_key = os.getenv("STRIPE_SECRET_KEY")

@router.post("/register-checkout", response_model=CheckoutSessionResponse)
def register_tenant_with_checkout(payload: TenantRegistrationRequest, db: Session = Depends(get_db)):
    """Registra un tenant y genera una sesión de pago en Stripe si el plan lo requiere."""
    # 1. Validar si el correo ya existe
    if db.query(Usuario).filter(Usuario.Correo == payload.admin_correo).first():
        raise HTTPException(status_code=400, detail="El correo ya está registrado")

    # 2. Validar Plan
    plan = db.query(PlanSaaS).filter(PlanSaaS.Id == payload.plan_id, PlanSaaS.Activo == True).first()
    if not plan:
        raise HTTPException(status_code=404, detail="El plan seleccionado no existe o está inactivo")

    # 3. Crear Usuario Administrador de Tenant
    rol_admin_tenant = db.query(Rol).filter(Rol.Nombre == "Admin Tenant").first()
    if not rol_admin_tenant:
        rol_admin_tenant = Rol(Nombre="Admin Tenant")
        db.add(rol_admin_tenant)
        db.commit()

    hashed_pass = get_password_hash(payload.admin_password)
    nuevo_usuario = Usuario(
        Correo=payload.admin_correo,
        Password=hashed_pass,
        Nombre=payload.admin_nombre,
        Apellidos=payload.admin_apellidos
    )
    db.add(nuevo_usuario)
    db.commit()
    db.refresh(nuevo_usuario)

    # 4. Obtener Plan Básico Gratuito por defecto
    plan_basico = db.query(PlanSaaS).filter(PlanSaaS.PrecioMensual == 0, PlanSaaS.Activo == True).first()
    if not plan_basico:
        raise HTTPException(status_code=500, detail="No se encontró un plan básico gratuito configurado")

    # 5. Crear Tenant (activo con plan básico temporalmente/permanentemente)
    nuevo_tenant = Tenant(
        Nombre=payload.tenant_nombre,
        SuscripcionActiva=1
    )
    db.add(nuevo_tenant)
    db.commit()
    db.refresh(nuevo_tenant)

    # Vincular usuario al tenant como Admin Tenant
    membership = UsuarioTenant(usuario_id=nuevo_usuario.Id, tenant_id=nuevo_tenant.Id, rol_id=rol_admin_tenant.Id)
    db.add(membership)
    db.commit()

    # Crear perfil de Administrador asociado
    nuevo_admin = Administrador(IdUsuario=nuevo_usuario.Id, Usuario=payload.admin_nombre or "Admin")
    db.add(nuevo_admin)
    db.commit()

    # Suscribir inicialmente al plan básico gratuito
    suscripcion = Suscripcion(
        tenant_id=nuevo_tenant.Id,
        plan_id=plan_basico.Id,
        FechaInicio=datetime.utcnow(),
        Estado="Activa"
    )
    db.add(suscripcion)
    db.commit()

    frontend_url = os.getenv("FRONTEND_URL", "http://localhost:4200")

    # 6. Si el plan seleccionado es el gratuito, terminamos aquí
    if plan.PrecioMensual == 0 and not payload.extra_usuarios and not payload.extra_incidentes:
        return CheckoutSessionResponse(
            checkout_url=f"{frontend_url}/pagos/success",
            message="Tenant registrado exitosamente con plan gratuito.",
            tenant_id=nuevo_tenant.Id
        )

    # 7. Preparar datos para Stripe Checkout (Upgrade al plan seleccionado)
    try:
        if plan.Nombre == 'Premium' and (payload.extra_usuarios or payload.extra_incidentes):
            # Plan Premium Expandido: Creamos un precio dinámico sumando extras al precio base
            extra_usd = ((payload.extra_usuarios or 0) * 2) + ((payload.extra_incidentes or 0) * 0.05)
            precio_usd = (plan.PrecioMensual / 100.0) + extra_usd
            precio_cents = int(precio_usd * 100)
            
            # Crear un plan específico para este tenant en la base de datos
            plan_dinamico = PlanSaaS(
                Nombre=f"Premium Plus - {payload.tenant_nombre}",
                PrecioMensual=precio_cents,
                MaxUsuarios=plan.MaxUsuarios + (payload.extra_usuarios or 0),
                MaxIncidentes=plan.MaxIncidentes + (payload.extra_incidentes or 0),
                Descripcion=f"Premium con {payload.extra_usuarios or 0} usuarios extra y {payload.extra_incidentes or 0} incidentes extra.",
                StripePriceId=None,
                Activo=True
            )
            db.add(plan_dinamico)
            db.commit()
            db.refresh(plan_dinamico)
            
            plan_to_subscribe_id = plan_dinamico.Id

            line_items = [{
                "price_data": {
                    "currency": "usd",
                    "product_data": {"name": plan_dinamico.Nombre},
                    "unit_amount": precio_cents,
                    "recurring": {"interval": "month"}
                },
                "quantity": 1,
            }]
        else:
            plan_to_subscribe_id = plan.Id
            line_items = [{
                "price_data": {
                    "currency": "usd",
                    "product_data": {
                        "name": f"Plan {plan.Nombre}"
                    },
                    "unit_amount": plan.PrecioMensual,
                    "recurring": {"interval": "month"}
                },
                "quantity": 1,
            }]

        session = stripe.checkout.Session.create(
            payment_method_types=["card"],
            line_items=line_items,
            mode="subscription",
            success_url=f"{frontend_url}/pago-exitoso?session_id={{CHECKOUT_SESSION_ID}}",
            cancel_url=f"{frontend_url}/pago-cancelado",
            customer_email=payload.admin_correo,
            metadata={
                "tenant_id": nuevo_tenant.Id,
                "plan_id": plan_to_subscribe_id
            }
        )

        return CheckoutSessionResponse(
            checkout_url=session.url,
            message="Sesión de pago creada exitosamente.",
            tenant_id=nuevo_tenant.Id
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al conectar con Stripe: {str(e)}")


@router.post("/suscripciones/checkout", response_model=CheckoutSessionResponse)
def upgrade_subscription_checkout(
    payload: UpgradeCheckoutRequest,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user)
):
    """Crea una sesión de Checkout para que el Tenant actual contrate o mejore su plan."""
    if not current_user.tenant_id:
        raise HTTPException(status_code=403, detail="El usuario no pertenece a ningún tenant")

    tenant = db.query(Tenant).filter(Tenant.Id == current_user.tenant_id).first()
    plan = db.query(PlanSaaS).filter(PlanSaaS.Id == payload.plan_id).first()

    if not plan or not plan.Activo:
        raise HTTPException(status_code=404, detail="Plan no disponible")
    if plan.PrecioMensual == 0:
        raise HTTPException(status_code=400, detail="No es posible contratar este plan desde aquí")

    frontend_url = os.getenv("FRONTEND_URL", "http://localhost:4200")

    try:
        session_params = {
            "payment_method_types": ["card"],
            "line_items": [{
                "price_data": {
                    "currency": "usd",
                    "product_data": {
                        "name": f"Plan {plan.Nombre}"
                    },
                    "unit_amount": plan.PrecioMensual,
                    "recurring": {"interval": "month"}
                },
                "quantity": 1
            }],
            "mode": "subscription",
            "success_url": f"{frontend_url}/pagos/success?session_id={{CHECKOUT_SESSION_ID}}&type=saas",
            "cancel_url": f"{frontend_url}/dashboard/saas/mi-suscripcion",
            "metadata": {
                "tenant_id": tenant.Id,
                "plan_id": plan.Id
            }
        }

        # Si ya tiene un cliente en Stripe, se lo pasamos, si no, le pedimos email
        if tenant.StripeCustomerId:
            session_params["customer"] = tenant.StripeCustomerId
        else:
            session_params["customer_email"] = current_user.Correo

        session = stripe.checkout.Session.create(**session_params)

        return CheckoutSessionResponse(
            checkout_url=session.url,
            message="Sesión de checkout creada",
            tenant_id=tenant.Id
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error Stripe: {str(e)}")


@router.post("/suscripciones/confirmar")
def confirmar_suscripcion_sync(
    session_id: str,
    db: Session = Depends(get_db)
):
    """Endpoint sincrónico para confirmar el pago en la BD sin requerir Webhooks de Stripe. Ideal para entornos de prueba."""
    try:
        session = stripe.checkout.Session.retrieve(session_id)
        if session.payment_status == "paid" or session.status == "complete":
            tenant_id = getattr(session.metadata, "tenant_id", None)
            plan_id = getattr(session.metadata, "plan_id", None)
            subscription_id = getattr(session, "subscription", None)

            if tenant_id and plan_id:
                tenant = db.query(Tenant).filter(Tenant.Id == int(tenant_id)).first()
                if tenant:
                    tenant.SuscripcionActiva = 1
                    if session.customer:
                        tenant.StripeCustomerId = session.customer
                    
                    # Desactivar otras
                    db.query(Suscripcion).filter(
                        Suscripcion.tenant_id == tenant.Id, 
                        Suscripcion.Estado == "Activa"
                    ).update({"Estado": "Cancelada"})
                    
                    suscripcion = Suscripcion(
                        tenant_id=tenant.Id,
                        plan_id=int(plan_id),
                        FechaInicio=datetime.utcnow(),
                        Estado="Activa",
                        StripeSubscriptionId=subscription_id
                    )
                    db.add(suscripcion)
                    db.commit()
                    return {"success": True, "message": "Suscripción confirmada"}
        return {"success": False, "message": "El pago no está completado"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/suscripciones/portal", response_model=PortalSessionResponse)
def create_customer_portal(
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user)
):
    """Genera la URL del Stripe Customer Portal para gestionar la suscripción."""
    if not current_user.tenant_id:
        raise HTTPException(status_code=403, detail="El usuario no pertenece a ningún tenant")

    tenant = db.query(Tenant).filter(Tenant.Id == current_user.tenant_id).first()

    if not tenant.StripeCustomerId:
        raise HTTPException(status_code=400, detail="Este tenant no tiene una facturación activa configurada")

    frontend_url = os.getenv("FRONTEND_URL", "http://localhost:4200")

    try:
        session = stripe.billing_portal.Session.create(
            customer=tenant.StripeCustomerId,
            return_url=f"{frontend_url}/dashboard/saas/mi-suscripcion"
        )
        return PortalSessionResponse(portal_url=session.url)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error Stripe: {str(e)}")

@router.post("/webhook", include_in_schema=False)
async def stripe_webhook(request: Request, db: Session = Depends(get_db)):
    """Webhook para procesar eventos de Stripe."""
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")
    webhook_secret = os.getenv("STRIPE_WEBHOOK_SECRET", "")

    try:
        # En desarrollo local sin webhook_secret, parseamos el JSON directamente
        import json
        if not webhook_secret:
            event = stripe.Event.construct_from(json.loads(payload), stripe.api_key)
        else:
            event = stripe.Webhook.construct_event(payload, sig_header, webhook_secret)
    except ValueError as e:
        raise HTTPException(status_code=400, detail="Invalid payload")
    except stripe.error.SignatureVerificationError as e:
        raise HTTPException(status_code=400, detail="Invalid signature")

    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]
        tenant_id = session.get("metadata", {}).get("tenant_id")
        plan_id = session.get("metadata", {}).get("plan_id")
        subscription_id = session.get("subscription")

        if tenant_id and plan_id:
            tenant = db.query(Tenant).filter(Tenant.Id == int(tenant_id)).first()
            if tenant:
                tenant.SuscripcionActiva = 1
                tenant.StripeCustomerId = session.get("customer")
                
                # Desactivar suscripciones anteriores
                db.query(Suscripcion).filter(Suscripcion.tenant_id == tenant.Id, Suscripcion.Estado == "Activa").update({"Estado": "Cancelada"})
                
                suscripcion = Suscripcion(
                    tenant_id=tenant.Id,
                    plan_id=int(plan_id),
                    FechaInicio=datetime.utcnow(),
                    Estado="Activa",
                    StripeSubscriptionId=subscription_id
                )
                db.add(suscripcion)
                db.commit()

    return {"status": "success"}
