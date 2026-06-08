from src.core.database import get_db
from src.core.security import SECRET_KEY, ALGORITHM
from src.modules.iam.models import Usuario, Rol
from src.modules.iam.schemas import TokenData
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from sqlalchemy.orm import Session


oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")

def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
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
        if correo is None:
            raise credentials_exception
        token_data = TokenData(correo=correo, tenant_id=tenant_id, rol_id=rol_id)
    except JWTError:
        raise credentials_exception
    
    user = db.query(Usuario).filter(Usuario.Correo == token_data.correo).first()
    if user is None:
        raise credentials_exception

    # Inyectar tenant_id y rol desde el JWT
    user.tenant_id = tenant_id
    user.rol = None
    if rol_id is not None:
        rol = db.query(Rol).filter(Rol.Id == rol_id).first()
        user.rol = rol

    return user
