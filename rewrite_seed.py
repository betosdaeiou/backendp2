import os

seed_code = '''"""
Seed completo de la plataforma.
Genera 2 tenants con todos los tipos de usuario, talleres, mecanicos,
conductores, vehiculos y operaciones (incidentes en todos los estados,
cotizaciones, pagos, evidencias, analisis IA, chat, bitacora y notificaciones).

Ejecutar:  python -m src.seed
"""

import datetime
import random
from src.core.database import Base, SessionLocal, engine
from src.core.security import get_password_hash

# ── Models ───────────────────────────────────────────────────────────────────
from src.modules.iam.models import Permiso, Rol, Usuario, UsuarioTenant
from src.modules.saas.models import Tenant, PlanSaaS, Suscripcion
from src.modules.catalog.models import (
    Administrador, Conductor, Mecanico,
    ServicioTaller, Taller, Vehiculo, VehiculoConductor,
)
from src.modules.operations.models import (
    AnalisisIA, Bitacora, Cotizacion, Evidencia,
    Incidente, MensajeChat, Notificacion, Pago,
)

# ── Helpers ──────────────────────────────────────────────────────────────────

def get_or_create(db, model, defaults=None, **filters):
    instance = db.query(model).filter_by(**filters).first()
    if instance:
        return instance, False
    params = {**filters, **(defaults or {})}
    instance = model(**params)
    db.add(instance)
    db.commit()
    db.refresh(instance)
    return instance, True

def make_user(db, *, correo, password, nombre, apellidos, ci, fecha_nac):
    existing = db.query(Usuario).filter(Usuario.Correo == correo).first()
    if existing:
        return existing
    u = Usuario(
        Correo=correo,
        Password=get_password_hash(password),
        Nombre=nombre,
        Apellidos=apellidos,
        CI=ci,
        Fechanac=fecha_nac,
    )
    db.add(u)
    db.commit()
    db.refresh(u)
    return u

def assign_tenant(db, user, tenant, rol):
    exists = db.query(UsuarioTenant).filter_by(
        usuario_id=user.Id, tenant_id=tenant.Id
    ).first()
    if not exists:
        db.add(UsuarioTenant(usuario_id=user.Id, tenant_id=tenant.Id, rol_id=rol.Id))
        db.commit()

# ═══════════════════════════════════════════════════════════════════════════════
#  1. PERMISOS & ROLES
# ═══════════════════════════════════════════════════════════════════════════════

PERMISOS_NOMBRES = [
    "Ver Operaciones", "Ver Reportes", "Gestionar Mecanicos",
    "Gestionar Usuarios", "Gestionar Roles", "Ver Bitacora",
    "Gestionar Tenants", "Gestionar Planes", "Ver Analytics",
]

ROLES_PERMISOS = {
    "Mecanico":       ["Ver Operaciones"],
    "Taller":         ["Ver Operaciones", "Ver Reportes", "Gestionar Mecanicos"],
    "Admin Tenant":   ["Ver Operaciones", "Ver Reportes", "Gestionar Mecanicos",
                       "Gestionar Usuarios", "Gestionar Roles", "Ver Bitacora", "Ver Analytics"],
    "Administrador":  ["Gestionar Usuarios", "Gestionar Roles", "Ver Bitacora",
                       "Gestionar Tenants", "Gestionar Planes", "Ver Analytics"],
    "Conductor":      [],
}

def seed_roles_permisos(db):
    permisos = {}
    for nombre in PERMISOS_NOMBRES:
        p, _ = get_or_create(db, Permiso, Nombre=nombre)
        permisos[nombre] = p
    roles = {}
    for rol_name, perm_names in ROLES_PERMISOS.items():
        r, _ = get_or_create(db, Rol, Nombre=rol_name)
        for pn in perm_names:
            if permisos[pn] not in r.permisos:
                r.permisos.append(permisos[pn])
        roles[rol_name] = r
    db.commit()
    return roles

# ═══════════════════════════════════════════════════════════════════════════════
#  2. PLANES & TENANTS
# ═══════════════════════════════════════════════════════════════════════════════

def seed_planes(db):
    planes_data = [
        {"Nombre": "Básico",  "PrecioMensual": 0,    "MaxUsuarios": 5,   "MaxIncidentes": 50,   "Descripcion": "Plan gratuito."},
        {"Nombre": "Pro",     "PrecioMensual": 2900,  "MaxUsuarios": 20,  "MaxIncidentes": 500,  "Descripcion": "Para talleres en crecimiento."},
        {"Nombre": "Premium", "PrecioMensual": 9900,  "MaxUsuarios": 100, "MaxIncidentes": 5000, "Descripcion": "Sin límites."},
    ]
    for d in planes_data:
        get_or_create(db, PlanSaaS, **d)
    return {p.Nombre: p for p in db.query(PlanSaaS).all()}

def seed_tenants(db, planes):
    t1, _ = get_or_create(db, Tenant, Nombre="Red AutoFix Bolivia",
                          defaults={"SuscripcionActiva": 1, "Dominio": "autofix.bo", "balance": 14500})
    t2, _ = get_or_create(db, Tenant, Nombre="MecaRed Express",
                          defaults={"SuscripcionActiva": 1, "Dominio": "mecared.com", "balance": 800})
    get_or_create(db, Suscripcion, tenant_id=t1.Id, plan_id=planes["Premium"].Id,
                  defaults={"Estado": "Activa"})
    get_or_create(db, Suscripcion, tenant_id=t2.Id, plan_id=planes["Básico"].Id,
                  defaults={"Estado": "Activa"})
    return t1, t2

# ── Generadores Aleatorios ──
NOMBRES = ["Carlos", "Luis", "José", "Juan", "Pedro", "María", "Ana", "Laura", "Fernanda", "Andrea", "Diego", "Miguel", "Sergio", "Daniel", "Jorge", "Raúl", "Roberto", "Alejandro", "Marco", "David", "Lucía", "Carmen", "Paola", "Valeria", "Gabriela", "Natalia", "Javier", "Manuel", "Víctor", "Fernando"]
APELLIDOS = ["Mamani", "Flores", "Condori", "Vargas", "Gutiérrez", "Rojas", "Choque", "Quispe", "Sánchez", "Gómez", "Rodríguez", "López", "Pérez", "García", "Martínez", "Chávez", "Ortiz", "Mendoza", "Castillo", "Suárez", "Montaño", "Rivera", "Jiménez", "Ruiz", "Díaz", "Álvarez", "Fernández", "Morales", "Cruz", "Ramos"]

def r_nombre(): return random.choice(NOMBRES)
def r_apellido(): return random.choice(APELLIDOS)
def r_ci(): return str(random.randint(1000000, 9999999))
def r_fecha_nac(): return datetime.date(random.randint(1970, 2000), random.randint(1, 12), random.randint(1, 28))
def r_coord(): return f"{random.uniform(-17.85, -17.72):.6f},{random.uniform(-63.22, -63.12):.6f}"
def r_fecha_reciente(dias=90):
    ahora = datetime.datetime.now()
    inicio = ahora - datetime.timedelta(days=dias)
    return inicio + datetime.timedelta(seconds=random.randint(0, int((ahora - inicio).total_seconds())))

# ═══════════════════════════════════════════════════════════════════════════════
#  3. USUARIOS
# ═══════════════════════════════════════════════════════════════════════════════

def seed_usuarios(db, roles, t1, t2):
    u = {}
    
    # ── Super Admin Global ──
    u["super"] = make_user(db, correo="admin@demo.local", password="Admin123!",
                           nombre="Carlos", apellidos="Rivas", ci="0000001", fecha_nac=datetime.date(1980, 1, 15))
    adm = db.query(Administrador).filter_by(IdUsuario=u["super"].Id).first()
    if not adm:
        db.add(Administrador(IdUsuario=u["super"].Id, Usuario="superadmin"))
        db.commit()

    # ─────────────── TENANT 1: Red AutoFix Bolivia ───────────────
    u["t1_admin"] = make_user(db, correo="admin.autofix@demo.local", password="User123!",
                              nombre="Laura", apellidos="Montaño", ci="1100001", fecha_nac=datetime.date(1988, 4, 10))
    assign_tenant(db, u["t1_admin"], t1, roles["Admin Tenant"])
    adm1 = db.query(Administrador).filter_by(IdUsuario=u["t1_admin"].Id).first()
    if not adm1:
        db.add(Administrador(IdUsuario=u["t1_admin"].Id, Usuario="LauraMontano"))
        db.commit()

    # Dueños de talleres (5 talleres para T1)
    for i in range(1, 6):
        key = f"t1_taller{i}"
        u[key] = make_user(db, correo=f"taller{i}.autofix@demo.local", password="User123!",
                           nombre=r_nombre(), apellidos=r_apellido(), ci=r_ci(), fecha_nac=r_fecha_nac())
        assign_tenant(db, u[key], t1, roles["Taller"])

    # Mecánicos T1 (10 mecánicos)
    for i in range(1, 11):
        key = f"t1_mec{i}"
        u[key] = make_user(db, correo=f"mecanico{i}.autofix@demo.local", password="User123!",
                           nombre=r_nombre(), apellidos=r_apellido(), ci=r_ci(), fecha_nac=r_fecha_nac())
        assign_tenant(db, u[key], t1, roles["Mecanico"])

    # Conductores Globales (15 conductores)
    for i in range(1, 16):
        key = f"cond{i}"
        u[key] = make_user(db, correo=f"conductor{i}@demo.local", password="User123!",
                           nombre=r_nombre(), apellidos=r_apellido(), ci=r_ci(), fecha_nac=r_fecha_nac())

    # ─────────────── TENANT 2: MecaRed Express ───────────────
    u["t2_admin"] = make_user(db, correo="admin.mecared@demo.local", password="User123!",
                              nombre="Roberto", apellidos="Gutiérrez", ci="3300001", fecha_nac=datetime.date(1987, 8, 3))
    assign_tenant(db, u["t2_admin"], t2, roles["Admin Tenant"])
    adm2 = db.query(Administrador).filter_by(IdUsuario=u["t2_admin"].Id).first()
    if not adm2:
        db.add(Administrador(IdUsuario=u["t2_admin"].Id, Usuario="RobertoGutierrez"))
        db.commit()

    u["t2_taller1"] = make_user(db, correo="taller.norte@demo.local", password="User123!",
                                nombre=r_nombre(), apellidos=r_apellido(), ci=r_ci(), fecha_nac=r_fecha_nac())
    assign_tenant(db, u["t2_taller1"], t2, roles["Taller"])

    u["t2_mec1"] = make_user(db, correo="mecanico.luis@demo.local", password="User123!",
                             nombre="Luis", apellidos="Condori", ci=r_ci(), fecha_nac=r_fecha_nac())
    assign_tenant(db, u["t2_mec1"], t2, roles["Mecanico"])

    return u

# ═══════════════════════════════════════════════════════════════════════════════
#  4. CATÁLOGOS
# ═══════════════════════════════════════════════════════════════════════════════

def seed_catalogos(db, u, t1, t2):
    cat = {}

    # ── Conductores ──
    for i in range(1, 16):
        key = f"cond{i}"
        c = db.query(Conductor).filter_by(IdUsuario=u[key].Id).first()
        if not c:
            c = Conductor(IdUsuario=u[key].Id)
            db.add(c)
            db.commit()
            db.refresh(c)
        cat[key] = c

    # ── Talleres Tenant 1 ──
    nombres_t1 = ["AutoFix Central", "AutoFix Sur", "AutoFix Norte", "AutoFix Este", "AutoFix Oeste"]
    talleres_t1 = []
    for i in range(1, 6):
        taller_obj = db.query(Taller).filter_by(Nombre=nombres_t1[i-1]).first()
        if not taller_obj:
            taller_obj = Taller(
                Nombre=nombres_t1[i-1], Direccion=f"Av. Anillo {i}, Santa Cruz",
                Coordenadas=r_coord(), Cap=random.randint(2, 6), Capmax=random.randint(6, 12),
                IdUsuario=u[f"t1_taller{i}"].Id, tenant_id=t1.Id,
            )
            db.add(taller_obj)
            db.commit()
            db.refresh(taller_obj)
        talleres_t1.append(taller_obj)
        cat[f"taller1_{i}"] = taller_obj
        
        # Servicios
        servs = random.sample(["Mecánica general", "Electricidad automotriz", "Cambio de aceite", "Alineación y balanceo", "Frenos", "Suspensión"], k=random.randint(2,5))
        for s in servs:
            if not db.query(ServicioTaller).filter_by(taller_id=taller_obj.Id, nombre=s).first():
                db.add(ServicioTaller(nombre=s, taller_id=taller_obj.Id))
        db.commit()

    # ── Taller Tenant 2 ──
    taller2 = db.query(Taller).filter_by(Nombre="MecaRed Norte").first()
    if not taller2:
        taller2 = Taller(
            Nombre="MecaRed Norte", Direccion="Av. Cristo Redentor km 5, Santa Cruz",
            Coordenadas=r_coord(), Cap=2, Capmax=6,
            IdUsuario=u["t2_taller1"].Id, tenant_id=t2.Id,
        )
        db.add(taller2)
        db.commit()
        db.refresh(taller2)
    cat["taller2a"] = taller2

    if not db.query(ServicioTaller).filter_by(taller_id=taller2.Id, nombre="Suspensión").first():
        db.add(ServicioTaller(nombre="Suspensión", taller_id=taller2.Id))
        db.commit()

    # ── Mecánicos T1 ──
    for i in range(1, 11):
        key = f"t1_mec{i}"
        taller_asig = random.choice(talleres_t1)
        m = db.query(Mecanico).filter_by(id=u[key].Id).first()
        if not m:
            m = Mecanico(id=u[key].Id, estado="Disponible", taller_id=taller_asig.Id, tenant_id=t1.Id)
            db.add(m)
            db.commit()
        cat[key] = m

    # ── Mecánico T2 ──
    m2 = db.query(Mecanico).filter_by(id=u["t2_mec1"].Id).first()
    if not m2:
        m2 = Mecanico(id=u["t2_mec1"].Id, estado="Disponible", taller_id=taller2.Id, tenant_id=t2.Id)
        db.add(m2)
        db.commit()
    cat["t2_mec1"] = m2

    return cat

# ═══════════════════════════════════════════════════════════════════════════════
#  5. VEHÍCULOS
# ═══════════════════════════════════════════════════════════════════════════════

MARCAS = ["Toyota", "Nissan", "Hyundai", "Suzuki", "Kia", "Ford", "Chevrolet"]
MODELOS = {"Toyota": ["Yaris", "Corolla", "Hilux"], "Nissan": ["Sentra", "Frontier", "Kicks"], "Hyundai": ["Tucson", "Accent", "Creta"], "Suzuki": ["Swift", "Vitara"], "Kia": ["Sportage", "Rio"], "Ford": ["Ranger", "Escape"], "Chevrolet": ["Tracker", "Spark"]}

def seed_vehiculos(db, cat):
    rels = {}
    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    for i in range(1, 16):
        cond_key = f"cond{i}"
        marca = random.choice(MARCAS)
        modelo = random.choice(MODELOS[marca]) + f" {random.randint(2010, 2024)}"
        placa = f"{random.choice(['LPZ', 'SCZ', 'CBB'])}-{random.randint(1000, 9999)}"
        categoria = random.choice(["Sedan", "SUV", "Camioneta", "Hatchback"])
        
        v = db.query(Vehiculo).filter_by(Placa=placa).first()
        if not v:
            v = Vehiculo(Marca=marca, Modelo=modelo, Placa=placa, Categoria=categoria, Año=random.randint(2010, 2024))
            db.add(v)
            db.commit()
            db.refresh(v)

        conductor = cat[cond_key]
        vc = db.query(VehiculoConductor).filter_by(conductor_id=conductor.IdUsuario, vehiculo_id=v.Id).first()
        if not vc:
            vc = VehiculoConductor(fechareg=now_str, conductor_id=conductor.IdUsuario, vehiculo_id=v.Id)
            db.add(vc)
            db.commit()
            db.refresh(vc)
        rels[cond_key] = vc

    return rels

# ═══════════════════════════════════════════════════════════════════════════════
#  6. INCIDENTES Y OPERACIONES
# ═══════════════════════════════════════════════════════════════════════════════

def _create_incidente(db, **kwargs):
    i = Incidente(**kwargs)
    db.add(i)
    db.commit()
    db.refresh(i)
    return i

def seed_operaciones(db, u, cat, rels, t1, t2):
    # Generar 35 incidentes históricos para T1
    estados = ["pagado", "pagado", "pagado", "pagado", "pagado", "resuelto", "en reparacion", "taller asignado", "cotizado", "pendiente"]
    
    for i in range(35):
        fecha_rep = r_fecha_reciente(120)
        cond_key = f"cond{random.randint(1, 10)}" # Usamos los primeros 10 conductores para t1
        taller_key = f"taller1_{random.randint(1, 5)}"
        estado = random.choice(estados)
        
        if estado == "pendiente":
            taller_id = None
        else:
            taller_id = cat[taller_key].Id
            
        inc = _create_incidente(db,
            coordenadagps=r_coord(), estado=estado,
            fecha=fecha_rep.strftime("%Y-%m-%d %H:%M:%S"),
            vc_id=rels[cond_key].id, taller_id=taller_id, tenant_id=t1.Id)
            
        db.add(Evidencia(
            descripcion=f"Falla mecánica reportada el {fecha_rep.strftime('%d/%m')}",
            fotos=f"falla_{i}.jpg", incidente_id=inc.id))
            
        # Si pasó de pendiente, hay cotización y análisis IA
        if estado != "pendiente":
            monto = random.randint(150, 2500)
            db.add(Cotizacion(
                monto=monto, mensaje="Revisión y reparación general", tiempo_estimado=f"{random.randint(1, 4)} horas",
                estado="Aceptada" if estado != "cotizado" else "Pendiente",
                fecha_creacion=(fecha_rep + datetime.timedelta(minutes=30)).strftime("%Y-%m-%d %H:%M:%S"),
                incidente_id=inc.id, taller_id=taller_id, tenant_id=t1.Id))
            db.add(AnalisisIA(
                Clasificacion=random.choice(["Motor", "Frenos", "Eléctrico", "Suspensión"]),
                NivelPrioridad=random.choice(["Alta", "Media", "Baja"]),
                Resumen="Análisis automático de daño estructural y piezas requeridas.",
                incidente_id=inc.id))
                
        # Si se asignó mecánico
        if estado in ["taller asignado", "en reparacion", "resuelto", "pagado"]:
            inc.fecha_asignacion = (fecha_rep + datetime.timedelta(minutes=45)).strftime("%Y-%m-%d %H:%M:%S")
            mec_id = u[f"t1_mec{random.randint(1, 10)}"].Id
            mec = db.query(Mecanico).filter_by(id=mec_id).first()
            if mec:
                inc.mecanicos.append(mec)
            db.commit()
            
        # Si llegó
        if estado in ["en reparacion", "resuelto", "pagado"]:
            inc.fecha_llegada = (fecha_rep + datetime.timedelta(hours=1)).strftime("%Y-%m-%d %H:%M:%S")
            
        # Si finalizó/pagó
        if estado in ["resuelto", "pagado"]:
            inc.fecha_finalizacion = (fecha_rep + datetime.timedelta(hours=random.randint(2, 6))).strftime("%Y-%m-%d %H:%M:%S")
            
            db.add(Bitacora(
                accion="INCIDENTE_RESUELTO", descripcion=f"Incidente resuelto con ID {inc.id}",
                fecha=inc.fecha_finalizacion[:10], ip="127.0.0.1",
                usuario_id=mec_id, tenant_id=t1.Id))
                
        # Si está pagado
        if estado == "pagado":
            db.add(Pago(
                monto_total=monto, metodo=random.choice(["Efectivo", "Tarjeta", "QR"]), estado="Completado",
                fecha=(fecha_rep + datetime.timedelta(hours=random.randint(6, 24))).strftime("%Y-%m-%d %H:%M:%S"),
                incidente_id=inc.id, tenant_id=t1.Id))
                
        db.commit()

    # ── Tenant 2: MecaRed Express (solo 2 ejemplos) ──
    inc_t2 = _create_incidente(db,
        coordenadagps=r_coord(), estado="taller asignado",
        fecha=datetime.datetime.now().strftime("%Y-%m-%d 10:00:00"),
        vc_id=rels["cond14"].id, taller_id=cat["taller2a"].Id, tenant_id=t2.Id)
        
    db.add(Evidencia(descripcion="El vehículo vibra mucho.", fotos="vibracion.jpg", incidente_id=inc_t2.id))
    db.add(Cotizacion(monto=200, mensaje="Balanceo de llantas", tiempo_estimado="1 hora", estado="Aceptada",
                      fecha_creacion=datetime.datetime.now().strftime("%Y-%m-%d 10:30:00"),
                      incidente_id=inc_t2.id, taller_id=cat["taller2a"].Id, tenant_id=t2.Id))
    
    db.commit()


# ═══════════════════════════════════════════════════════════════════════════════
#  ORQUESTADOR
# ═══════════════════════════════════════════════════════════════════════════════

def run_seed():
    print("Iniciando seed de base de datos...")
    Base.metadata.drop_all(bind=engine)
    print("✓ Tablas eliminadas")
    Base.metadata.create_all(bind=engine)
    print("✓ Tablas creadas nuevamente")

    db = SessionLocal()
    try:
        roles = seed_roles_permisos(db)
        print("✓ Roles y permisos generados")

        planes = seed_planes(db)
        t1, t2 = seed_tenants(db, planes)
        print("✓ Planes SaaS y Tenants generados")

        u = seed_usuarios(db, roles, t1, t2)
        print("✓ Usuarios generados (Admins, Mecánicos, Conductores)")

        cat = seed_catalogos(db, u, t1, t2)
        print("✓ Catálogos generados (Talleres, Servicios)")

        rels = seed_vehiculos(db, cat)
        print("✓ Vehículos generados")

        seed_operaciones(db, u, cat, rels, t1, t2)
        print("✓ Operaciones generadas (35+ Incidentes masivos en T1, pocos en T2)")

        print("¡Seed completado con éxito!")
    except Exception as e:
        print(f"Error durante el seed: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    run_seed()
'''

with open(r'c:\Users\aober\OneDrive\Documents\GitHub\lin\backendp2\src\seed.py', 'w', encoding='utf-8') as f:
    f.write(seed_code)
print("Updated seed.py")
