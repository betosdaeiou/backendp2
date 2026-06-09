# 🚀 Guía de Despliegue en Coolify - Backend

## 📋 Pre-requisitos

1. Cuenta en Coolify configurada
2. Acceso al repositorio Git (GitHub/GitLab)
3. Variables de entorno preparadas (ver abajo)

## 🔧 Configuración en Coolify

### 1. Crear Servicio de Base de Datos PostgreSQL

1. En Coolify, ve a **Services** → **+ New Service**
2. Selecciona **PostgreSQL**
3. Configura:
   - **Name**: `emergencia-db`
   - **PostgreSQL Version**: 16 (o la más reciente)
   - **Database Name**: `emergencia_db`
   - **Username**: `postgres`
   - **Password**: (genera una segura)
4. Despliega el servicio
5. Copia la **Connection String** (DATABASE_URL)

### 2. Desplegar Backend

1. En Coolify, ve a **Applications** → **+ New Application**
2. Selecciona **Git Repository**
3. Configura:
   - **Repository**: Tu repo de GitHub/GitLab
   - **Branch**: `main` o `master`
   - **Build Pack**: Docker (detectará automáticamente el Dockerfile)
   - **Base Directory**: `/backendp2` (si es monorepo)
   - **Port**: `8000`

### 3. Variables de Entorno Requeridas

En la sección **Environment Variables** de tu aplicación en Coolify, agrega:

```bash
# ── BASE DE DATOS ──
DATABASE_URL=postgresql://usuario:password@host:5432/emergencia_db
# Usa la connection string del servicio PostgreSQL creado arriba

# ── SEGURIDAD Y JWT ──
SECRET_KEY=genera-una-clave-secreta-muy-larga-y-aleatoria-aqui
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30

# ── INTELIGENCIA ARTIFICIAL ──
GEMINI_API_KEY=tu_api_key_de_google_gemini

# ── SERVICIO DE CORREO ──
EMAIL_PROVIDER=brevo
BREVO_API_KEY=tu_api_key_de_brevo
# O si usas Resend:
# EMAIL_PROVIDER=resend
# RESEND_API_KEY=tu_api_key_de_resend

FRONTEND_URL=https://tu-frontend.coolify.app
EMAIL_FROM=noreply@emergenciavehicular.com
EMAIL_FROM_NAME=Emergencia Vehicular

# ── FIREBASE (NOTIFICACIONES PUSH) ──
# Opción 1 (Recomendada para Coolify):
FIREBASE_SERVICE_ACCOUNT_BASE64=base64_codificado_del_json
# Para generar: cat firebase-service-account.json | base64 -w 0

# ── STRIPE (PAGOS) ──
STRIPE_SECRET_KEY=sk_live_tu_clave_secreta_de_stripe
```

### 4. Generar SECRET_KEY

Ejecuta en tu terminal local:

```bash
python -c "import secrets; print(secrets.token_urlsafe(64))"
```

### 5. Preparar Firebase Credentials en Base64

```bash
# En Linux/Mac:
cat firebase-service-account.json | base64 -w 0

# En Windows PowerShell:
[Convert]::ToBase64String([System.IO.File]::ReadAllBytes("firebase-service-account.json"))
```

## 🎯 Proceso de Despliegue

1. **Push al repositorio**: Coolify detectará automáticamente los cambios
2. **Build automático**: Docker construirá la imagen usando el Dockerfile
3. **Deploy**: La aplicación se desplegará en el puerto 8000
4. **Health Check**: Verifica en `https://tu-backend.coolify.app/health`

## ✅ Verificación Post-Despliegue

### 1. Health Check
```bash
curl https://tu-backend.coolify.app/health
```

Respuesta esperada:
```json
{
  "status": "ok",
  "database": "connected"
}
```

### 2. Documentación API
Visita: `https://tu-backend.coolify.app/docs`

### 3. Logs
En Coolify, ve a tu aplicación → **Logs** para monitorear.

## 🔒 Seguridad

- ✅ Usa siempre HTTPS (Coolify lo provee automáticamente)
- ✅ Nunca expongas tu archivo .env
- ✅ Usa claves secretas fuertes
- ✅ Configura CORS correctamente en producción (actualizar en main.py si es necesario)

## 📊 Recursos

- **CPU**: 1 vCPU mínimo
- **RAM**: 512 MB mínimo (recomendado 1 GB)
- **Storage**: Según uploads de usuarios

## 🐛 Troubleshooting

### Error: Database connection failed
- Verifica que el servicio PostgreSQL esté corriendo
- Confirma que DATABASE_URL esté correctamente configurado
- Revisa que las tablas se hayan creado (se crean automáticamente al inicio)

### Error: Módulo no encontrado
- Verifica que requirements.txt esté actualizado
- Revisa los logs de build en Coolify

### Error 500 en endpoints
- Revisa logs de la aplicación en Coolify
- Verifica que todas las variables de entorno estén configuradas

## 🔄 Actualización y Rollback

- **Actualizar**: Solo haz push a tu rama
- **Rollback**: En Coolify → **Deployments** → Selecciona un deployment previo

## 🌐 URLs Importantes

- API Base: `https://tu-backend.coolify.app`
- Documentación: `https://tu-backend.coolify.app/docs`
- Health: `https://tu-backend.coolify.app/health`
- Uploads: `https://tu-backend.coolify.app/uploads/`

## ✨ Próximo Paso

Continúa con el despliegue del Frontend (ver COOLIFY_DEPLOY.md en frontendp2)
