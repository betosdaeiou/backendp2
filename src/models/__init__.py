"""
Registro central de modelos SQLAlchemy.

Para consultas a BD (db.query, db.add, etc.) importar SIEMPRE desde aquí
o desde src.modules.<modulo>.models — nunca desde schemas.

Uso recomendado:
    from src.models import Incidente, Usuario, Taller
"""

from src.modules.iam.models import Permiso, Rol, Usuario, UsuarioTenant
from src.modules.saas.models import PlanSaaS, Suscripcion, Tenant
from src.modules.catalog.models import (
    Administrador,
    Conductor,
    Mecanico,
    ServicioTaller,
    Taller,
    Vehiculo,
    VehiculoConductor,
)
from src.modules.operations.models import (
    AnalisisIA,
    Bitacora,
    Cotizacion,
    Evidencia,
    Incidente,
    MensajeChat,
    Notificacion,
    Pago,
)

__all__ = [
    # iam
    "Permiso",
    "Rol",
    "Usuario",
    "UsuarioTenant",
    # saas
    "Tenant",
    "PlanSaaS",
    "Suscripcion",
    # catalog
    "Taller",
    "ServicioTaller",
    "Administrador",
    "Conductor",
    "Vehiculo",
    "VehiculoConductor",
    "Mecanico",
    # operations
    "Incidente",
    "Evidencia",
    "Cotizacion",
    "Pago",
    "Bitacora",
    "Notificacion",
    "MensajeChat",
    "AnalisisIA",
]
