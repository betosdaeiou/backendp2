from src.core.database import get_db
from src.core.security import SECRET_KEY, ALGORITHM
from src.modules.iam.models import Usuario, Rol, UsuarioTenant
from src.modules.iam.schemas import TokenData
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from sqlalchemy.orm import Session


oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")

def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    """Obtiene el usuario actual y le inyecta tenant_id y rol desde el JWT."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="No se pudieron validar las credenciales",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        correo: str = payload.get("sub")
        tenant_id = payload.get("tenant_id")
        rol_id = payload.get("rol_id")
        token_type = payload.get("type")

        if correo is None:
            raise credentials_exception
        # Rechazar tokens temporales de selección de tenant
        if token_type == "tenant_selection":
            raise credentials_exception

    except JWTError:
        raise credentials_exception
    
    user = db.query(Usuario).filter(Usuario.Correo == correo).first()
    if user is None:
        raise credentials_exception

    # Inyectar tenant_id y rol dinámicamente desde el JWT
    # para que current_user.tenant_id y current_user.rol sigan funcionando en todo el código
    user.tenant_id = tenant_id
    user.rol = None
    if rol_id is not None:
        rol = db.query(Rol).filter(Rol.Id == rol_id).first()
        user.rol = rol

    return user


def require_permission(required_permission: str):
    """Dependencia que verifica que el rol del usuario actual tenga el permiso requerido."""
    def permission_checker(current_user: Usuario = Depends(get_current_user)):
        if not current_user.rol:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Acceso denegado. El usuario no tiene un rol asignado."
            )
        
        permisos_usuario = [p.Nombre for p in current_user.rol.permisos]
        if required_permission not in permisos_usuario:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Acceso denegado. Se requiere el permiso: '{required_permission}'."
            )
        return current_user
    return permission_checker

from src.core.database import SessionLocal

def verify_token_ws(token: str) -> Usuario | None:
    """Verifica un token JWT para conexiones WebSocket y retorna el usuario con tenant_id inyectado."""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        correo: str = payload.get("sub")
        tenant_id = payload.get("tenant_id")
        rol_id = payload.get("rol_id")
        if correo is None:
            return None
    except JWTError:
        return None
    
    db = SessionLocal()
    try:
        user = db.query(Usuario).filter(Usuario.Correo == correo).first()
        if user:
            user.tenant_id = tenant_id
            user.rol = None
            if rol_id is not None:
                rol = db.query(Rol).filter(Rol.Id == rol_id).first()
                user.rol = rol
        return user
    finally:
        db.close()
