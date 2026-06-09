"""
Seed completo de la plataforma.
Genera 2 tenants con todos los tipos de usuario, talleres, mecanicos,
conductores, vehiculos y operaciones (incidentes en todos los estados,
cotizaciones, pagos, evidencias, analisis IA, chat, bitacora y notificaciones).

Ejecutar:  python -m src.seed
"""

import datetime
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
    """Devuelve (instancia, creado: bool)."""
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
    """Crea un Usuario si no existe."""
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
    """Crea membresía usuario↔tenant si no existe."""
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
        {"Nombre": "Básico",  "PrecioMensual": 0,    "MaxUsuarios": 5,   "MaxIncidentes": 50,   "Descripcion": "Plan gratuito para iniciar."},
        {"Nombre": "Pro",     "PrecioMensual": 2900,  "MaxUsuarios": 20,  "MaxIncidentes": 500,  "Descripcion": "Para talleres en crecimiento.", "StripePriceId": "price_mock_pro"},
        {"Nombre": "Premium", "PrecioMensual": 9900,  "MaxUsuarios": 100, "MaxIncidentes": 5000, "Descripcion": "Sin límites.", "StripePriceId": "price_mock_premium"},
    ]
    for d in planes_data:
        get_or_create(db, PlanSaaS, **d)
    return {p.Nombre: p for p in db.query(PlanSaaS).all()}


def seed_tenants(db, planes):
    t1, _ = get_or_create(db, Tenant, Nombre="Red AutoFix Bolivia",
                          defaults={"SuscripcionActiva": 1, "Dominio": "autofix.bo", "balance": 1650})
    t2, _ = get_or_create(db, Tenant, Nombre="MecaRed Express",
                          defaults={"SuscripcionActiva": 1, "Dominio": "mecared.com", "balance": 800})

    # Suscripciones
    get_or_create(db, Suscripcion, tenant_id=t1.Id, plan_id=planes["Pro"].Id,
                  defaults={"Estado": "Activa"})
    get_or_create(db, Suscripcion, tenant_id=t2.Id, plan_id=planes["Básico"].Id,
                  defaults={"Estado": "Activa"})
    return t1, t2


# ═══════════════════════════════════════════════════════════════════════════════
#  3. USUARIOS POR TENANT
# ═══════════════════════════════════════════════════════════════════════════════

def seed_usuarios(db, roles, t1, t2):
    u = {}

    # ── Super Admin Global ──
    u["super"] = make_user(db, correo="admin@demo.local", password="Admin123!",
                           nombre="Carlos", apellidos="Rivas", ci="0000001",
                           fecha_nac=datetime.date(1980, 1, 15))
    adm = db.query(Administrador).filter_by(IdUsuario=u["super"].Id).first()
    if not adm:
        db.add(Administrador(IdUsuario=u["super"].Id, Usuario="superadmin"))
        db.commit()

    # ─────────────── TENANT 1: Red AutoFix Bolivia ───────────────

    # Admin del tenant
    u["t1_admin"] = make_user(db, correo="admin.autofix@demo.local", password="User123!",
                              nombre="Laura", apellidos="Montaño", ci="1100001",
                              fecha_nac=datetime.date(1988, 4, 10))
    assign_tenant(db, u["t1_admin"], t1, roles["Admin Tenant"])
    adm1 = db.query(Administrador).filter_by(IdUsuario=u["t1_admin"].Id).first()
    if not adm1:
        db.add(Administrador(IdUsuario=u["t1_admin"].Id, Usuario="LauraMontano"))
        db.commit()

    # Dueño taller 1A
    u["t1_taller1"] = make_user(db, correo="taller.central@demo.local", password="User123!",
                                nombre="Mario", apellidos="Quiroga", ci="1100002",
                                fecha_nac=datetime.date(1985, 6, 20))
    assign_tenant(db, u["t1_taller1"], t1, roles["Taller"])

    # Dueño taller 1B
    u["t1_taller2"] = make_user(db, correo="taller.sur@demo.local", password="User123!",
                                nombre="Andrea", apellidos="Sánchez", ci="1100003",
                                fecha_nac=datetime.date(1990, 9, 5))
    assign_tenant(db, u["t1_taller2"], t1, roles["Taller"])

    # Mecánicos tenant 1
    u["t1_mec1"] = make_user(db, correo="mecanico.juan@demo.local", password="User123!",
                             nombre="Juan", apellidos="Flores", ci="1100004",
                             fecha_nac=datetime.date(1993, 2, 14))
    assign_tenant(db, u["t1_mec1"], t1, roles["Mecanico"])

    u["t1_mec2"] = make_user(db, correo="mecanico.pedro@demo.local", password="User123!",
                             nombre="Pedro", apellidos="Mamani", ci="1100005",
                             fecha_nac=datetime.date(1991, 7, 30))
    assign_tenant(db, u["t1_mec2"], t1, roles["Mecanico"])

    # Conductores (globales, sin tenant)
    u["cond1"] = make_user(db, correo="conductor.ana@demo.local", password="User123!",
                           nombre="Ana", apellidos="López", ci="2200001",
                           fecha_nac=datetime.date(1995, 3, 8))
    u["cond2"] = make_user(db, correo="conductor.diego@demo.local", password="User123!",
                           nombre="Diego", apellidos="Vargas", ci="2200002",
                           fecha_nac=datetime.date(1992, 11, 22))
    u["cond3"] = make_user(db, correo="conductor.sofia@demo.local", password="User123!",
                           nombre="Sofía", apellidos="Rojas", ci="2200003",
                           fecha_nac=datetime.date(1997, 5, 17))

    # ─────────────── TENANT 2: MecaRed Express ───────────────

    u["t2_admin"] = make_user(db, correo="admin.mecared@demo.local", password="User123!",
                              nombre="Roberto", apellidos="Gutiérrez", ci="3300001",
                              fecha_nac=datetime.date(1987, 8, 3))
    assign_tenant(db, u["t2_admin"], t2, roles["Admin Tenant"])
    adm2 = db.query(Administrador).filter_by(IdUsuario=u["t2_admin"].Id).first()
    if not adm2:
        db.add(Administrador(IdUsuario=u["t2_admin"].Id, Usuario="RobertoGutierrez"))
        db.commit()

    u["t2_taller1"] = make_user(db, correo="taller.norte@demo.local", password="User123!",
                                nombre="Fernanda", apellidos="Torrez", ci="3300002",
                                fecha_nac=datetime.date(1989, 12, 1))
    assign_tenant(db, u["t2_taller1"], t2, roles["Taller"])

    u["t2_mec1"] = make_user(db, correo="mecanico.luis@demo.local", password="User123!",
                             nombre="Luis", apellidos="Condori", ci="3300003",
                             fecha_nac=datetime.date(1994, 4, 25))
    assign_tenant(db, u["t2_mec1"], t2, roles["Mecanico"])

    return u


# ═══════════════════════════════════════════════════════════════════════════════
#  4. PERFILES DE CATÁLOGO (Conductor, Taller, Mecánico)
# ═══════════════════════════════════════════════════════════════════════════════

def seed_catalogos(db, u, t1, t2):
    cat = {}

    # ── Conductores ──
    for key in ["cond1", "cond2", "cond3"]:
        c = db.query(Conductor).filter_by(IdUsuario=u[key].Id).first()
        if not c:
            c = Conductor(IdUsuario=u[key].Id)
            db.add(c)
            db.commit()
            db.refresh(c)
        cat[key] = c

    # ── Talleres Tenant 1 ──
    taller1a = db.query(Taller).filter_by(Nombre="AutoFix Central").first()
    if not taller1a:
        taller1a = Taller(
            Nombre="AutoFix Central", Direccion="Av. Banzer 3er Anillo, Santa Cruz",
            Coordenadas="-17.7650,-63.1750", Cap=3, Capmax=8,
            IdUsuario=u["t1_taller1"].Id, tenant_id=t1.Id,
        )
        db.add(taller1a)
        db.commit()
        db.refresh(taller1a)
    cat["taller1a"] = taller1a

    taller1b = db.query(Taller).filter_by(Nombre="AutoFix Sur").first()
    if not taller1b:
        taller1b = Taller(
            Nombre="AutoFix Sur", Direccion="Av. Santos Dumont 4to Anillo, Santa Cruz",
            Coordenadas="-17.8100,-63.1800", Cap=1, Capmax=5,
            IdUsuario=u["t1_taller2"].Id, tenant_id=t1.Id,
        )
        db.add(taller1b)
        db.commit()
        db.refresh(taller1b)
    cat["taller1b"] = taller1b

    # ── Taller Tenant 2 ──
    taller2a = db.query(Taller).filter_by(Nombre="MecaRed Norte").first()
    if not taller2a:
        taller2a = Taller(
            Nombre="MecaRed Norte", Direccion="Av. Cristo Redentor km 5, Santa Cruz",
            Coordenadas="-17.7500,-63.1700", Cap=2, Capmax=6,
            IdUsuario=u["t2_taller1"].Id, tenant_id=t2.Id,
        )
        db.add(taller2a)
        db.commit()
        db.refresh(taller2a)
    cat["taller2a"] = taller2a

    # ── Servicios ──
    for taller, servicios in [
        (taller1a, ["Mecánica general", "Electricidad automotriz", "Cambio de aceite"]),
        (taller1b, ["Alineación y balanceo", "Frenos"]),
        (taller2a, ["Diagnóstico computarizado", "Cambio de llantas", "Suspensión"]),
    ]:
        for s_nombre in servicios:
            exists = db.query(ServicioTaller).filter_by(taller_id=taller.Id, nombre=s_nombre).first()
            if not exists:
                db.add(ServicioTaller(nombre=s_nombre, taller_id=taller.Id))
    db.commit()

    # ── Mecánicos ──
    for key, taller, tenant in [
        ("t1_mec1", taller1a, t1),
        ("t1_mec2", taller1b, t1),
        ("t2_mec1", taller2a, t2),
    ]:
        m = db.query(Mecanico).filter_by(id=u[key].Id).first()
        if not m:
            m = Mecanico(id=u[key].Id, estado="Disponible", taller_id=taller.Id, tenant_id=tenant.Id)
            db.add(m)
            db.commit()
        cat[key] = m

    return cat


# ═══════════════════════════════════════════════════════════════════════════════
#  5. VEHÍCULOS & RELACIONES CONDUCTOR-VEHÍCULO
# ═══════════════════════════════════════════════════════════════════════════════

VEHICULOS = [
    {"Marca": "Toyota",    "Modelo": "Yaris 2022",     "Placa": "LPZ-1234", "Categoria": "Sedan",     "Año": 2022, "conductor_key": "cond1"},
    {"Marca": "Hyundai",   "Modelo": "Tucson 2021",    "Placa": "CBB-5678", "Categoria": "SUV",       "Año": 2021, "conductor_key": "cond2"},
    {"Marca": "Nissan",    "Modelo": "NP300 Frontier",  "Placa": "SCZ-9012", "Categoria": "Camioneta", "Año": 2020, "conductor_key": "cond3"},
]


def seed_vehiculos(db, cat):
    rels = {}
    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    for v_data in VEHICULOS:
        cond_key = v_data.pop("conductor_key")
        v = db.query(Vehiculo).filter_by(Placa=v_data["Placa"]).first()
        if not v:
            v = Vehiculo(**v_data)
            db.add(v)
            db.commit()
            db.refresh(v)

        conductor = cat[cond_key]
        vc = db.query(VehiculoConductor).filter_by(
            conductor_id=conductor.IdUsuario, vehiculo_id=v.Id
        ).first()
        if not vc:
            vc = VehiculoConductor(
                fechareg=now_str, conductor_id=conductor.IdUsuario, vehiculo_id=v.Id
            )
            db.add(vc)
            db.commit()
            db.refresh(vc)

        rels[cond_key] = vc

    return rels


# ═══════════════════════════════════════════════════════════════════════════════
#  6. INCIDENTES Y TODAS LAS OPERACIONES
# ═══════════════════════════════════════════════════════════════════════════════

def seed_operaciones(db, u, cat, rels, t1, t2):
    """
    Crea incidentes en distintos estados para ambos tenants:
      • Pendiente  — recién reportado
      • Cotizado   — con cotización esperando aceptación
      • Taller asignado — mecánico en camino
      • En reparación — mecánico trabajando
      • Resuelto  — finalizado y pagado
    """

    # ═══════════════════════════════════════════════════════════════════════
    #  TENANT 1  —  Red AutoFix Bolivia
    # ═══════════════════════════════════════════════════════════════════════

    # ── Incidente 1: PENDIENTE (recién reportado, sin taller) ──
    inc1 = _create_incidente(db,
        coordenadagps="-17.7680,-63.1720", estado="pendiente",
        fecha="2026-06-05 08:30:00",
        vc_id=rels["cond1"].id, taller_id=None, tenant_id=t1.Id)

    if inc1:
        db.add(Evidencia(
            descripcion="Se escuchó un ruido fuerte en el motor al encender el vehículo.",
            fotos="motor_ruido_01.jpg,motor_ruido_02.jpg",
            incidente_id=inc1.id))
        db.add(Notificacion(
            titulo="Incidente reportado", descripcion="Ana López reportó un problema con su Toyota Yaris.",
            fecha="2026-06-05 08:31:00", usuario_id=u["t1_admin"].Id, tenant_id=t1.Id))
        db.commit()

    # ── Incidente 2: COTIZADO (cotización enviada, esperando aceptación) ──
    inc2 = _create_incidente(db,
        coordenadagps="-17.7600,-63.1800", estado="cotizado",
        fecha="2026-06-04 14:00:00",
        vc_id=rels["cond1"].id, taller_id=cat["taller1a"].Id, tenant_id=t1.Id)

    if inc2:
        db.add(Evidencia(
            descripcion="La llanta delantera izquierda está completamente desinflada.",
            fotos="llanta_pinchada.jpg",
            incidente_id=inc2.id))
        db.add(Cotizacion(
            monto=180, mensaje="Cambio de llanta + alineación", tiempo_estimado="45 min",
            estado="Pendiente", fecha_creacion="2026-06-04 14:30:00",
            incidente_id=inc2.id, taller_id=cat["taller1a"].Id, tenant_id=t1.Id))
        db.add(AnalisisIA(
            Clasificacion="Neumático", NivelPrioridad="Baja",
            Resumen="Pinchazo en llanta delantera izquierda. No hay daños estructurales visibles.",
            incidente_id=inc2.id))
        db.add(MensajeChat(contenido="Buenas tardes, le envié la cotización.", fecha="2026-06-04 14:32:00",
                           incidente_id=inc2.id, usuario_id=u["t1_taller1"].Id))
        db.add(MensajeChat(contenido="Gracias, lo reviso.", fecha="2026-06-04 14:35:00",
                           incidente_id=inc2.id, usuario_id=u["cond1"].Id))
        db.commit()

    # ── Incidente 3: TALLER ASIGNADO (mecánico en camino) ──
    inc3 = _create_incidente(db,
        coordenadagps="-17.8150,-63.1850", estado="taller asignado",
        fecha="2026-06-06 10:15:00", fecha_asignacion="2026-06-06 10:25:00",
        vc_id=rels["cond2"].id, taller_id=cat["taller1b"].Id, tenant_id=t1.Id)

    if inc3:
        db.add(Evidencia(
            descripcion="Los frenos hacen un chirrido al frenar a baja velocidad.",
            fotos="frenos_desgaste.jpg",
            incidente_id=inc3.id))
        db.add(Cotizacion(
            monto=350, mensaje="Cambio de pastillas de freno delanteras y traseras",
            tiempo_estimado="1 hora", estado="Aceptada", fecha_creacion="2026-06-06 10:20:00",
            incidente_id=inc3.id, taller_id=cat["taller1b"].Id, tenant_id=t1.Id))
        db.add(AnalisisIA(
            Clasificacion="Sistema de frenos", NivelPrioridad="Alta",
            Resumen="Desgaste severo de pastillas de freno. Se recomienda reemplazo inmediato.",
            incidente_id=inc3.id))
        if cat.get("t1_mec2") and cat["t1_mec2"] not in inc3.mecanicos:
            inc3.mecanicos.append(cat["t1_mec2"])
        db.add(MensajeChat(contenido="Ya salí del taller, llego en 15 minutos.", fecha="2026-06-06 10:30:00",
                           incidente_id=inc3.id, usuario_id=u["t1_mec2"].Id))
        db.add(Notificacion(
            titulo="Mecánico en camino", descripcion="Pedro Mamani se dirige a tu ubicación.",
            fecha="2026-06-06 10:26:00", usuario_id=u["cond2"].Id, tenant_id=t1.Id))
        db.commit()

    # ── Incidente 4: EN REPARACIÓN ──
    inc4 = _create_incidente(db,
        coordenadagps="-17.7630,-63.1780", estado="en reparacion",
        fecha="2026-06-06 07:00:00", fecha_asignacion="2026-06-06 07:15:00",
        fecha_llegada="2026-06-06 07:40:00",
        vc_id=rels["cond2"].id, taller_id=cat["taller1a"].Id, tenant_id=t1.Id)

    if inc4:
        db.add(Evidencia(
            descripcion="El aire acondicionado no enfría y hace un sonido extraño.",
            fotos="ac_falla_01.jpg,ac_falla_02.jpg",
            incidente_id=inc4.id))
        db.add(Cotizacion(
            monto=520, mensaje="Recarga de gas + revisión del compresor",
            tiempo_estimado="2 horas", estado="Aceptada", fecha_creacion="2026-06-06 07:20:00",
            incidente_id=inc4.id, taller_id=cat["taller1a"].Id, tenant_id=t1.Id))
        db.add(AnalisisIA(
            Clasificacion="Aire acondicionado", NivelPrioridad="Media",
            Resumen="Sistema de A/C sin refrigerante. Posible fuga en el compresor.",
            incidente_id=inc4.id))
        if cat.get("t1_mec1") and cat["t1_mec1"] not in inc4.mecanicos:
            inc4.mecanicos.append(cat["t1_mec1"])
        db.add(MensajeChat(contenido="Ya llegué, estoy revisando el compresor.", fecha="2026-06-06 07:42:00",
                           incidente_id=inc4.id, usuario_id=u["t1_mec1"].Id))
        db.add(MensajeChat(contenido="¿Cuánto tiempo más tomará?", fecha="2026-06-06 08:10:00",
                           incidente_id=inc4.id, usuario_id=u["cond2"].Id))
        db.add(MensajeChat(contenido="Aproximadamente 1 hora más, encontré la fuga.", fecha="2026-06-06 08:12:00",
                           incidente_id=inc4.id, usuario_id=u["t1_mec1"].Id))
        db.commit()

    # ── Incidente 5: RESUELTO (pagado) ──
    inc5 = _create_incidente(db,
        coordenadagps="-17.7670,-63.1710", estado="resuelto",
        fecha="2026-05-28 09:00:00", fecha_asignacion="2026-05-28 09:10:00",
        fecha_llegada="2026-05-28 09:30:00", fecha_finalizacion="2026-05-28 11:00:00",
        vc_id=rels["cond1"].id, taller_id=cat["taller1a"].Id, tenant_id=t1.Id)

    if inc5:
        db.add(Evidencia(
            descripcion="La batería del vehículo no carga. El motor no arranca.",
            fotos="bateria_muerta.jpg",
            incidente_id=inc5.id))
        db.add(Cotizacion(
            monto=280, mensaje="Cambio de batería 12V", tiempo_estimado="30 min",
            estado="Aceptada", fecha_creacion="2026-05-28 09:15:00",
            incidente_id=inc5.id, taller_id=cat["taller1a"].Id, tenant_id=t1.Id))
        db.add(AnalisisIA(
            Clasificacion="Falla eléctrica", NivelPrioridad="Alta",
            Resumen="Batería sin voltaje. Requiere reemplazo completo.",
            incidente_id=inc5.id))
        if cat.get("t1_mec1") and cat["t1_mec1"] not in inc5.mecanicos:
            inc5.mecanicos.append(cat["t1_mec1"])
        db.add(Pago(
            monto_total=280, metodo="Tarjeta", estado="Completado",
            fecha="2026-05-28 11:05:00", incidente_id=inc5.id, tenant_id=t1.Id))
        db.add(MensajeChat(contenido="Listo, batería cambiada. ¡Buen viaje!", fecha="2026-05-28 11:01:00",
                           incidente_id=inc5.id, usuario_id=u["t1_mec1"].Id))
        db.add(Notificacion(
            titulo="Servicio completado", descripcion="Tu vehículo Toyota Yaris fue reparado exitosamente.",
            fecha="2026-05-28 11:02:00", usuario_id=u["cond1"].Id, tenant_id=t1.Id))
        db.add(Bitacora(
            accion="INCIDENTE_RESUELTO", descripcion="Incidente de batería resuelto - Toyota Yaris LPZ-1234",
            fecha=datetime.date(2026, 5, 28), ip="192.168.1.10",
            usuario_id=u["t1_mec1"].Id, tenant_id=t1.Id))
        db.commit()

    # ── Incidente 6: RESUELTO antiguo (más datos históricos) ──
    inc6 = _create_incidente(db,
        coordenadagps="-17.8080,-63.1820", estado="resuelto",
        fecha="2026-05-20 16:00:00", fecha_asignacion="2026-05-20 16:10:00",
        fecha_llegada="2026-05-20 16:35:00", fecha_finalizacion="2026-05-20 18:00:00",
        vc_id=rels["cond2"].id, taller_id=cat["taller1b"].Id, tenant_id=t1.Id)

    if inc6:
        db.add(Evidencia(
            descripcion="El motor se recalienta después de 20 minutos de manejo.",
            fotos="motor_recalentado.jpg",
            incidente_id=inc6.id))
        db.add(Cotizacion(
            monto=450, mensaje="Cambio de termostato + limpieza de radiador",
            tiempo_estimado="1.5 horas", estado="Aceptada", fecha_creacion="2026-05-20 16:15:00",
            incidente_id=inc6.id, taller_id=cat["taller1b"].Id, tenant_id=t1.Id))
        db.add(AnalisisIA(
            Clasificacion="Sistema de refrigeración", NivelPrioridad="Alta",
            Resumen="Termostato atascado en posición cerrada. Radiador con acumulación de sedimentos.",
            incidente_id=inc6.id))
        if cat.get("t1_mec2") and cat["t1_mec2"] not in inc6.mecanicos:
            inc6.mecanicos.append(cat["t1_mec2"])
        db.add(Pago(
            monto_total=450, metodo="Efectivo", estado="Completado",
            fecha="2026-05-20 18:05:00", incidente_id=inc6.id, tenant_id=t1.Id))
        db.add(Bitacora(
            accion="INCIDENTE_RESUELTO", descripcion="Incidente de refrigeración resuelto - Hyundai Tucson",
            fecha=datetime.date(2026, 5, 20), ip="192.168.1.15",
            usuario_id=u["t1_mec2"].Id, tenant_id=t1.Id))
        db.commit()

    # ═══════════════════════════════════════════════════════════════════════
    #  TENANT 2  —  MecaRed Express
    # ═══════════════════════════════════════════════════════════════════════

    # ── Incidente 7: PENDIENTE ──
    inc7 = _create_incidente(db,
        coordenadagps="-17.7480,-63.1680", estado="pendiente",
        fecha="2026-06-06 11:00:00",
        vc_id=rels["cond3"].id, taller_id=None, tenant_id=t2.Id)

    if inc7:
        db.add(Evidencia(
            descripcion="Se prendió la luz del check engine en el tablero.",
            fotos="check_engine.jpg",
            incidente_id=inc7.id))
        db.add(Notificacion(
            titulo="Nuevo incidente", descripcion="Sofía Rojas reportó un problema con su Nissan NP300.",
            fecha="2026-06-06 11:01:00", usuario_id=u["t2_admin"].Id, tenant_id=t2.Id))
        db.commit()

    # ── Incidente 8: TALLER ASIGNADO ──
    inc8 = _create_incidente(db,
        coordenadagps="-17.7520,-63.1650", estado="taller asignado",
        fecha="2026-06-05 15:00:00", fecha_asignacion="2026-06-05 15:15:00",
        vc_id=rels["cond3"].id, taller_id=cat["taller2a"].Id, tenant_id=t2.Id)

    if inc8:
        db.add(Evidencia(
            descripcion="El vehículo vibra mucho al pasar de 80 km/h.",
            fotos="vibracion_volante.jpg",
            incidente_id=inc8.id))
        db.add(Cotizacion(
            monto=200, mensaje="Balanceo de llantas + revisión de amortiguadores",
            tiempo_estimado="1 hora", estado="Aceptada", fecha_creacion="2026-06-05 15:10:00",
            incidente_id=inc8.id, taller_id=cat["taller2a"].Id, tenant_id=t2.Id))
        db.add(AnalisisIA(
            Clasificacion="Suspensión/Dirección", NivelPrioridad="Media",
            Resumen="Desbalanceo en llantas delanteras. Posible desgaste de rótulas.",
            incidente_id=inc8.id))
        if cat.get("t2_mec1") and cat["t2_mec1"] not in inc8.mecanicos:
            inc8.mecanicos.append(cat["t2_mec1"])
        db.add(MensajeChat(contenido="Buenas tardes, estoy saliendo del taller.", fecha="2026-06-05 15:18:00",
                           incidente_id=inc8.id, usuario_id=u["t2_mec1"].Id))
        db.add(Notificacion(
            titulo="Mecánico asignado", descripcion="Luis Condori atenderá tu incidente.",
            fecha="2026-06-05 15:16:00", usuario_id=u["cond3"].Id, tenant_id=t2.Id))
        db.commit()

    # ── Incidente 9: RESUELTO (pagado) ──
    inc9 = _create_incidente(db,
        coordenadagps="-17.7490,-63.1720", estado="resuelto",
        fecha="2026-05-25 13:00:00", fecha_asignacion="2026-05-25 13:10:00",
        fecha_llegada="2026-05-25 13:30:00", fecha_finalizacion="2026-05-25 15:00:00",
        vc_id=rels["cond3"].id, taller_id=cat["taller2a"].Id, tenant_id=t2.Id)

    if inc9:
        db.add(Evidencia(
            descripcion="Se reventó la manguera del radiador y salió vapor del capó.",
            fotos="manguera_rota.jpg,vapor_capo.jpg",
            incidente_id=inc9.id))
        db.add(Cotizacion(
            monto=150, mensaje="Cambio de manguera de radiador",
            tiempo_estimado="40 min", estado="Aceptada", fecha_creacion="2026-05-25 13:15:00",
            incidente_id=inc9.id, taller_id=cat["taller2a"].Id, tenant_id=t2.Id))
        db.add(AnalisisIA(
            Clasificacion="Sistema de refrigeración", NivelPrioridad="Alta",
            Resumen="Manguera superior del radiador reventada. Requiere reemplazo urgente.",
            incidente_id=inc9.id))
        if cat.get("t2_mec1") and cat["t2_mec1"] not in inc9.mecanicos:
            inc9.mecanicos.append(cat["t2_mec1"])
        db.add(Pago(
            monto_total=150, metodo="QR", estado="Completado",
            fecha="2026-05-25 15:05:00", incidente_id=inc9.id, tenant_id=t2.Id))
        db.add(MensajeChat(contenido="Manguera cambiada, probando que no haya fugas.", fecha="2026-05-25 14:50:00",
                           incidente_id=inc9.id, usuario_id=u["t2_mec1"].Id))
        db.add(MensajeChat(contenido="Perfecto, muchas gracias!", fecha="2026-05-25 15:02:00",
                           incidente_id=inc9.id, usuario_id=u["cond3"].Id))
        db.add(Notificacion(
            titulo="Servicio finalizado", descripcion="Tu Nissan NP300 fue reparado exitosamente.",
            fecha="2026-05-25 15:01:00", usuario_id=u["cond3"].Id, tenant_id=t2.Id))
        db.add(Bitacora(
            accion="INCIDENTE_RESUELTO", descripcion="Manguera de radiador cambiada - Nissan NP300 SCZ-9012",
            fecha=datetime.date(2026, 5, 25), ip="10.0.0.5",
            usuario_id=u["t2_mec1"].Id, tenant_id=t2.Id))
        db.commit()

    # ── Bitácora extra (operaciones de login, etc.) ──
    _seed_bitacora_extra(db, u, t1, t2)


def _create_incidente(db, *, coordenadagps, estado, fecha, vc_id, taller_id, tenant_id,
                      fecha_asignacion=None, fecha_llegada=None, fecha_finalizacion=None):
    """Crea un incidente solo si no existe uno con el mismo vc + fecha."""
    exists = db.query(Incidente).filter_by(vehiculoconductor_id=vc_id, fecha=fecha).first()
    if exists:
        return None
    inc = Incidente(
        coordenadagps=coordenadagps, estado=estado, fecha=fecha,
        fecha_asignacion=fecha_asignacion, fecha_llegada=fecha_llegada,
        fecha_finalizacion=fecha_finalizacion,
        vehiculoconductor_id=vc_id, taller_id=taller_id, tenant_id=tenant_id,
    )
    db.add(inc)
    db.commit()
    db.refresh(inc)
    return inc


def _seed_bitacora_extra(db, u, t1, t2):
    """Entradas de bitácora genéricas para que el log no esté vacío."""
    entries = [
        ("Inicio de Sesión", "Laura Montaño inició sesión", datetime.date(2026, 6, 5), u["t1_admin"].Id, t1.Id),
        ("Crear Usuario",    "Se creó la cuenta de mecanico.juan@demo.local", datetime.date(2026, 6, 1), u["t1_admin"].Id, t1.Id),
        ("Crear Usuario",    "Se creó la cuenta de mecanico.pedro@demo.local", datetime.date(2026, 6, 1), u["t1_admin"].Id, t1.Id),
        ("Inicio de Sesión", "Roberto Gutiérrez inició sesión", datetime.date(2026, 6, 5), u["t2_admin"].Id, t2.Id),
        ("Crear Usuario",    "Se registró el taller MecaRed Norte", datetime.date(2026, 5, 30), u["t2_admin"].Id, t2.Id),
        ("Inicio de Sesión", "admin@demo.local inició sesión como Super Admin", datetime.date(2026, 6, 6), u["super"].Id, None),
    ]
    for accion, desc, fecha, uid, tid in entries:
        exists = db.query(Bitacora).filter_by(accion=accion, descripcion=desc).first()
        if not exists:
            db.add(Bitacora(accion=accion, descripcion=desc, fecha=fecha, ip="127.0.0.1",
                            usuario_id=uid, tenant_id=tid))
    db.commit()


# ═══════════════════════════════════════════════════════════════════════════════
#  MAIN
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        print("[1/7] Creando permisos y roles...")
        roles = seed_roles_permisos(db)

        print("[2/7] Creando planes SaaS...")
        planes = seed_planes(db)

        print("[3/7] Creando tenants...")
        t1, t2 = seed_tenants(db, planes)

        print("[4/7] Creando usuarios...")
        u = seed_usuarios(db, roles, t1, t2)

        print("[5/7] Creando catalogos (talleres, mecanicos, conductores)...")
        cat = seed_catalogos(db, u, t1, t2)

        print("[6/7] Creando vehiculos...")
        rels = seed_vehiculos(db, cat)

        print("[7/7] Creando incidentes y operaciones...")
        seed_operaciones(db, u, cat, rels, t1, t2)

        print()
        print("=" * 60)
        print("  SEED COMPLETADO EXITOSAMENTE")
        print("=" * 60)
        print()
        print("  TENANTS:")
        print(f"    1. {t1.Nombre} (Plan Pro)")
        print(f"    2. {t2.Nombre} (Plan Basico)")
        print()
        print("  CREDENCIALES:")
        print("  Super Admin:     admin@demo.local         / Admin123!")
        print()
        print("  Admin Tenant 1:  admin.autofix@demo.local / User123!")
        print("  Taller 1A:       taller.central@demo.local/ User123!")
        print("  Taller 1B:       taller.sur@demo.local    / User123!")
        print("  Mecanico 1:      mecanico.juan@demo.local / User123!")
        print("  Mecanico 2:      mecanico.pedro@demo.local/ User123!")
        print()
        print("  Admin Tenant 2:  admin.mecared@demo.local / User123!")
        print("  Taller 2:        taller.norte@demo.local  / User123!")
        print("  Mecanico 3:      mecanico.luis@demo.local / User123!")
        print()
        print("  Conductor 1:     conductor.ana@demo.local / User123!")
        print("  Conductor 2:     conductor.diego@demo.local/User123!")
        print("  Conductor 3:     conductor.sofia@demo.local/User123!")
        print()

    finally:
        db.close()


if __name__ == "__main__":
    main()
