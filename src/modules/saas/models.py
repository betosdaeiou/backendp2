from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Boolean, Text
from sqlalchemy.orm import relationship
from src.core.database import Base
from datetime import datetime


class Tenant(Base):
    """Empresa/organización que usa la plataforma. Cada tenant tiene su propio espacio de datos aislado."""
    __tablename__ = 'Tenant'

    Id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    Nombre = Column(String(255), nullable=False)
    SuscripcionActiva = Column(Integer, default=1)  # 1 = Activa, 0 = Inactiva
    Dominio = Column(String(255), nullable=True)
    LogoUrl = Column(String(500), nullable=True)
    StripeCustomerId = Column(String(255), nullable=True)
    CreatedAt = Column(DateTime, default=datetime.utcnow)

    usuario_tenants = relationship("UsuarioTenant", back_populates="tenant", cascade="all, delete-orphan")
    suscripciones = relationship("Suscripcion", back_populates="tenant")


class PlanSaaS(Base):
    """Planes disponibles para suscripción en la plataforma."""
    __tablename__ = 'PlanSaaS'

    Id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    Nombre = Column(String(100), nullable=False)
    PrecioMensual = Column(Integer, nullable=False, default=0)  # En centavos o unidad mínima
    MaxUsuarios = Column(Integer, nullable=False, default=10)
    MaxIncidentes = Column(Integer, nullable=False, default=100)
    Descripcion = Column(Text, nullable=True)
    StripePriceId = Column(String(255), nullable=True)
    Activo = Column(Boolean, default=True)

    suscripciones = relationship("Suscripcion", back_populates="plan")


class Suscripcion(Base):
    """Relación entre un Tenant y un PlanSaaS con fechas de vigencia."""
    __tablename__ = 'Suscripcion'

    Id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    tenant_id = Column(Integer, ForeignKey('Tenant.Id', ondelete="CASCADE"), nullable=False)
    plan_id = Column(Integer, ForeignKey('PlanSaaS.Id', ondelete="CASCADE"), nullable=False)
    FechaInicio = Column(DateTime, nullable=False, default=datetime.utcnow)
    FechaFin = Column(DateTime, nullable=True)
    Estado = Column(String(50), default="Activa")  # Activa, Cancelada, Expirada
    StripeSubscriptionId = Column(String(255), nullable=True)

    tenant = relationship("Tenant", back_populates="suscripciones")
    plan = relationship("PlanSaaS", back_populates="suscripciones")
