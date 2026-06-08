from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime


# ── Tenant ────────────────────────────────────────────────────────────────────

class TenantBase(BaseModel):
    Nombre: str
    Dominio: Optional[str] = None
    LogoUrl: Optional[str] = None

class TenantCreate(TenantBase):
    pass

class TenantUpdate(BaseModel):
    Nombre: Optional[str] = None
    SuscripcionActiva: Optional[int] = None
    Dominio: Optional[str] = None
    LogoUrl: Optional[str] = None

class TenantOut(TenantBase):
    Id: int
    SuscripcionActiva: int = 1
    CreatedAt: Optional[datetime] = None

    class Config:
        from_attributes = True


# ── PlanSaaS ──────────────────────────────────────────────────────────────────

class PlanSaaSBase(BaseModel):
    Nombre: str
    PrecioMensual: int = 0
    MaxUsuarios: int = 10
    MaxIncidentes: int = 100
    Descripcion: Optional[str] = None

class PlanSaaSCreate(PlanSaaSBase):
    pass

class PlanSaaSOut(PlanSaaSBase):
    Id: int
    Activo: bool = True

    class Config:
        from_attributes = True


# ── Suscripcion ───────────────────────────────────────────────────────────────

class SuscripcionBase(BaseModel):
    tenant_id: int
    plan_id: int

class SuscripcionCreate(SuscripcionBase):
    pass

class SuscripcionOut(SuscripcionBase):
    Id: int
    FechaInicio: Optional[datetime] = None
    FechaFin: Optional[datetime] = None
    Estado: str = "Activa"
    StripeSubscriptionId: Optional[str] = None

    class Config:
        from_attributes = True

# ── Registro ──────────────────────────────────────────────────────────────────

class TenantRegistrationRequest(BaseModel):
    admin_correo: str
    admin_password: str
    admin_nombre: Optional[str] = None
    admin_apellidos: Optional[str] = None
    tenant_nombre: str
    plan_id: int
    extra_usuarios: Optional[int] = 0
    extra_incidentes: Optional[int] = 0

class CheckoutSessionResponse(BaseModel):
    checkout_url: Optional[str] = None
    message: str
    tenant_id: int

class UpgradeCheckoutRequest(BaseModel):
    plan_id: int

class PortalSessionResponse(BaseModel):
    portal_url: str
