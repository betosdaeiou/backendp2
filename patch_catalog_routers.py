import os
import re

path = 'src/modules/catalog/routers.py'

with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

# Add imports
imports_pattern = "from src.modules.iam.models import Rol, Usuario, UsuarioTenant"
new_imports = "from src.modules.iam.models import Rol, Usuario, UsuarioTenant, Permiso, Tenant"
content = content.replace(imports_pattern, new_imports)

schema_imports_pattern = "MecanicoProfileData, TallerProfileData, UbicacionUpdate, PasswordChange"
new_schema_imports = "MecanicoProfileData, TallerProfileData, UbicacionUpdate, PasswordChange, TallerCreateInternal, TallerOut"
content = content.replace(schema_imports_pattern, new_schema_imports)

# Add the new endpoints under some new router, or just use a new talleres_router
new_router_code = """

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

"""

# Insert new router code before the file ends
# Or find a place to put it
# It's better to just append it and then import it in main.py
if "talleres_router =" not in content:
    content += new_router_code
    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)
    print("talleres_router added to catalog/routers.py")
else:
    print("talleres_router already exists")
