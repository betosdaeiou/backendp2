import sys
from src.core.database import Base, engine
from src.modules.saas.models import Tenant, PlanSaaS, Suscripcion
from src.modules.iam.models import Usuario, Rol, Permiso, UsuarioTenant
from src.modules.catalog.models import Administrador, Conductor, Mecanico, Vehiculo, VehiculoConductor, Taller, ServicioTaller
from src.modules.operations.models import Incidente, Evidencia, Cotizacion, Pago, Bitacora, Notificacion, MensajeChat, AnalisisIA

def reset_db():
    print("Dropping all tables...")
    Base.metadata.drop_all(bind=engine)
    print("Creating all tables...")
    Base.metadata.create_all(bind=engine)
    print("Database reset complete.")

if __name__ == "__main__":
    reset_db()
