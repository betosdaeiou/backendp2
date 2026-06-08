from src.core.database import get_db
from src.modules.iam.dependencies import get_current_user, require_permission
from src.core.security import create_access_token, get_password_hash, verify_password, ACCESS_TOKEN_EXPIRE_MINUTES, SECRET_KEY, ALGORITHM
from src.shared.bitacora_util import registrar_bitacora, registrar_bitacora_background
from src.shared.email_util import enviar_email_reset
from src.modules.iam.models import Permiso, Rol, Usuario, UsuarioTenant
from src.modules.catalog.models import Administrador, Conductor, Taller
from src.modules.catalog.schemas import ConductorRegistro, TallerRegistro
from src.modules.saas.models import Tenant
from src.modules.iam.schemas import (
    MensajeResponse, PasswordReset, PasswordResetRequest, Token, UsuarioCreate,
    Rol as RolSchema, Usuario as UsuarioSchema, UsuarioUpdate,
    Permiso as PermisoSchema, RolCreate, FCMTokenUpdate,
    LoginResponse, TenantOption, TenantSelectionPayload
)

from fastapi import APIRouter, Depends, HTTPException, status, Request, BackgroundTasks
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from datetime import timedelta
from typing import Annotated, List


router = APIRouter(tags=["IAM - Seguridad y Accesos"])

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")

# ─── AUTHENTICATION ──────────────────────────────────────────────────────────

auth_router = APIRouter(prefix="/auth", tags=["Authentication"])

@auth_router.post("/login", response_model=LoginResponse)
def login_for_access_token(request: Request, background_tasks: BackgroundTasks, form_data: Annotated[OAuth2PasswordRequestForm, Depends()], db: Session = Depends(get_db)):
    """Login centralizado con selección de tenant.
    
    - Si el usuario no tiene tenants (super admin): devuelve JWT final con tenant_id=null.
    - Si el usuario tiene 1 tenant: devuelve JWT final directamente.
    - Si el usuario tiene 2+ tenants: devuelve un token temporal y la lista de tenants para elegir.
    """
    user = db.query(Usuario).filter(Usuario.Correo == form_data.username).first()
    
    if not user or not verify_password(form_data.password, user.Password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Correo electrónico o contraseña incorrectos",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    memberships = user.tenants  # Lista de UsuarioTenant

    # Caso 1: Usuario global (sin tenants, ej. Super Admin o Conductor)
    if len(memberships) == 0:
        if hasattr(user, 'administrador') and user.administrador:
            rol = db.query(Rol).filter(Rol.Nombre == "Administrador").first()
            role_type = "super admin"
        elif hasattr(user, 'conductor') and user.conductor:
            rol = db.query(Rol).filter(Rol.Nombre == "Conductor").first()
            role_type = "conductor global"
        else:
            raise HTTPException(status_code=403, detail="El usuario no tiene roles asignados")

        rol_id = rol.Id if rol else None
        role_name = rol.Nombre if rol else None
        permisos_list = [p.Nombre for p in rol.permisos] if rol and rol.permisos else []

        access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = create_access_token(
            data={"sub": user.Correo, "tenant_id": None, "rol_id": rol_id},
            expires_delta=access_token_expires
        )
        background_tasks.add_task(
            registrar_bitacora_background,
            user.Id, "Inicio de Sesión",
            f"El usuario {user.Correo} inició sesión ({role_type})",
            request.client.host if request.client else "0.0.0.0",
            None
        )
        return LoginResponse(
            access_token=access_token,
            token_type="bearer",
            role=role_name,
            permisos=permisos_list,
            tenant_id=None,
            requires_tenant_selection=False
        )

    # Caso 2: Un solo tenant → login directo
    if len(memberships) == 1:
        m = memberships[0]
        role_name = m.rol.Nombre if m.rol else None
        permisos_list = [p.Nombre for p in m.rol.permisos] if m.rol and m.rol.permisos else []
        
        access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = create_access_token(
            data={"sub": user.Correo, "tenant_id": m.tenant_id, "rol_id": m.rol_id},
            expires_delta=access_token_expires
        )
        background_tasks.add_task(
            registrar_bitacora_background,
            user.Id, "Inicio de Sesión",
            f"El usuario {user.Correo} inició sesión en tenant {m.tenant.Nombre}",
            request.client.host if request.client else "0.0.0.0"
        )
        return LoginResponse(
            access_token=access_token,
            token_type="bearer",
            role=role_name,
            permisos=permisos_list,
            tenant_id=m.tenant_id,
            requires_tenant_selection=False
        )

    # Caso 3: Múltiples tenants → token temporal + lista para elegir
    temp_token = create_access_token(
        data={"sub": user.Correo, "type": "tenant_selection"},
        expires_delta=timedelta(minutes=5)
    )
    tenant_options = [
        TenantOption(
            id=m.tenant_id,
            nombre=m.tenant.Nombre,
            logo=m.tenant.LogoUrl,
            rol=m.rol.Nombre if m.rol else "Sin Rol"
        )
        for m in memberships
    ]
    return LoginResponse(
        requires_tenant_selection=True,
        temp_token=temp_token,
        tenants=tenant_options
    )


@auth_router.post("/select-tenant", response_model=Token)
def select_tenant(
    request: Request,
    background_tasks: BackgroundTasks,
    payload: TenantSelectionPayload,
    db: Session = Depends(get_db)
):
    """Segundo paso del login: seleccionar un tenant cuando el usuario tiene múltiples opciones."""
    from jose import JWTError, jwt as jose_jwt
    
    # 1. Validar el token temporal
    try:
        token_data = jose_jwt.decode(payload.temp_token, SECRET_KEY, algorithms=[ALGORITHM])
        correo = token_data.get("sub")
        token_type = token_data.get("type")

        if not correo or token_type != "tenant_selection":
            raise HTTPException(status_code=400, detail="Token temporal inválido")
    except JWTError:
        raise HTTPException(status_code=400, detail="Token temporal inválido o expirado")

    # 2. Buscar usuario y su membresía en el tenant seleccionado
    user = db.query(Usuario).filter(Usuario.Correo == correo).first()
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")

    membership = db.query(UsuarioTenant).filter(
        UsuarioTenant.usuario_id == user.Id,
        UsuarioTenant.tenant_id == payload.tenant_id
    ).first()

    if not membership:
        raise HTTPException(status_code=403, detail="No tienes acceso a este tenant")

    # 3. Generar JWT final con tenant_id y rol_id
    role_name = membership.rol.Nombre if membership.rol else None
    permisos_list = [p.Nombre for p in membership.rol.permisos] if membership.rol and membership.rol.permisos else []

    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.Correo, "tenant_id": membership.tenant_id, "rol_id": membership.rol_id},
        expires_delta=access_token_expires
    )

    background_tasks.add_task(
        registrar_bitacora_background,
        user.Id, "Inicio de Sesión",
        f"El usuario {user.Correo} seleccionó tenant {membership.tenant.Nombre}",
        request.client.host if request.client else "0.0.0.0"
    )

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "role": role_name,
        "permisos": permisos_list,
        "tenant_id": membership.tenant_id
    }


@auth_router.post("/registrar", response_model=dict)
def register_user(usuario: UsuarioCreate, db: Session = Depends(get_db)):
    """Registra un nuevo usuario y opcionalmente lo asocia a un tenant con un rol."""
    rol = db.query(Rol).filter(Rol.Id == usuario.IdRol).first()
    if not rol:
        raise HTTPException(status_code=400, detail="El rol especificado no existe")
    
    db_user = db.query(Usuario).filter(Usuario.Correo == usuario.Correo).first()
    if db_user:
        raise HTTPException(status_code=400, detail="Este correo ya está registrado")
    
    hashed_password = get_password_hash(usuario.Password)
    new_user = Usuario(Correo=usuario.Correo, Password=hashed_password)
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    # Si se proporcionó un tenant_id, crear la membresía
    if usuario.tenant_id is not None:
        tenant = db.query(Tenant).filter(Tenant.Id == usuario.tenant_id).first()
        if not tenant:
            raise HTTPException(status_code=400, detail="El tenant especificado no existe")
        membership = UsuarioTenant(
            usuario_id=new_user.Id,
            tenant_id=usuario.tenant_id,
            rol_id=usuario.IdRol
        )
        db.add(membership)
        db.commit()

    return {"message": "Usuario registrado exitosamente"}

@auth_router.post("/registrar-conductor", response_model=dict)
def register_conductor(request: Request, background_tasks: BackgroundTasks, conductor_data: ConductorRegistro, db: Session = Depends(get_db)):
    """Registra un conductor global (no requiere tenant_id)."""
    rol = db.query(Rol).filter(Rol.Nombre == "Conductor").first()
    if not rol:
        rol = Rol(Nombre="Conductor")
        db.add(rol)
        db.commit()
        db.refresh(rol)

    if db.query(Usuario).filter(Usuario.Correo == conductor_data.Correo).first():
        raise HTTPException(status_code=400, detail="Este correo ya está registrado en el sistema")

    hashed_pass = get_password_hash(conductor_data.Password)
    new_user = Usuario(
        Correo=conductor_data.Correo, 
        Password=hashed_pass,
        Nombre=conductor_data.Nombre,
        Apellidos=conductor_data.Apellidos,
        CI=conductor_data.CI,
        Fechanac=conductor_data.Fechanac
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    nuevo_conductor = Conductor(IdUsuario=new_user.Id)
    db.add(nuevo_conductor)
    db.commit()

    background_tasks.add_task(
        registrar_bitacora_background,
        new_user.Id, "Registro",
        f"Nuevo conductor registrado: {conductor_data.Nombre} {conductor_data.Apellidos}",
        request.client.host if request.client else "0.0.0.0"
    )
    return {"message": "Conductor registrado exitosamente"}

@auth_router.post("/registrar-taller", response_model=dict)
def register_taller(request: Request, background_tasks: BackgroundTasks, taller_data: TallerRegistro, db: Session = Depends(get_db)):
    """Registra un taller. Requiere tenant_id en el body."""
    if not hasattr(taller_data, 'tenant_id') or taller_data.tenant_id is None:
        raise HTTPException(status_code=400, detail="Se requiere un tenant_id para registrar un taller")

    tenant = db.query(Tenant).filter(Tenant.Id == taller_data.tenant_id).first()
    if not tenant:
        raise HTTPException(status_code=400, detail="El tenant especificado no existe")

    rol = db.query(Rol).filter(Rol.Nombre == "Taller").first()
    if not rol:
        rol = Rol(Nombre="Taller")
        permiso = db.query(Permiso).filter(Permiso.Nombre == "Gestionar Mecanicos").first()
        if permiso:
            rol.permisos.append(permiso)
        db.add(rol)
        db.commit()
        db.refresh(rol)

    if db.query(Usuario).filter(Usuario.Correo == taller_data.Correo).first():
        raise HTTPException(status_code=400, detail="Este correo ya está registrado por otra cuenta")

    hashed_pass = get_password_hash(taller_data.Password)
    new_user = Usuario(Correo=taller_data.Correo, Password=hashed_pass)
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    # Crear membresía en el tenant
    membership = UsuarioTenant(
        usuario_id=new_user.Id,
        tenant_id=taller_data.tenant_id,
        rol_id=rol.Id
    )
    db.add(membership)
    db.commit()

    nuevo_taller = Taller(
        IdUsuario=new_user.Id,
        Nombre=taller_data.Nombre,
        Direccion=taller_data.Direccion,
        Coordenadas=taller_data.Coordenadas,
        Cap=taller_data.Cap if taller_data.Cap is not None else 0,
        Capmax=taller_data.Capmax if taller_data.Capmax is not None else 10
    )
    db.add(nuevo_taller)
    db.commit()

    background_tasks.add_task(
        registrar_bitacora_background,
        new_user.Id, "Registro",
        f"Nuevo taller registrado: {taller_data.Nombre}",
        request.client.host if request.client else "0.0.0.0"
    )
    
    return {"message": "Taller registrado exitosamente. Ahora puede iniciar sesión."}


# --- Recuperación de Contraseña ---

@auth_router.post("/solicitar-reset", response_model=MensajeResponse)
def solicitar_reset_password(payload: PasswordResetRequest, db: Session = Depends(get_db)):
    """Envía un correo con un link para restablecer la contraseña."""
    user = db.query(Usuario).filter(Usuario.Correo == payload.correo).first()

    if not user:
        return {"message": "Si el correo está registrado, recibirás un enlace para restablecer tu contraseña."}

    reset_token = create_access_token(
        data={"sub": user.Correo, "type": "password_reset"},
        expires_delta=timedelta(minutes=30)
    )

    try:
                enviar_email_reset(user.Correo, reset_token)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al enviar el correo: {str(e)}"
        )

    return {"message": "Si el correo está registrado, recibirás un enlace para restablecer tu contraseña."}


@auth_router.post("/restablecer-password", response_model=MensajeResponse)
def restablecer_password(payload: PasswordReset, db: Session = Depends(get_db)):
    """Restablece la contraseña usando el token enviado por correo."""
    from jose import JWTError, jwt
    
    try:
        token_data = jwt.decode(payload.token, SECRET_KEY, algorithms=[ALGORITHM])
        correo = token_data.get("sub")
        token_type = token_data.get("type")

        if not correo or token_type != "password_reset":
            raise HTTPException(status_code=400, detail="Token inválido")

    except JWTError:
        raise HTTPException(status_code=400, detail="Token inválido o expirado")

    user = db.query(Usuario).filter(Usuario.Correo == correo).first()
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")

    user.Password = get_password_hash(payload.nueva_password)
    db.commit()

    return {"message": "Contraseña actualizada exitosamente. Ya puedes iniciar sesión."}


# ─── USERS (CRUD) ────────────────────────────────────────────────────────────

users_router = APIRouter(prefix="/users", tags=["Usuarios"])

@users_router.get("/", response_model=List[UsuarioSchema])
def get_users(
    db: Session = Depends(get_db), 
    current_user: Usuario = Depends(require_permission("Gestionar Usuarios")),
    skip: int = 0, 
    limit: int = 100
):
    """Lista usuarios. Si el usuario tiene tenant_id, filtra por ese tenant."""
    if current_user.tenant_id is not None:
        # Obtener IDs de usuarios que pertenecen al mismo tenant
        user_ids = [
            ut.usuario_id for ut in
            db.query(UsuarioTenant).filter(UsuarioTenant.tenant_id == current_user.tenant_id).all()
        ]
        users = db.query(Usuario).filter(Usuario.Id.in_(user_ids)).offset(skip).limit(limit).all()
    else:
        users = db.query(Usuario).offset(skip).limit(limit).all()

    # Mapear memberships
    result = []
    for u in users:
        memberships = []
        for ut in u.tenants:
            if current_user.tenant_id is not None and ut.tenant_id != current_user.tenant_id:
                continue
            memberships.append({
                "tenant_id": ut.tenant_id,
                "tenant_nombre": ut.tenant.Nombre if ut.tenant else "Desconocido",
                "rol_id": ut.rol_id,
                "rol_nombre": ut.rol.Nombre if ut.rol else "Desconocido"
            })
        
        user_dict = {
            "Id": u.Id,
            "Correo": u.Correo,
            "memberships": memberships
        }
        result.append(user_dict)
        
    return result

@users_router.get("/roles", response_model=List[RolSchema])
def get_roles_for_users(
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(require_permission("Gestionar Usuarios"))
):
    roles = db.query(Rol).all()
    return roles

@users_router.post("/", response_model=UsuarioSchema, status_code=status.HTTP_201_CREATED)
def create_user(
    request: Request,
    background_tasks: BackgroundTasks,
    user_data: UsuarioCreate, 
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(require_permission("Gestionar Usuarios"))
):
    """Crea un nuevo usuario y lo asocia al tenant del usuario actual."""
    if db.query(Usuario).filter(Usuario.Correo == user_data.Correo).first():
        raise HTTPException(status_code=400, detail="Este correo ya está registrado")
    
    rol = db.query(Rol).filter(Rol.Id == user_data.IdRol).first()
    if not rol:
        raise HTTPException(status_code=400, detail="El rol especificado no existe")
    
    hashed_password = get_password_hash(user_data.Password)
    new_user = Usuario(
        Correo=user_data.Correo, 
        Password=hashed_password
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    # Crear membresía en el tenant del usuario actual (si tiene)
    target_tenant_id = user_data.tenant_id if user_data.tenant_id is not None else current_user.tenant_id
    if target_tenant_id is not None:
        membership = UsuarioTenant(
            usuario_id=new_user.Id,
            tenant_id=target_tenant_id,
            rol_id=user_data.IdRol
        )
        db.add(membership)
        db.commit()

    background_tasks.add_task(
        registrar_bitacora_background,
        current_user.Id, "Crear Usuario",
        f"Creó el usuario {new_user.Correo} con rol {rol.Nombre}",
        request.client.host if request.client else "0.0.0.0"
    )
    return new_user

@users_router.put("/{user_id}", response_model=UsuarioSchema)
def update_user(
    request: Request,
    background_tasks: BackgroundTasks,
    user_id: int, 
    user_data: UsuarioUpdate, 
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(require_permission("Gestionar Usuarios"))
):
    # Verificar que el usuario existe y pertenece al mismo tenant
    db_user = db.query(Usuario).filter(Usuario.Id == user_id).first()
    if not db_user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")

    # Si el usuario actual tiene tenant, verificar que el usuario a editar pertenezca al mismo tenant
    if current_user.tenant_id is not None:
        membership = db.query(UsuarioTenant).filter(
            UsuarioTenant.usuario_id == user_id,
            UsuarioTenant.tenant_id == current_user.tenant_id
        ).first()
        if not membership:
            raise HTTPException(status_code=404, detail="Usuario no encontrado")
    
    if user_data.Correo and user_data.Correo != db_user.Correo:
        if db.query(Usuario).filter(Usuario.Correo == user_data.Correo).first():
            raise HTTPException(status_code=400, detail="El correo ya se encuentra en uso por otro usuario")
        db_user.Correo = user_data.Correo
        
    if user_data.Password:
        db_user.Password = get_password_hash(user_data.Password)
        
    # Actualizar el rol en la membresía del tenant actual
    if user_data.IdRol is not None and current_user.tenant_id is not None:
        rol = db.query(Rol).filter(Rol.Id == user_data.IdRol).first()
        if not rol:
            raise HTTPException(status_code=400, detail="El rol especificado no existe")
        membership = db.query(UsuarioTenant).filter(
            UsuarioTenant.usuario_id == user_id,
            UsuarioTenant.tenant_id == current_user.tenant_id
        ).first()
        if membership:
            membership.rol_id = user_data.IdRol
        
    db.commit()
    db.refresh(db_user)

    background_tasks.add_task(
        registrar_bitacora_background,
        current_user.Id, "Editar Usuario",
        f"Editó al usuario #{user_id} ({db_user.Correo})",
        request.client.host if request.client else "0.0.0.0"
    )
    return db_user

@users_router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(
    request: Request,
    background_tasks: BackgroundTasks,
    user_id: int, 
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(require_permission("Gestionar Usuarios"))
):
    db_user = db.query(Usuario).filter(Usuario.Id == user_id).first()
    if not db_user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")

    # Si tiene tenant, verificar pertenencia
    if current_user.tenant_id is not None:
        membership = db.query(UsuarioTenant).filter(
            UsuarioTenant.usuario_id == user_id,
            UsuarioTenant.tenant_id == current_user.tenant_id
        ).first()
        if not membership:
            raise HTTPException(status_code=404, detail="Usuario no encontrado")
    
    if db_user.Id == current_user.Id:
        raise HTTPException(status_code=400, detail="No puedes eliminar tu propia cuenta de administrador")
    
    correo_eliminado = db_user.Correo

    db.query(Administrador).filter(Administrador.IdUsuario == user_id).delete()
    db.query(Conductor).filter(Conductor.IdUsuario == user_id).delete()
    db.query(Taller).filter(Taller.IdUsuario == user_id).delete()
    db.query(UsuarioTenant).filter(UsuarioTenant.usuario_id == user_id).delete()

    db.delete(db_user)
    db.commit()

    background_tasks.add_task(
        registrar_bitacora_background,
        current_user.Id, "Eliminar Usuario",
        f"Eliminó al usuario #{user_id} ({correo_eliminado})",
        request.client.host if request.client else "0.0.0.0"
    )
    return None


# ─── ROLES & PERMISOS ────────────────────────────────────────────────────────

roles_router = APIRouter(prefix="/roles", tags=["Roles y Permisos"])

@roles_router.get("/", response_model=List[RolSchema])
def get_roles(db: Session = Depends(get_db)):
    """Extrae todos los roles junto con sus permisos asignados."""
    roles = db.query(Rol).all()
    return roles

@roles_router.post("/", response_model=RolSchema, status_code=status.HTTP_201_CREATED)
def create_role(request: Request, background_tasks: BackgroundTasks, role_data: RolCreate, db: Session = Depends(get_db), current_user: Usuario = Depends(require_permission("Gestionar Roles"))):
    if db.query(Rol).filter(Rol.Nombre == role_data.Nombre).first():
        raise HTTPException(status_code=400, detail="Ya existe un rol con ese nombre")
        
    nuevo_rol = Rol(Nombre=role_data.Nombre)
    db.add(nuevo_rol)
    db.commit()
    db.refresh(nuevo_rol)

    background_tasks.add_task(
        registrar_bitacora_background,
        current_user.Id, "Crear Rol",
        f"Creó el rol '{nuevo_rol.Nombre}'",
        request.client.host if request.client else "0.0.0.0"
    )
    return nuevo_rol

@roles_router.put("/{role_id}", response_model=RolSchema)
def update_role(request: Request, background_tasks: BackgroundTasks, role_id: int, role_data: RolCreate, db: Session = Depends(get_db), current_user: Usuario = Depends(require_permission("Gestionar Roles"))):
    db_rol = db.query(Rol).filter(Rol.Id == role_id).first()
    if not db_rol:
        raise HTTPException(status_code=404, detail="Rol no encontrado")
        
    if role_data.Nombre != db_rol.Nombre:
        if db.query(Rol).filter(Rol.Nombre == role_data.Nombre).first():
            raise HTTPException(status_code=400, detail="Ya existe un rol con ese nombre")
        db_rol.Nombre = role_data.Nombre
        db.commit()
        db.refresh(db_rol)
        
    background_tasks.add_task(
        registrar_bitacora_background,
        current_user.Id, "Editar Rol",
        f"Editó el rol #{role_id} a '{db_rol.Nombre}'",
        request.client.host if request.client else "0.0.0.0"
    )
    return db_rol

@roles_router.delete("/{role_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_role(request: Request, background_tasks: BackgroundTasks, role_id: int, db: Session = Depends(get_db), current_user: Usuario = Depends(require_permission("Gestionar Roles"))):
    db_rol = db.query(Rol).filter(Rol.Id == role_id).first()
    if not db_rol:
        raise HTTPException(status_code=404, detail="Rol no encontrado")
        
    # Verificar si hay membresías usando este rol
    memberships_count = db.query(UsuarioTenant).filter(UsuarioTenant.rol_id == role_id).count()
    if memberships_count > 0:
        raise HTTPException(
            status_code=400, 
            detail=f"Imposible eliminar. El rol está actualmente asignado a {memberships_count} usuario(s)."
        )
        
    nombre_eliminado = db_rol.Nombre
    db_rol.permisos.clear()
    
    db.delete(db_rol)
    db.commit()

    background_tasks.add_task(
        registrar_bitacora_background,
        current_user.Id, "Eliminar Rol",
        f"Eliminó el rol '{nombre_eliminado}'",
        request.client.host if request.client else "0.0.0.0"
    )
    return None

@roles_router.get("/permisos/todos", response_model=List[PermisoSchema])
def get_all_permisos(db: Session = Depends(get_db)):
    return db.query(Permiso).all()

@roles_router.post("/{role_id}/permisos/{permiso_id}", status_code=status.HTTP_201_CREATED)
def assign_permiso_to_role(request: Request, background_tasks: BackgroundTasks, role_id: int, permiso_id: int, db: Session = Depends(get_db), current_user: Usuario = Depends(require_permission("Gestionar Roles"))):
    db_rol = db.query(Rol).filter(Rol.Id == role_id).first()
    if not db_rol:
        raise HTTPException(status_code=404, detail="Rol no encontrado")
        
    db_perm = db.query(Permiso).filter(Permiso.Id == permiso_id).first()
    if not db_perm:
        raise HTTPException(status_code=404, detail="Permiso no encontrado")
        
    if db_perm not in db_rol.permisos:
        db_rol.permisos.append(db_perm)
        db.commit()

    background_tasks.add_task(
        registrar_bitacora_background,
        current_user.Id, "Asignar Permiso",
        f"Asignó permiso '{db_perm.Nombre}' al rol '{db_rol.Nombre}'",
        request.client.host if request.client else "0.0.0.0"
    )
    return {"message": "Permiso asignado"}

@roles_router.delete("/{role_id}/permisos/{permiso_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_permiso_from_role(request: Request, background_tasks: BackgroundTasks, role_id: int, permiso_id: int, db: Session = Depends(get_db), current_user: Usuario = Depends(require_permission("Gestionar Roles"))):
    db_rol = db.query(Rol).filter(Rol.Id == role_id).first()
    if not db_rol:
        raise HTTPException(status_code=404, detail="Rol no encontrado")
        
    db_perm = db.query(Permiso).filter(Permiso.Id == permiso_id).first()
    if not db_perm:
        raise HTTPException(status_code=404, detail="Permiso no encontrado")
        
    if db_perm in db_rol.permisos:
        db_rol.permisos.remove(db_perm)
        db.commit()

    background_tasks.add_task(
        registrar_bitacora_background,
        current_user.Id, "Revocar Permiso",
        f"Revocó permiso '{db_perm.Nombre}' del rol '{db_rol.Nombre}'",
        request.client.host if request.client else "0.0.0.0"
    )
    return None
