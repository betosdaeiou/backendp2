from pydantic import BaseModel
from typing import List, Optional

class Token(BaseModel):
    access_token: str
    token_type: str
    role: Optional[str] = None
    permisos: Optional[List[str]] = []
    tenant_id: Optional[int] = None

class TokenData(BaseModel):
    correo: Optional[str] = None
    tenant_id: Optional[int] = None
    rol_id: Optional[int] = None

class PasswordResetRequest(BaseModel):
    correo: str

class PasswordReset(BaseModel):
    token: str
    nueva_password: str

class MensajeResponse(BaseModel):
    message: str

# ── Permisos ──────────────────────────────────────────────────────────────────

class PermisoBase(BaseModel):
    Nombre: str

class PermisoCreate(PermisoBase):
    pass

class Permiso(PermisoBase):
    Id: int

    class Config:
        from_attributes = True

# ── Roles ─────────────────────────────────────────────────────────────────────

class RolBase(BaseModel):
    Nombre: str

class RolCreate(RolBase):
    pass

class Rol(RolBase):
    Id: int
    permisos: List[Permiso] = []

    class Config:
        from_attributes = True

# ── Tenant Selection (Login en 2 pasos) ──────────────────────────────────────

class TenantOption(BaseModel):
    """Un tenant disponible para el usuario durante la selección."""
    id: int
    nombre: str
    logo: Optional[str] = None
    rol: str

    class Config:
        from_attributes = True

class LoginResponse(BaseModel):
    """Respuesta unificada del login. Si requires_tenant_selection es True,
    el frontend debe mostrar la lista de tenants y llamar a /auth/select-tenant."""
    access_token: Optional[str] = None
    token_type: Optional[str] = None
    role: Optional[str] = None
    permisos: Optional[List[str]] = []
    tenant_id: Optional[int] = None
    requires_tenant_selection: bool = False
    temp_token: Optional[str] = None
    tenants: Optional[List[TenantOption]] = None

class TenantSelectionPayload(BaseModel):
    """Payload para seleccionar un tenant después del login."""
    temp_token: str
    tenant_id: int

# ── Usuarios ──────────────────────────────────────────────────────────────────

class UsuarioCreate(BaseModel):
    Correo: str
    Password: str
    IdRol: int
    tenant_id: Optional[int] = None

class UsuarioUpdate(BaseModel):
    Correo: Optional[str] = None
    Password: Optional[str] = None
    IdRol: Optional[int] = None

class UsuarioTenantInfo(BaseModel):
    tenant_id: int
    tenant_nombre: str
    rol_id: int
    rol_nombre: str

    class Config:
        from_attributes = True

class Usuario(BaseModel):
    Id: int
    Correo: str
    memberships: List[UsuarioTenantInfo] = []
    
    class Config:
        from_attributes = True

class FCMTokenUpdate(BaseModel):
    fcm_token: str
