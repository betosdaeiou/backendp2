from sqlalchemy import Column, Integer, String, ForeignKey, Table, Date
from sqlalchemy.orm import relationship
from src.core.database import Base

rol_permiso_table = Table(
    'Rol_Permiso',
    Base.metadata,
    Column('IdRol', Integer, ForeignKey('Rol.Id'), primary_key=True),
    Column('IdPermiso', Integer, ForeignKey('Permiso.Id'), primary_key=True)
)

class Permiso(Base):
    __tablename__ = 'Permiso'

    Id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    Nombre = Column(String(255), nullable=False)

    roles = relationship("Rol", secondary=rol_permiso_table, back_populates="permisos")


class Rol(Base):
    __tablename__ = 'Rol'

    Id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    Nombre = Column(String(255), nullable=False)

    permisos = relationship("Permiso", secondary=rol_permiso_table, back_populates="roles")


class UsuarioTenant(Base):
    """Relación muchos-a-muchos entre Usuario y Tenant. Contiene el rol del usuario en ese tenant."""
    __tablename__ = 'Usuario_Tenant'

    id = Column(Integer, primary_key=True, autoincrement=True)
    usuario_id = Column(Integer, ForeignKey('Usuario.Id', ondelete="CASCADE"), nullable=False)
    tenant_id = Column(Integer, ForeignKey('Tenant.Id', ondelete="CASCADE"), nullable=False)
    rol_id = Column(Integer, ForeignKey('Rol.Id'), nullable=False)

    usuario = relationship("Usuario", back_populates="tenants")
    tenant = relationship("Tenant", back_populates="usuario_tenants")
    rol = relationship("Rol")


class Usuario(Base):
    __tablename__ = 'Usuario'

    Id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    Correo = Column(String(255), nullable=False, unique=True, index=True)
    Password = Column(String(255), nullable=False)
    Nombre = Column(String(255), nullable=True)
    Apellidos = Column(String(255), nullable=True)
    CI = Column(String(50), nullable=True)
    Fechanac = Column(Date, nullable=True)
    fcm_token = Column(String(255), nullable=True)
    FotoPerfil = Column(String(255), nullable=True)

    tenants = relationship("UsuarioTenant", back_populates="usuario", cascade="all, delete-orphan")
    talleres = relationship("Taller", back_populates="usuario")
    administrador = relationship("Administrador", uselist=False, back_populates="usuario")
    conductor = relationship("Conductor", uselist=False, back_populates="usuario")
    mecanico = relationship("Mecanico", uselist=False, back_populates="usuario")
    bitacoras = relationship("Bitacora", back_populates="usuario")
    notificaciones = relationship("Notificacion", back_populates="usuario", cascade="all, delete-orphan")
