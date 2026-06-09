from src.core.database import get_db
from src.modules.iam.dependencies import get_current_user
from src.core.security import get_password_hash, verify_password
from src.shared.bitacora_util import registrar_bitacora, registrar_bitacora_background
from src.modules.iam.models import Rol, Usuario, UsuarioTenant, Permiso
from src.modules.saas.models import Tenant
from src.modules.catalog.models import Mecanico, Taller, Vehiculo, VehiculoConductor, Administrador, Conductor
from src.modules.catalog.schemas import (
    MecanicoOut, MecanicoRegistro, MecanicoUpdate,
    Vehiculo as VehiculoSchema, VehiculoCreate,
    ProfileOut, ProfileUpdate, AdminProfileData, ConductorProfileData, MecanicoProfileData, TallerProfileData, UbicacionUpdate, PasswordChange, TallerCreateInternal, TallerOut
)

from fastapi import APIRouter, Depends, HTTPException, status, Request, BackgroundTasks, UploadFile, File
from sqlalchemy.orm import Session, joinedload
from typing import List
import datetime
import os
import shutil
import uuid

# ─── VEHÍCULOS ───────────────────────────────────────────────────────────────

vehiculos_router = APIRouter(prefix="/vehiculos", tags=["Vehículos"])

@vehiculos_router.post("/", response_model=VehiculoSchema)
def registrar_vehiculo(
    vehiculo: VehiculoCreate, 
    db: Session = Depends(get_db), 
    current_user: Usuario = Depends(get_current_user)
):
    if not current_user.conductor:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, 
            detail="Debe tener un perfil de conductor para registrar vehículos"
        )
    
    db_vehiculo = None
    if vehiculo.Placa:
        db_vehiculo = db.query(Vehiculo).filter(Vehiculo.Placa == vehiculo.Placa).first()
    
    if db_vehiculo:
        if current_user.conductor not in db_vehiculo.conductores:
            fecha_actual = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            asociacion = VehiculoConductor(fechareg=fecha_actual, conductor_id=current_user.conductor.IdUsuario, vehiculo_id=db_vehiculo.Id)
            db.add(asociacion)
            db.commit()
            db.refresh(db_vehiculo)
        return db_vehiculo

    nuevo_vehiculo_data = vehiculo.model_dump() if hasattr(vehiculo, 'model_dump') else vehiculo.dict()
    db_vehiculo = Vehiculo(**nuevo_vehiculo_data)
    db.add(db_vehiculo)
    db.commit()
    db.refresh(db_vehiculo)
    
    fecha_actual = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    asociacion = VehiculoConductor(fechareg=fecha_actual, conductor_id=current_user.conductor.IdUsuario, vehiculo_id=db_vehiculo.Id)
    db.add(asociacion)
    db.commit()
    db.refresh(db_vehiculo)
    
    return db_vehiculo

@vehiculos_router.get("/mis-vehiculos", response_model=List[VehiculoSchema])
def obtener_mis_vehiculos(
    db: Session = Depends(get_db), 
    current_user: Usuario = Depends(get_current_user)
):
    if not current_user.conductor:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, 
            detail="Debe tener un perfil de conductor para ver sus vehículos"
        )
    return current_user.conductor.vehiculos


# ─── MECÁNICOS ───────────────────────────────────────────────────────────────

mecanicos_router = APIRouter(prefix="/mecanicos", tags=["Mecanicos"])

from datetime import datetime, time

@mecanicos_router.get("/")
def get_mecanicos_by_taller(db: Session = Depends(get_db), current_user: Usuario = Depends(get_current_user)):
    taller = db.query(Taller).filter(Taller.IdUsuario == current_user.Id).first()
    
    query = db.query(Mecanico).options(joinedload(Mecanico.usuario), joinedload(Mecanico.taller))
    
    if taller:
        mecanicos = query.filter(Mecanico.taller_id == taller.Id).all()
    elif current_user.rol and current_user.rol.Nombre in ['Administrador', 'Admin Tenant']:
        if current_user.tenant_id is None:
            mecanicos = query.all()
        else:
            mecanicos = query.filter(Mecanico.tenant_id == current_user.tenant_id).all()
    else:
        raise HTTPException(status_code=403, detail="No autorizado para visualizar mecánicos")
        
    result = []
    for m in mecanicos:
        fechanac_ms = None
        if m.usuario and m.usuario.Fechanac:
            try:
                # Fechanac is a date object. Convert to datetime then timestamp
                dt = datetime.combine(m.usuario.Fechanac, time.min)
                fechanac_ms = int(dt.timestamp() * 1000)
            except Exception:
                pass
                
        result.append({
            "id": m.id,
            "estado": m.estado,
            "taller_id": m.taller_id,
            "taller_nombre": m.taller.Nombre if m.taller else "No asignado",
            "nombre": m.usuario.Nombre if m.usuario else "Desconocido",
            "apellidos": m.usuario.Apellidos if m.usuario else "",
            "ci": m.usuario.CI if m.usuario else "",
            "extci": "",
            "fechanac": fechanac_ms,
            "correo": m.usuario.Correo if m.usuario else ""
        })
    return result

@mecanicos_router.post("/", response_model=MecanicoOut, status_code=status.HTTP_201_CREATED)
def create_mecanico(request: Request, background_tasks: BackgroundTasks, mecanico_data: MecanicoRegistro, db: Session = Depends(get_db), current_user: Usuario = Depends(get_current_user)):
    taller = db.query(Taller).filter(Taller.IdUsuario == current_user.Id).first()
    if not taller:
        raise HTTPException(status_code=403, detail="Debe ser un Taller registrado para crear mecánicos")

    if db.query(Usuario).filter(Usuario.Correo == mecanico_data.correo).first():
        raise HTTPException(status_code=400, detail="Este correo ya está registrado en el sistema")

    rol = db.query(Rol).filter(Rol.Nombre == 'Mecanico').first()
    if not rol:
        rol = Rol(Nombre='Mecanico')
        db.add(rol)
        db.commit()
        db.refresh(rol)

    hashed_pass = get_password_hash(mecanico_data.password)
    new_user = Usuario(
        Correo=mecanico_data.correo, 
        Password=hashed_pass,
        Nombre=mecanico_data.nombre,
        Apellidos=mecanico_data.apellidos,
        CI=mecanico_data.ci,
        Fechanac=mecanico_data.fechanac
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    # Crear membresía en el tenant actual
    if current_user.tenant_id is not None:
        membership = UsuarioTenant(
            usuario_id=new_user.Id,
            tenant_id=current_user.tenant_id,
            rol_id=rol.Id
        )
        db.add(membership)
        db.commit()

    nuevo_mecanico = Mecanico(
        id=new_user.Id,
        estado=mecanico_data.estado,
        taller_id=taller.Id,
        tenant_id=current_user.tenant_id
    )
    db.add(nuevo_mecanico)
    db.commit()
    db.refresh(nuevo_mecanico)

    background_tasks.add_task(
        registrar_bitacora_background,
        current_user.Id, "Crear Mecánico",
        f"Registró al mecánico {mecanico_data.nombre} {mecanico_data.apellidos}",
        request.client.host if request.client else "0.0.0.0"
    )
    return nuevo_mecanico

@mecanicos_router.put("/{mecanico_id}", response_model=MecanicoOut)
def update_mecanico(request: Request, background_tasks: BackgroundTasks, mecanico_id: int, m_update: MecanicoUpdate, db: Session = Depends(get_db), current_user: Usuario = Depends(get_current_user)):
    mecanico = db.query(Mecanico).filter(Mecanico.id == mecanico_id).first()
    if not mecanico:
        raise HTTPException(status_code=404, detail="Mecánico no encontrado")

    taller = db.query(Taller).filter(Taller.IdUsuario == current_user.Id).first()
    is_owner_taller = taller and mecanico.taller_id == taller.Id
    is_admin = current_user.rol and current_user.rol.Nombre == 'Administrador'
    is_self = hasattr(current_user, 'mecanico') and current_user.mecanico and current_user.mecanico.id == mecanico_id

    if not (is_owner_taller or is_admin or is_self):
        raise HTTPException(status_code=403, detail="No puedes editar mecánicos de otros talleres")

    if m_update.estado is not None:
        mecanico.estado = m_update.estado

    db.commit()
    db.refresh(mecanico)

    background_tasks.add_task(
        registrar_bitacora_background,
        current_user.Id, "Editar Mecánico",
        f"Editó al mecánico #{mecanico_id}",
        request.client.host if request.client else "0.0.0.0"
    )
    return mecanico

@mecanicos_router.delete("/{mecanico_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_mecanico(request: Request, background_tasks: BackgroundTasks, mecanico_id: int, db: Session = Depends(get_db), current_user: Usuario = Depends(get_current_user)):
    mecanico = db.query(Mecanico).filter(Mecanico.id == mecanico_id).first()
    if not mecanico:
        raise HTTPException(status_code=404, detail="Mecánico no encontrado")

    taller = db.query(Taller).filter(Taller.IdUsuario == current_user.Id).first()
    if not taller or mecanico.taller_id != taller.Id:
        if not (current_user.rol and current_user.rol.Nombre == 'Administrador'):
            raise HTTPException(status_code=403, detail="No puedes dar de baja técnicos que no te pertenecen")

    user_id = mecanico.id
    db.delete(mecanico)
    
    base_user = db.query(Usuario).filter(Usuario.Id == user_id).first()
    if base_user:
        db.delete(base_user)

    db.commit()

    background_tasks.add_task(
        registrar_bitacora_background,
        current_user.Id, "Eliminar Mecánico",
        f"Dio de baja al mecánico #{mecanico_id}",
        request.client.host if request.client else "0.0.0.0"
    )
    return None


# ─── PROFILE ─────────────────────────────────────────────────────────────────

profile_router = APIRouter(prefix="/profile", tags=["Perfil de Usuario"])

@profile_router.get("/me", response_model=ProfileOut)
def get_my_profile(
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user)
):
    rol_nombre = current_user.rol.Nombre if current_user.rol else None

    admin_data = None
    taller_data = None
    conductor_data = None
    mecanico_data = None

    if current_user.administrador:
        admin_data = AdminProfileData(Usuario=current_user.administrador.Usuario)

    taller = db.query(Taller).filter(Taller.IdUsuario == current_user.Id, Taller.tenant_id == current_user.tenant_id).first()
    
    if not taller and current_user.rol and current_user.rol.Nombre == "Admin Tenant" and current_user.tenant_id:
        taller = db.query(Taller).filter(Taller.tenant_id == current_user.tenant_id).first()

    if taller:
        taller_data = TallerProfileData(
            Id=taller.Id,
            Nombre=taller.Nombre,
            Direccion=taller.Direccion,
            Coordenadas=taller.Coordenadas,
            Cap=taller.Cap,
            Capmax=taller.Capmax
        )

    conductor = db.query(Conductor).filter(Conductor.IdUsuario == current_user.Id).first()
    if conductor:
        conductor_data = ConductorProfileData()

    mecanico = db.query(Mecanico).filter(Mecanico.id == current_user.Id, Mecanico.tenant_id == current_user.tenant_id).first()
    if mecanico:
        mecanico_data = MecanicoProfileData(
            id=mecanico.id,
            estado=mecanico.estado
        )

    from src.modules.saas.models import Tenant
    tenant_nombre = None
    tenant_balance = None
    if current_user.tenant_id:
        t_obj = db.query(Tenant).filter(Tenant.Id == current_user.tenant_id).first()
        if t_obj:
            tenant_nombre = t_obj.Nombre
            tenant_balance = t_obj.balance

    return ProfileOut(
        Id=current_user.Id,
        Correo=current_user.Correo,
        Nombre=current_user.Nombre,
        Apellidos=current_user.Apellidos,
        CI=current_user.CI,
        Fechanac=current_user.Fechanac,
        rol_nombre=rol_nombre,
        FotoPerfil=current_user.FotoPerfil,
        administrador=admin_data,
        taller=taller_data,
        conductor=conductor_data,
        mecanico=mecanico_data,
        tenant_nombre=tenant_nombre,
        tenant_balance=tenant_balance
    )

@profile_router.put("/me", response_model=ProfileOut)
def update_my_profile(
    request: Request,
    background_tasks: BackgroundTasks,
    profile_data: ProfileUpdate,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user)
):
    if profile_data.Correo and profile_data.Correo != current_user.Correo:
        existing = db.query(Usuario).filter(
            Usuario.Correo == profile_data.Correo,
            Usuario.Id != current_user.Id
        ).first()
        if existing:
            raise HTTPException(status_code=400, detail="Este correo ya está en uso por otro usuario")
        current_user.Correo = profile_data.Correo

    if profile_data.Password:
        current_user.Password = get_password_hash(profile_data.Password)

    if current_user.administrador and profile_data.admin_usuario is not None:
        current_user.administrador.Usuario = profile_data.admin_usuario

    if profile_data.Nombre is not None:
        current_user.Nombre = profile_data.Nombre
    if profile_data.Apellidos is not None:
        current_user.Apellidos = profile_data.Apellidos
    if profile_data.CI is not None:
        current_user.CI = profile_data.CI
    if profile_data.Fechanac is not None:
        current_user.Fechanac = profile_data.Fechanac

    t = db.query(Taller).filter(Taller.IdUsuario == current_user.Id, Taller.tenant_id == current_user.tenant_id).first()
    if t:
        if profile_data.taller_nombre is not None:
            t.Nombre = profile_data.taller_nombre
        if profile_data.taller_direccion is not None:
            t.Direccion = profile_data.taller_direccion
        if profile_data.taller_coordenadas is not None:
            t.Coordenadas = profile_data.taller_coordenadas
        if profile_data.taller_cap is not None:
            t.Cap = profile_data.taller_cap
        if profile_data.taller_capmax is not None:
            t.Capmax = profile_data.taller_capmax

    m = db.query(Mecanico).filter(Mecanico.id == current_user.Id, Mecanico.tenant_id == current_user.tenant_id).first()
    if m:
        if profile_data.mecanico_estado is not None:
            m.estado = profile_data.mecanico_estado

    db.commit()
    db.refresh(current_user)

    background_tasks.add_task(
        registrar_bitacora_background,
        current_user.Id, "Editar Perfil",
        f"El usuario {current_user.Correo} actualizó su perfil",
        request.client.host if request.client else "0.0.0.0"
    )

    return get_my_profile(db=db, current_user=current_user)

@profile_router.put("/me/ubicacion", response_model=ProfileOut)
def update_ubicacion_taller(
    request: Request,
    background_tasks: BackgroundTasks,
    ubicacion: UbicacionUpdate,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user)
):
    if not current_user.talleres or len(current_user.talleres) == 0:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Solo usuarios con perfil de Taller pueden actualizar la ubicación"
        )

    taller = current_user.talleres[0]
    taller.Coordenadas = ubicacion.Coordenadas
    if ubicacion.Direccion is not None:
        taller.Direccion = ubicacion.Direccion

    db.commit()
    db.refresh(current_user)

    background_tasks.add_task(
        registrar_bitacora_background,
        current_user.Id, "Actualizar Ubicación",
        f"El taller '{taller.Nombre}' actualizó su ubicación a {ubicacion.Coordenadas}",
        request.client.host if request.client else "0.0.0.0"
    )

    return get_my_profile(db=db, current_user=current_user)

@profile_router.put("/me/password", response_model=dict)
def update_my_password(
    request: Request,
    background_tasks: BackgroundTasks,
    password_data: PasswordChange,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user)
):
    if not verify_password(password_data.contrasena_actual, current_user.Password):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="La contraseña actual es incorrecta")

    current_user.Password = get_password_hash(password_data.nueva_contrasena)
    db.commit()

    background_tasks.add_task(
        registrar_bitacora_background,
        current_user.Id, "Cambio de Contraseña",
        f"El usuario {current_user.Correo} cambió su contraseña",
        request.client.host if request.client else "0.0.0.0"
    )

    return {"message": "Contraseña actualizada exitosamente"}

@profile_router.post("/me/avatar", response_model=ProfileOut)
def upload_avatar(
    request: Request,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user)
):
    if not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="El archivo debe ser una imagen")

    os.makedirs("uploads/avatars", exist_ok=True)
    file_extension = file.filename.split(".")[-1]
    unique_filename = f"{uuid.uuid4()}.{file_extension}"
    file_path = os.path.join("uploads", "avatars", unique_filename)

    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    if current_user.FotoPerfil and os.path.exists(current_user.FotoPerfil):
        try:
            os.remove(current_user.FotoPerfil)
        except Exception:
            pass

    current_user.FotoPerfil = file_path.replace("\\", "/")
    db.commit()
    db.refresh(current_user)

    background_tasks.add_task(
        registrar_bitacora_background,
        current_user.Id, "Actualizar Avatar",
        f"El usuario {current_user.Correo} actualizó su foto de perfil",
        request.client.host if request.client else "0.0.0.0"
    )

    return get_my_profile(db=db, current_user=current_user)

@profile_router.delete("/me", status_code=status.HTTP_204_NO_CONTENT)
def delete_my_account(
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user)
):
    if current_user.rol and current_user.rol.Nombre == 'Administrador':
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Un administrador no puede eliminar su propia cuenta desde aquí")

    correo_eliminado = current_user.Correo
    user_id = current_user.Id

    db.query(Conductor).filter(Conductor.IdUsuario == user_id).delete()
    db.query(Taller).filter(Taller.IdUsuario == user_id).delete()
    db.query(Mecanico).filter(Mecanico.id == user_id).delete()

    db.delete(current_user)
    db.commit()

    background_tasks.add_task(
        registrar_bitacora_background,
        user_id, "Eliminar Cuenta",
        f"El usuario {correo_eliminado} eliminó su propia cuenta",
        request.client.host if request.client else "0.0.0.0"
    )

    return None


# ─── TALLERES (SUCURSALES) ───────────────────────────────────────────────────────────────

talleres_router = APIRouter(prefix="/talleres", tags=["Talleres"])

@talleres_router.get("/mis-sucursales", response_model=List[TallerOut])
def get_mis_sucursales(db: Session = Depends(get_db), current_user: Usuario = Depends(get_current_user)):
    if not current_user.tenant_id:
        raise HTTPException(status_code=403, detail="No pertenece a ningn tenant")
    
    # Validar si tiene rol de Administrador o Admin Tenant
    if not current_user.rol or current_user.rol.Nombre not in ["Administrador", "Admin Tenant"]:
        raise HTTPException(status_code=403, detail="No autorizado para ver todas las sucursales")

    talleres = db.query(Taller).filter(Taller.tenant_id == current_user.tenant_id).all()
    return talleres

@talleres_router.post("/", response_model=TallerOut, status_code=status.HTTP_201_CREATED)
def create_sucursal(
    request: Request, 
    background_tasks: BackgroundTasks, 
    taller_data: TallerCreateInternal, 
    db: Session = Depends(get_db), 
    current_user: Usuario = Depends(get_current_user)
):
    if not current_user.tenant_id:
        raise HTTPException(status_code=403, detail="Debe pertenecer a un tenant para crear sucursales")
        
    if not current_user.rol or current_user.rol.Nombre not in ["Administrador", "Admin Tenant"]:
        raise HTTPException(status_code=403, detail="No autorizado para crear sucursales")

    rol = db.query(Rol).filter(Rol.Nombre == "Taller").first()
    if not rol:
        rol = Rol(Nombre="Taller")
        db.add(rol)
        db.commit()
        db.refresh(rol)

    if db.query(Usuario).filter(Usuario.Correo == taller_data.Correo).first():
        raise HTTPException(status_code=400, detail="El correo de la sucursal ya est en uso")

    hashed_pass = get_password_hash(taller_data.Password)
    new_user = Usuario(Correo=taller_data.Correo, Password=hashed_pass)
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    # Crear membresa en el tenant actual
    membership = UsuarioTenant(
        usuario_id=new_user.Id,
        tenant_id=current_user.tenant_id,
        rol_id=rol.Id
    )
    db.add(membership)
    db.commit()

    nuevo_taller = Taller(
        IdUsuario=new_user.Id,
        Nombre=taller_data.Nombre,
        Direccion=taller_data.Direccion,
        Coordenadas=taller_data.Coordenadas,
        Cap=taller_data.Cap,
        Capmax=taller_data.Capmax,
        tenant_id=current_user.tenant_id
    )
    db.add(nuevo_taller)
    db.commit()
    db.refresh(nuevo_taller)

    registrar_bitacora_background(
        background_tasks, db, "Crear Sucursal", 
        f"Se cre la sucursal {taller_data.Nombre}", 
        current_user.Id, current_user.tenant_id,
        request.client.host if request.client else "0.0.0.0"
    )

    return nuevo_taller

