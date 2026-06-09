from pydantic import BaseModel
from typing import List, Optional
from datetime import date
from src.modules.catalog.schemas import MecanicoOut, TallerOut, ConductorOut, Vehiculo

# ── Evidencia ─────────────────────────────────────────────────────────────────

class EvidenciaBase(BaseModel):
    audio: Optional[str] = None
    descripcion: Optional[str] = None
    fotos: Optional[str] = None

class EvidenciaCreate(EvidenciaBase):
    pass

class EvidenciaOut(EvidenciaBase):
    id: int
    incidente_id: int
    class Config:
        from_attributes = True

# ── Analisis IA ───────────────────────────────────────────────────────────────

class AnalisisIAEnIncidente(BaseModel):
    Clasificacion: Optional[str] = None
    NivelPrioridad: Optional[str] = None
    Resumen: Optional[str] = None
    informacion_valida: Optional[bool] = True
    class Config:
        from_attributes = True

class ReintentarAnalisisPayload(BaseModel):
    nueva_descripcion: str

# ── Cotizacion ────────────────────────────────────────────────────────────────

class CotizacionBase(BaseModel):
    monto: Optional[int] = None
    mensaje: Optional[str] = None
    tiempo_estimado: Optional[str] = None

class CotizacionCreate(BaseModel):
    taller_id: int

class CotizacionOfrecer(BaseModel):
    monto: int
    mensaje: str
    tiempo_estimado: Optional[str] = None

class CotizacionUpdate(BaseModel):
    estado: str

class CotizacionOut(CotizacionBase):
    id: int
    estado: str
    fecha_creacion: str
    taller_id: int
    incidente_id: int
    taller: Optional[TallerOut] = None
    class Config:
        from_attributes = True

# ── Pago ──────────────────────────────────────────────────────────────────────

class PagoBase(BaseModel):
    monto_total: int
    metodo: str

class PagoOut(PagoBase):
    id: int
    estado: str
    stripe_session_id: Optional[str] = None
    fecha: str
    incidente_id: int
    class Config:
        from_attributes = True

# ── Incidente ─────────────────────────────────────────────────────────────────

class IncidenteBase(BaseModel):
    coordenadagps: str
    vehiculoconductor_id: int

class IncidenteCreate(IncidenteBase):
    descripcion: Optional[str] = None

class EstadoUpdate(BaseModel):
    estado: str

class MecanicosAsignacion(BaseModel):
    mecanico_ids: List[int]

class AsignarMecanicos(BaseModel):
    mecanicos_ids: List[int]

class AsignarTaller(BaseModel):
    taller_id: int

class VehiculoConductorListOut(BaseModel):
    id: int
    conductor: ConductorOut
    vehiculo: Optional[Vehiculo] = None
    class Config:
        from_attributes = True

class IncidenteOut(IncidenteBase):
    id: int
    estado: str
    fecha: str
    taller_id: Optional[int] = None
    evidencias: List[EvidenciaOut] = []
    class Config:
        from_attributes = True

class IncidenteDetalle(IncidenteOut):
    taller: Optional[TallerOut] = None
    vehiculoconductor: Optional[VehiculoConductorListOut] = None
    cotizaciones: List[CotizacionOut] = []
    mecanicos: List[MecanicoOut] = []
    analisis_ia: Optional[AnalisisIAEnIncidente] = None
    pagos: List[PagoOut] = []

Incidente = IncidenteOut

class IncidentePendiente(IncidenteDetalle):
    distancia_km: Optional[float] = None

# ── Bitacora ──────────────────────────────────────────────────────────────────

class BitacoraOut(BaseModel):
    id: int
    accion: str
    descripcion: Optional[str] = None
    fecha: date
    ip: Optional[str] = None
    usuario_id: Optional[int] = None
    usuario_correo: Optional[str] = None
    usuario_rol: Optional[str] = None
    class Config:
        from_attributes = True

# ── Notificacion ──────────────────────────────────────────────────────────────

class NotificacionBase(BaseModel):
    titulo: str
    descripcion: str
    estado: Optional[str] = None
    fecha: Optional[str] = None

class NotificacionCreate(NotificacionBase):
    pass

class NotificacionOut(NotificacionBase):
    id: int
    usuario_id: int
    class Config:
        from_attributes = True

# ── Chat ──────────────────────────────────────────────────────────────────────

class MensajeChatCreate(BaseModel):
    contenido: str

class MensajeChatOut(BaseModel):
    id: int
    contenido: str
    fecha: str
    incidente_id: Optional[int] = None
    destinatario_id: Optional[int] = None
    usuario_id: int
    nombre_usuario: str
    rol_usuario: str
    class Config:
        from_attributes = True

class ChatSummaryOut(BaseModel):
    is_incidente: bool
    incidente_id: Optional[int] = None
    destinatario_id: Optional[int] = None
    titulo: str
    subtitulo: str
    ultimo_mensaje: str
    fecha_ultimo_mensaje: str
    no_leidos: int = 0

class ActualizarEstadoIncidente(BaseModel):
    nuevo_estado: str
    lat: Optional[float] = None
    lng: Optional[float] = None
