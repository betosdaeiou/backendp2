from sqlalchemy import Column, Integer, String, ForeignKey, Date, BigInteger
from sqlalchemy.orm import relationship
from src.core.database import Base

class Taller(Base):
    __tablename__ = 'Taller'
    
    Id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    Nombre = Column(String(255), nullable=False)
    Direccion = Column(String(255), nullable=False)
    Coordenadas = Column(String(255))
    Cap = Column(Integer, default=0)
    Capmax = Column(Integer, default=10)
    IdUsuario = Column(Integer, ForeignKey('Usuario.Id'), nullable=True)
    tenant_id = Column(Integer, ForeignKey('Tenant.Id', ondelete="CASCADE"), nullable=True)

    usuario = relationship("Usuario", back_populates="talleres")
    mecanicos = relationship("Mecanico", back_populates="taller")
    servicios = relationship("ServicioTaller", back_populates="taller", cascade="all, delete-orphan")


class ServicioTaller(Base):
    __tablename__ = 'ServicioTaller'

    id = Column(Integer, primary_key=True, autoincrement=True)
    nombre = Column(String(100), nullable=False)
    taller_id = Column(Integer, ForeignKey('Taller.Id', ondelete='CASCADE'), nullable=False)

    taller = relationship("Taller", back_populates="servicios")


class Administrador(Base):
    __tablename__ = 'Administrador'
    
    IdUsuario = Column(Integer, ForeignKey('Usuario.Id'), primary_key=True)
    Usuario = Column(String(255), nullable=False)

    usuario = relationship("Usuario", back_populates="administrador")


class Conductor(Base):
    __tablename__ = 'Conductor'
    
    IdUsuario = Column(Integer, ForeignKey('Usuario.Id'), primary_key=True)

    usuario = relationship("Usuario", back_populates="conductor")
    vehiculos = relationship("Vehiculo", secondary="VehiculoConductor", back_populates="conductores")
    vehiculo_conductores = relationship("VehiculoConductor", back_populates="conductor", overlaps="vehiculos")

    @property
    def Nombre(self):
        return self.usuario.Nombre if self.usuario else None

    @property
    def Apellidos(self):
        return self.usuario.Apellidos if self.usuario else None

    @property
    def CI(self):
        return self.usuario.CI if self.usuario else None


class Vehiculo(Base):
    __tablename__ = 'Vehiculo'
    
    Id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    Marca = Column(String(100))
    Modelo = Column(String(100))
    Placa = Column(String(50), unique=True)
    Poliza = Column(String(100))
    Categoria = Column(String(100))
    Año = Column(Integer)
    conductores = relationship("Conductor", secondary="VehiculoConductor", back_populates="vehiculos", overlaps="vehiculo_conductores")
    vehiculo_conductores = relationship("VehiculoConductor", back_populates="vehiculo", overlaps="conductores,vehiculos")


class VehiculoConductor(Base):
    __tablename__ = 'VehiculoConductor'

    id = Column(Integer, primary_key=True, autoincrement=True)
    fechareg = Column(String(50))
    conductor_id = Column(Integer, ForeignKey('Conductor.IdUsuario', ondelete="CASCADE"), nullable=False)
    vehiculo_id = Column(Integer, ForeignKey('Vehiculo.Id', ondelete="CASCADE"), nullable=False)

    conductor = relationship("Conductor", back_populates="vehiculo_conductores", overlaps="conductores,vehiculos")
    vehiculo = relationship("Vehiculo", back_populates="vehiculo_conductores", overlaps="conductores,vehiculos")
    incidentes = relationship("Incidente", back_populates="vehiculoconductor")


class Mecanico(Base):
    __tablename__ = 'Mecanico'
    
    id = Column(Integer, ForeignKey('Usuario.Id', ondelete="CASCADE"), primary_key=True)
    estado = Column(String(50), default="Disponible")
    taller_id = Column(Integer, ForeignKey('Taller.Id', ondelete="SET NULL"), nullable=True)
    tenant_id = Column(Integer, ForeignKey('Tenant.Id', ondelete="CASCADE"), nullable=True)

    usuario = relationship("Usuario", back_populates="mecanico")
    taller = relationship("Taller", back_populates="mecanicos")
    incidentes_asignados = relationship("Incidente", secondary="IncidenteMecanico", back_populates="mecanicos")
