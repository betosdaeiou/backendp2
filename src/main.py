from fastapi import FastAPI, Depends
from sqlalchemy.orm import Session
from src.core.database import engine, Base, get_db

import os

# Crear todas las tablas en la base de datos
Base.metadata.create_all(bind=engine)

from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

app = FastAPI(
    title="Backend API - Plataforma SaaS Multi-Tenant de Emergencias Vehiculares",
    description="Arquitectura Modular Multi-Tenant con FastAPI, WebSockets y Offline-Sync",
    version="2.0.0"
)

# Habilitar CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── IMPORTS DE ROUTERS ───────────────────────────────────────────────────────

from src.modules.iam.routers import auth_router, users_router, roles_router
from src.modules.saas.routers import router as saas_router
from src.modules.catalog.routers import mecanicos_router, vehiculos_router, profile_router, talleres_router
from src.modules.operations.routers.incidentes import router as incidentes_router
from src.modules.operations.routers.chat import router as chat_router
from src.modules.operations.routers.bitacora import router as bitacora_router
from src.modules.operations.routers.notificaciones import router as notificaciones_router
from src.modules.operations.routers.pagos import router as pagos_router
from src.modules.operations.routers.ia import router as ia_router
from src.modules.analytics.routers import router as analytics_router
from src.modules.offline_sync.routers import router as offline_sync_router
from src.modules.realtime.sockets import router as realtime_router

# ─── INCLUSIÓN DE ROUTERS ─────────────────────────────────────────────────────

# IAM
app.include_router(auth_router)
app.include_router(users_router)
app.include_router(roles_router)

# SaaS
app.include_router(saas_router)

# Catalog
app.include_router(mecanicos_router)
app.include_router(vehiculos_router)
app.include_router(profile_router)
app.include_router(talleres_router)

# Operations
app.include_router(incidentes_router)
app.include_router(chat_router)
app.include_router(bitacora_router)
app.include_router(notificaciones_router)
app.include_router(pagos_router)
app.include_router(ia_router)

# Analytics
app.include_router(analytics_router)

# Offline Sync
app.include_router(offline_sync_router)

# Realtime (WebSockets)
app.include_router(realtime_router)


# Servir archivos estáticos (fotos de incidentes)
os.makedirs("uploads", exist_ok=True)
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")

@app.get("/")
def read_root():
    return {"message": "Bienvenido a la API del proyecto SaaS Multi-Tenant"}

@app.get("/health")
def health_check(db: Session = Depends(get_db)):
    try:
        from sqlalchemy import text
        db.execute(text("SELECT 1"))
        return {"status": "ok", "database": "connected"}
    except Exception as e:
        return {"status": "error", "database": "disconnected", "details": str(e)}
