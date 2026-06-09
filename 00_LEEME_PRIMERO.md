# 📖 LÉEME PRIMERO - Despliegue en Coolify

## 🎯 Estado del Proyecto

**✅ PROYECTO LIMPIO Y LISTO PARA DESPLEGAR EN COOLIFY**

Se han eliminado **39 archivos innecesarios** (scripts de desarrollo y archivos temporales) y se ha creado documentación completa para el despliegue.

---

## 📚 Documentos Importantes (en orden de lectura)

### 1️⃣ **DESPLIEGUE_COOLIFY_INICIO.md** ⭐ **EMPIEZA AQUÍ**
Guía rápida paso a paso para desplegar en Coolify (30-45 min)

### 2️⃣ **COOLIFY_DEPLOY.md**
Guías detalladas específicas para Backend y Frontend

### 3️⃣ **VERIFICACION_FINAL.md**
Checklist completo de verificación pre y post despliegue

### 4️⃣ **README.md**
Documentación técnica completa de cada proyecto

### 5️⃣ **LIMPIEZA_RESUMEN.md**
Resumen de archivos eliminados durante la limpieza

---

## 🚀 Inicio Rápido (3 pasos)

### 1. Backend
```bash
1. Crear PostgreSQL en Coolify
2. Crear aplicación desde Git repo
3. Configurar variables de entorno (ver .env.example)
4. Deploy
```

### 2. Frontend
```bash
1. Actualizar URL del backend en el código
2. Crear aplicación desde Git repo
3. Deploy
```

### 3. Verificar
```bash
Backend:  https://tu-backend.coolify.app/health
Frontend: https://tu-frontend.coolify.app
```

---

## 📋 Requisitos Previos

### APIs y Credenciales Necesarias:

- [ ] **PostgreSQL** (se crea en Coolify)
- [ ] **Google Gemini API Key** → https://aistudio.google.com/app/apikey
- [ ] **Brevo API Key** → https://app.brevo.com/settings/keys/api
- [ ] **Stripe API Key** → https://dashboard.stripe.com/apikeys
- [ ] **Firebase Service Account** → Firebase Console
- [ ] **SECRET_KEY** (generar con Python - instrucciones en guía)

### Tiempos Estimados:
- ⏱️ Obtener API Keys: 15 minutos
- ⏱️ Configurar Backend: 15 minutos
- ⏱️ Configurar Frontend: 10 minutos
- ⏱️ Verificación: 10 minutos
- **Total: ~50 minutos**

---

## 🔄 Proceso de Despliegue

```
┌─────────────────┐
│  1. PostgreSQL  │ ← Crear servicio en Coolify
└────────┬────────┘
         │
         ↓
┌─────────────────┐
│   2. Backend    │ ← Desplegar con Dockerfile
└────────┬────────┘
         │
         ↓
┌─────────────────┐
│  3. Frontend    │ ← Desplegar con Dockerfile
└────────┬────────┘
         │
         ↓
┌─────────────────┐
│  4. Verificar   │ ← Probar funcionalidades
└─────────────────┘
```

---

## 📦 Estructura de Archivos de Configuración

### Backend (backendp2/)
```
✅ Dockerfile              → Configuración Docker
✅ requirements.txt        → Dependencias Python
✅ .env.example            → Template de variables
✅ docker-compose.yml      → Para desarrollo local
✅ .dockerignore           → Archivos excluidos del build
✅ src/                    → Código fuente
```

### Frontend (frontendp2/)
```
✅ Dockerfile              → Multi-stage build con Nginx
✅ package.json            → Dependencias Node
✅ angular.json            → Configuración Angular
✅ ngsw-config.json        → Service Worker (PWA)
✅ .dockerignore           → Archivos excluidos del build
✅ src/                    → Código fuente
```

---

## ⚡ Comandos Útiles

### Generar SECRET_KEY
```bash
python -c "import secrets; print(secrets.token_urlsafe(64))"
```

### Firebase en Base64 (Windows PowerShell)
```powershell
[Convert]::ToBase64String([System.IO.File]::ReadAllBytes("firebase-service-account.json"))
```

### Firebase en Base64 (Linux/Mac)
```bash
cat firebase-service-account.json | base64 -w 0
```

### Verificar Backend Local
```bash
cd backendp2
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
uvicorn src.main:app --reload
```

### Verificar Frontend Local
```bash
cd frontendp2
npm install
npm start
```

---

## 🎯 URLs Importantes Después del Despliegue

### Backend
- **API Base**: `https://tu-backend.coolify.app`
- **Documentación**: `https://tu-backend.coolify.app/docs`
- **Health Check**: `https://tu-backend.coolify.app/health`

### Frontend
- **Aplicación**: `https://tu-frontend.coolify.app`
- **Login**: `https://tu-frontend.coolify.app/login`
- **Dashboard**: `https://tu-frontend.coolify.app/dashboard`

---

## ✅ Checklist Rápido

### Antes de Empezar
- [ ] Cuenta en Coolify configurada
- [ ] Acceso al repositorio Git
- [ ] Todas las API keys obtenidas

### Backend
- [ ] PostgreSQL creado
- [ ] Variables de entorno configuradas
- [ ] Aplicación desplegada
- [ ] Health check funciona

### Frontend
- [ ] URL del backend actualizada en código
- [ ] Aplicación desplegada
- [ ] Login funciona
- [ ] PWA instalable

---

## 🆘 ¿Problemas?

### Backend no inicia
→ Revisar logs en Coolify y verificar DATABASE_URL

### Frontend no se conecta
→ Verificar URL del backend en el código y CORS

### Build falla
→ Revisar logs de build y verificar Dockerfile

Para más detalles, consulta **VERIFICACION_FINAL.md** sección Troubleshooting.

---

## 📞 Soporte

Para más ayuda:
1. Consulta la documentación completa en los archivos MD
2. Revisa los logs en Coolify
3. Verifica que todas las variables de entorno estén configuradas

---

## 🎉 ¡Siguiente Paso!

**👉 Abre: DESPLIEGUE_COOLIFY_INICIO.md**

Allí encontrarás la guía paso a paso completa para desplegar tu aplicación.

---

**Creado:** Junio 2026  
**Estado:** ✅ Listo para producción  
**Tiempo estimado:** 50 minutos  
**Dificultad:** Media
