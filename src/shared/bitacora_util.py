from datetime import date
from sqlalchemy.orm import Session
from src.modules.operations.models import Bitacora
from src.modules.iam.models import Usuario, UsuarioTenant
from src.core.database import SessionLocal


def registrar_bitacora(
    db: Session,
    usuario_id: int,
    accion: str,
    descripcion: str,
    ip: str = "0.0.0.0",
    tenant_id: int = None
):
    """Registra una entrada en la bitácora de actividades del sistema.
    Si no se pasa tenant_id, intenta obtenerlo del primer UsuarioTenant del usuario."""
    if tenant_id is None:
        membership = db.query(UsuarioTenant).filter(
            UsuarioTenant.usuario_id == usuario_id
        ).first()
        tenant_id = membership.tenant_id if membership else None

    entrada = Bitacora(
        accion=accion,
        descripcion=descripcion,
        fecha=date.today(),
        ip=ip,
        usuario_id=usuario_id,
        tenant_id=tenant_id
    )
    db.add(entrada)
    db.commit()


def registrar_bitacora_background(
    usuario_id: int,
    accion: str,
    descripcion: str,
    ip: str = "0.0.0.0",
    tenant_id: int = None
):
    """Registra una entrada en la bitácora utilizando una nueva sesión (ideal para BackgroundTasks)."""
    db = SessionLocal()
    try:
        registrar_bitacora(db, usuario_id, accion, descripcion, ip, tenant_id)
    finally:
        db.close()
