from sqlalchemy import Column, Integer, String, ForeignKey, Table, Text, Boolean, Date
from sqlalchemy.orm import relationship
from src.core.database import Base

incidente_mecanico_table = Table(
    'IncidenteMecanico',
    Base.metadata,
    Column('incidente_id', Integer, ForeignKey('Incidente.id', ondelete="CASCADE"), primary_key=True),
    Column('mecanico_id', Integer, ForeignKey('Mecanico.id', ondelete="CASCADE"), primary_key=True)
)

class Incidente(Base):
    __tablename__ = 'Incidente'

    id = Column(Integer, primary_key=True, autoincrement=True)
    coordenadagps = Column(String(255))
    estado = Column(String(50))
    fecha = Column(String(50))
    fecha_asignacion = Column(String(50), nullable=True)
    fecha_llegada = Column(String(50), nullable=True)
    fecha_finalizacion = Column(String(50), nullable=True)
    vehiculoconductor_id = Column(Integer, ForeignKey('VehiculoConductor.id', ondelete="CASCADE"), nullable=False)
    taller_id = Column(Integer, ForeignKey('Taller.Id', ondelete="SET NULL"), nullable=True)
    tenant_id = Column(Integer, ForeignKey('Tenant.Id', ondelete="CASCADE"), nullable=True)

    vehiculoconductor = relationship("VehiculoConductor", back_populates="incidentes")
    taller = relationship("Taller")
    evidencias = relationship("Evidencia", back_populates="incidente", cascade="all, delete-orphan")
    cotizaciones = relationship("Cotizacion", back_populates="incidente", cascade="all, delete-orphan")
    mecanicos = relationship("Mecanico", secondary=incidente_mecanico_table, back_populates="incidentes_asignados")
    pagos = relationship("Pago", back_populates="incidente", cascade="all, delete-orphan")
    analisis_ia = relationship("AnalisisIA", back_populates="incidente", uselist=False, cascade="all, delete-orphan")


class Evidencia(Base):
    __tablename__ = 'Evidencia'

    id = Column(Integer, primary_key=True, autoincrement=True)
    audio = Column(String(255), nullable=True)
    descripcion = Column(String(500), nullable=True)
    fotos = Column(String(1000), nullable=True)
    incidente_id = Column(Integer, ForeignKey('Incidente.id', ondelete="CASCADE"), nullable=False)

    incidente = relationship("Incidente", back_populates="evidencias")


class Cotizacion(Base):
    __tablename__ = 'Cotizacion'

    id = Column(Integer, primary_key=True, autoincrement=True)
    monto = Column(Integer)
    mensaje = Column(String(500))
    tiempo_estimado = Column(String(100), nullable=True)
    estado = Column(String(50), default="Pendiente")
    fecha_creacion = Column(String(50))
    incidente_id = Column(Integer, ForeignKey('Incidente.id', ondelete="CASCADE"), nullable=False)
    taller_id = Column(Integer, ForeignKey('Taller.Id', ondelete="CASCADE"), nullable=False)
    tenant_id = Column(Integer, ForeignKey('Tenant.Id', ondelete="CASCADE"), nullable=True)

    incidente = relationship("Incidente", back_populates="cotizaciones")
    taller = relationship("Taller")


class Pago(Base):
    __tablename__ = 'Pago'

    id = Column(Integer, primary_key=True, autoincrement=True)
    monto_total = Column(Integer, nullable=False)
    metodo = Column(String(50), nullable=False)
    estado = Column(String(50), default="Pendiente")
    stripe_session_id = Column(String(255), nullable=True)
    fecha = Column(String(50), nullable=False)
    incidente_id = Column(Integer, ForeignKey('Incidente.id', ondelete="CASCADE"), nullable=False)
    tenant_id = Column(Integer, ForeignKey('Tenant.Id', ondelete="CASCADE"), nullable=True)

    incidente = relationship("Incidente", back_populates="pagos")


class Bitacora(Base):
    __tablename__ = 'Bitacora'

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    accion = Column(String(100), nullable=False)
    descripcion = Column(String(500), nullable=True)
    fecha = Column(Date, nullable=False)
    ip = Column(String(50), nullable=True)
    usuario_id = Column(Integer, ForeignKey('Usuario.Id', ondelete="SET NULL"), nullable=True)
    tenant_id = Column(Integer, ForeignKey('Tenant.Id', ondelete="CASCADE"), nullable=True)

    usuario = relationship("Usuario", back_populates="bitacoras")


class Notificacion(Base):
    __tablename__ = 'Notificacion'

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    descripcion = Column(String(500), nullable=False)
    estado = Column(String(50), default="No leída")
    fecha = Column(String(50), nullable=False)
    titulo = Column(String(100), nullable=False)
    usuario_id = Column(Integer, ForeignKey('Usuario.Id', ondelete="CASCADE"), nullable=False)
    tenant_id = Column(Integer, ForeignKey('Tenant.Id', ondelete="CASCADE"), nullable=True)

    usuario = relationship("Usuario", back_populates="notificaciones")


class MensajeChat(Base):
    __tablename__ = 'MensajeChat'

    id = Column(Integer, primary_key=True, autoincrement=True)
    contenido = Column(String(1000), nullable=False)
    fecha = Column(String(50), nullable=False)
    incidente_id = Column(Integer, ForeignKey('Incidente.id', ondelete="CASCADE"), nullable=True)
    usuario_id = Column(Integer, ForeignKey('Usuario.Id', ondelete="CASCADE"), nullable=False)
    destinatario_id = Column(Integer, ForeignKey('Usuario.Id', ondelete="CASCADE"), nullable=True)

    incidente = relationship("Incidente")
    usuario = relationship("Usuario", foreign_keys=[usuario_id])
    destinatario = relationship("Usuario", foreign_keys=[destinatario_id])


class AnalisisIA(Base):
    __tablename__ = 'AnalisisIA'

    id = Column(Integer, primary_key=True, autoincrement=True)
    Clasificacion = Column(String(100), nullable=True)
    NivelPrioridad = Column(String(50), nullable=True)
    Resumen = Column(Text, nullable=True)
    TranscripcionAudio = Column(Text, nullable=True)
    informacion_valida = Column(Boolean, nullable=True, default=True)
    incidente_id = Column(Integer, ForeignKey('Incidente.id', ondelete="CASCADE"), unique=True)

    incidente = relationship("Incidente", back_populates="analisis_ia")
