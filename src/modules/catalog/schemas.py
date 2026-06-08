from pydantic import BaseModel
from datetime import date
from typing import Optional, List

# ── Conductor ─────────────────────────────────────────────────────────────────

class ConductorBase(BaseModel):
    pass

class ConductorRegistro(BaseModel):
    Correo: str
    Password: str
    Nombre: str
    Apellidos: str
    CI: str
    Fechanac: date

class ConductorOut(ConductorBase):
    IdUsuario: int
    class Config:
        from_attributes = True

# ── Taller ────────────────────────────────────────────────────────────────────

class TallerBase(BaseModel):
    Nombre: str
    Direccion: str
    Coordenadas: Optional[str] = None
    Cap: Optional[int] = 0
    Capmax: Optional[int] = 10

class TallerRegistro(TallerBase):
    Correo: str
    Password: str
    tenant_id: int

class TallerCreateInternal(TallerBase):
    Correo: str
    Password: str

class TallerOut(TallerBase):
    Id: int
    balance: int
    IdUsuario: Optional[int] = None
    class Config:
        from_attributes = True

class ServicioTallerBase(BaseModel):
    nombre: str

class ServicioTallerCreate(ServicioTallerBase):
    pass

class ServicioTallerOut(ServicioTallerBase):
    id: int
    taller_id: int
    class Config:
        from_attributes = True

class TallerDisponible(TallerOut):
    distancia_km: Optional[float] = None
    recomendado_ia: bool = False
    servicios: List[ServicioTallerOut] = []

# ── Vehiculo ──────────────────────────────────────────────────────────────────

class VehiculoBase(BaseModel):
    Marca: Optional[str] = None
    Modelo: Optional[str] = None
    Placa: Optional[str] = None
    Poliza: Optional[str] = None
    Categoria: Optional[str] = None
    Año: Optional[int] = None

class VehiculoCreate(VehiculoBase):
    pass

class Vehiculo(VehiculoBase):
    Id: int
    class Config:
        from_attributes = True

# ── Mecanico ──────────────────────────────────────────────────────────────────

class MecanicoBase(BaseModel):
    estado: Optional[str] = "Disponible"

class MecanicoRegistro(MecanicoBase):
    correo: str
    password: str
    nombre: str
    apellidos: str
    ci: str
    extci: Optional[str] = None
    fechanac: Optional[date] = None

class MecanicoUpdate(BaseModel):
    estado: Optional[str] = None

class MecanicoOut(MecanicoBase):
    id: int
    taller_id: Optional[int] = None
    class Config:
        from_attributes = True

# ── Perfil (Combinado) ────────────────────────────────────────────────────────

class AdminProfileData(BaseModel):
    Usuario: str
    class Config:
        from_attributes = True

class TallerProfileData(BaseModel):
    Id: int
    Nombre: str
    Direccion: str
    Coordenadas: Optional[str] = None
    Cap: int
    Capmax: int
    balance: int
    class Config:
        from_attributes = True

class ConductorProfileData(BaseModel):
    pass
    class Config:
        from_attributes = True

class MecanicoProfileData(BaseModel):
    id: int
    estado: str
    class Config:
        from_attributes = True

class ProfileOut(BaseModel):
    Id: int
    Correo: str
    Nombre: Optional[str] = None
    Apellidos: Optional[str] = None
    CI: Optional[str] = None
    Fechanac: Optional[date] = None
    rol_nombre: Optional[str] = None
    FotoPerfil: Optional[str] = None
    administrador: Optional[AdminProfileData] = None
    taller: Optional[TallerProfileData] = None
    conductor: Optional[ConductorProfileData] = None
    mecanico: Optional[MecanicoProfileData] = None
    tenant_nombre: Optional[str] = None
    class Config:
        from_attributes = True

class ProfileUpdate(BaseModel):
    Correo: Optional[str] = None
    Password: Optional[str] = None
    Nombre: Optional[str] = None
    Apellidos: Optional[str] = None
    CI: Optional[str] = None
    Fechanac: Optional[date] = None
    admin_usuario: Optional[str] = None
    taller_nombre: Optional[str] = None
    taller_direccion: Optional[str] = None
    taller_coordenadas: Optional[str] = None
    taller_cap: Optional[int] = None
    taller_capmax: Optional[int] = None
    mecanico_estado: Optional[str] = None

class UbicacionUpdate(BaseModel):
    Coordenadas: str
    Direccion: Optional[str] = None

class PasswordChange(BaseModel):
    contrasena_actual: str
    nueva_contrasena: str
