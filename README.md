# 🚨 Backend - Plataforma SaaS Multi-Tenant de Emergencias Vehiculares

Sistema backend para gestión de emergencias vehiculares con arquitectura Multi-Tenant, comunicación en tiempo real, sincronización offline y análisis inteligente mediante IA.

## 🏗️ Arquitectura

- **Framework**: FastAPI 0.135.3
- **Base de Datos**: PostgreSQL (SQLAlchemy ORM)
- **Autenticación**: JWT (python-jose)
- **Comunicación en Tiempo Real**: WebSockets
- **IA**: Google Gemini API
- **Pagos**: Stripe
- **Notificaciones**: Firebase Cloud Messaging
- **Email**: Brevo / Resend
- **Workers**: 2 (configurados en Dockerfile)

## 📦 Estructura del Proyecto

```
backendp2/
├── src/
│   ├── core/              # Configuración central (DB, Auth)
│   ├── modules/
│   │   ├── iam/           # Identity & Access Management
│   │   ├── saas/          # Multi-tenancy
│   │   ├── catalog/       # Mecánicos, vehículos, talleres
│   │   ├── operations/    # Incidentes, chat, pagos, notificaciones
│   │   ├── analytics/     # Reportes y estadísticas
│   │   ├── offline_sync/  # Sincronización offline
│   │   └── realtime/      # WebSockets
│   └── main.py            # Entry point
├── uploads/               # Archivos subidos (fotos, audios)
├── requirements.txt       # Dependencias Python
├── Dockerfile             # Configuración Docker
├── docker-compose.yml     # Orquestación (dev)
├── .env.example           # Variables de entorno template
└── .dockerignore          # Archivos excluidos del build

```

## 🚀 Inicio Rápido (Desarrollo Local)

### 1. Requisitos Previos
- Python 3.12+
- PostgreSQL 16+
- pip / virtualenv

### 2. Instalación

```bash
# Clonar repositorio
cd backendp2

# Crear entorno virtual
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Instalar dependencias
pip install -r requirements.txt

# Configurar variables de entorno
cp .env.example .env
# Editar .env con tus credenciales
```

### 3. Ejecutar

```bash
# Iniciar servidor
uvicorn src.main:app --reload --host 0.0.0.0 --port 8000

# Visitar
# API: http://localhost:8000
# Docs: http://localhost:8000/docs
# Health: http://localhost:8000/health
```

### 4. Docker (Alternativa)

```bash
# Desarrollo con docker-compose
docker-compose up -d

# Solo backend
docker build -t backend .
docker run -p 8000:8000 --env-file .env backend
```

## 📚 Módulos Principales

### IAM (Identity & Access Management)
- **Auth**: Login, registro, recuperación de contraseña
- **Users**: Gestión de usuarios
- **Roles**: Sistema de permisos basado en roles

### SaaS Multi-Tenant
- Gestión de organizaciones/empresas
- Aislamiento de datos por tenant

### Catalog
- **Mecánicos**: Registro y gestión de mecánicos
- **Vehículos**: Información de vehículos de usuarios
- **Talleres**: Registro de talleres mecánicos
- **Profile**: Perfiles de usuarios

### Operations
- **Incidentes**: CRUD y gestión de emergencias vehiculares
- **Chat**: Mensajería en tiempo real entre usuarios y mecánicos
- **Bitácora**: Registro de acciones y cambios
- **Notificaciones**: Push notifications vía Firebase
- **Pagos**: Integración con Stripe
- **IA**: Análisis automático de incidentes con Gemini

### Analytics
- Reportes y estadísticas
- Métricas de rendimiento

### Offline Sync
- Sincronización de datos para apps móviles
- Queue de cambios pendientes

### Realtime
- WebSockets para comunicación en vivo
- Actualizaciones en tiempo real de incidentes

## 🔧 Variables de Entorno

Ver `.env.example` para todas las variables requeridas:

```bash
DATABASE_URL=postgresql://user:pass@host:5432/db
SECRET_KEY=your-secret-key
GEMINI_API_KEY=your-gemini-key
FIREBASE_SERVICE_ACCOUNT_BASE64=base64-encoded-json
STRIPE_SECRET_KEY=sk_test_...
EMAIL_PROVIDER=brevo
BREVO_API_KEY=your-brevo-key
FRONTEND_URL=http://localhost:4200
```

## 📡 Endpoints Principales

### Autenticación
- `POST /auth/login` - Login
- `POST /auth/register` - Registro
- `POST /auth/forgot-password` - Recuperar contraseña

### Incidentes
- `GET /incidentes/` - Listar incidentes
- `POST /incidentes/` - Crear incidente
- `GET /incidentes/{id}` - Detalle de incidente
- `PATCH /incidentes/{id}` - Actualizar incidente
- `POST /incidentes/{id}/asignar` - Asignar mecánico

### WebSocket
- `WS /ws/{user_id}` - Conexión WebSocket

Ver documentación completa en `/docs` (Swagger UI)

## 🧪 Testing

```bash
# Instalar dependencias de testing
pip install pytest pytest-asyncio httpx

# Ejecutar tests
pytest

# Con cobertura
pytest --cov=src
```

## 🐳 Despliegue en Coolify

Ver guía completa: [COOLIFY_DEPLOY.md](./COOLIFY_DEPLOY.md)

### Resumen:
1. Crear servicio PostgreSQL en Coolify
2. Crear aplicación desde repo Git
3. Configurar variables de entorno
4. Deploy automático

## 🔒 Seguridad

- ✅ JWT para autenticación
- ✅ Bcrypt para contraseñas
- ✅ CORS configurado
- ✅ Validación de entrada con Pydantic
- ✅ Rate limiting (recomendado agregar)
- ✅ HTTPS en producción

## 📊 Tecnologías

- **FastAPI**: Framework web moderno y rápido
- **SQLAlchemy**: ORM para PostgreSQL
- **Pydantic**: Validación de datos
- **Uvicorn**: Servidor ASGI
- **Firebase Admin**: Push notifications
- **Stripe**: Procesamiento de pagos
- **Google Gemini**: IA generativa
- **WebSockets**: Comunicación en tiempo real

## 🤝 Contribución

1. Fork el repositorio
2. Crea una rama: `git checkout -b feature/nueva-funcionalidad`
3. Commit: `git commit -m 'Agregar nueva funcionalidad'`
4. Push: `git push origin feature/nueva-funcionalidad`
5. Pull Request

## 📝 Licencia

Este proyecto es privado y de uso académico.

## 👥 Autores

Proyecto desarrollado como parte del Segundo Parcial de Sistemas de Información 2.

## 🆘 Soporte

Para problemas o preguntas, abre un issue en el repositorio.

---

**Estado**: ✅ Listo para producción
**Última actualización**: Junio 2026
