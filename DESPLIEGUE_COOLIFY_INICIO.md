# 🚀 INICIO RÁPIDO - Despliegue en Coolify

## 📌 Orden de Despliegue

1. **Backend primero** (necesita base de datos)
2. **Frontend después** (necesita URL del backend)
3. **Mobile** (compilar localmente, no se despliega en Coolify)

---

## 🔹 PASO 1: Desplegar Backend

### 1.1 Crear PostgreSQL en Coolify

1. Ve a **Services** → **+ New Service**
2. Selecciona **PostgreSQL 16**
3. Configura:
   ```
   Name: emergencia-db
   Database: emergencia_db
   Username: postgres
   Password: [genera una segura]
   ```
4. Copia el **Connection String** (DATABASE_URL)

### 1.2 Preparar Variables de Entorno

**Genera SECRET_KEY:**
```bash
python -c "import secrets; print(secrets.token_urlsafe(64))"
```

**Firebase en Base64:**
```bash
# PowerShell (Windows):
[Convert]::ToBase64String([System.IO.File]::ReadAllBytes("firebase-service-account.json"))

# Linux/Mac:
cat firebase-service-account.json | base64 -w 0
```

### 1.3 Obtener API Keys

- [ ] **Google Gemini**: https://aistudio.google.com/app/apikey
- [ ] **Brevo**: https://app.brevo.com/settings/keys/api
- [ ] **Stripe**: https://dashboard.stripe.com/apikeys
- [ ] **Firebase**: https://console.firebase.google.com/ → Project Settings → Service Accounts

### 1.4 Crear Aplicación Backend en Coolify

1. **Applications** → **+ New Application**
2. Configurar:
   ```
   Repository: [Tu repo Git]
   Branch: main
   Build Pack: Docker
   Base Directory: /backendp2
   Port: 8000
   ```

3. **Variables de Entorno** (copiar de .env.example):
   ```bash
   DATABASE_URL=postgresql://postgres:password@host:5432/emergencia_db
   SECRET_KEY=[tu-secret-key-generado]
   ALGORITHM=HS256
   ACCESS_TOKEN_EXPIRE_MINUTES=30
   
   GEMINI_API_KEY=[tu-gemini-key]
   
   EMAIL_PROVIDER=brevo
   BREVO_API_KEY=[tu-brevo-key]
   EMAIL_FROM=noreply@emergenciavehicular.com
   EMAIL_FROM_NAME=Emergencia Vehicular
   FRONTEND_URL=https://tu-frontend.coolify.app
   
   FIREBASE_SERVICE_ACCOUNT_BASE64=[tu-firebase-base64]
   
   STRIPE_SECRET_KEY=[tu-stripe-key]
   ```

4. **Deploy** y espera a que termine

### 1.5 Verificar Backend

```bash
# Health Check
https://tu-backend.coolify.app/health
# Debe devolver: {"status": "ok", "database": "connected"}

# Documentación
https://tu-backend.coolify.app/docs
```

✅ **Backend desplegado exitosamente**

---

## 🔹 PASO 2: Desplegar Frontend

### 2.1 Actualizar URL del Backend

**IMPORTANTE:** Antes de desplegar, actualiza la URL del backend en tu código.

Busca y reemplaza en los archivos de servicios:

```typescript
// Ejemplo en src/app/services/api.service.ts
private apiUrl = 'https://tu-backend.coolify.app';
```

Hacer commit y push:
```bash
git add .
git commit -m "Actualizar URL del backend para producción"
git push
```

### 2.2 Crear Aplicación Frontend en Coolify

1. **Applications** → **+ New Application**
2. Configurar:
   ```
   Repository: [Tu repo Git]
   Branch: main
   Build Pack: Docker
   Base Directory: /frontendp2
   Port: 80
   ```

3. **Variables de Entorno** (opcional, si usas environment.ts):
   ```bash
   API_URL=https://tu-backend.coolify.app
   ```

4. **Deploy** y espera (build puede tardar 5-10 minutos)

### 2.3 Verificar Frontend

1. Abre: `https://tu-frontend.coolify.app`
2. Verifica:
   - [ ] La página carga sin errores
   - [ ] Login funciona
   - [ ] No hay errores en DevTools Console
   - [ ] Service Worker está activo (DevTools → Application)

✅ **Frontend desplegado exitosamente**

---

## 🔹 PASO 3: Verificación Completa

### Backend
- [ ] `/health` devuelve status OK
- [ ] `/docs` muestra Swagger UI
- [ ] Login desde frontend funciona
- [ ] Creación de incidentes funciona
- [ ] Upload de imágenes funciona

### Frontend
- [ ] Página principal carga
- [ ] Login funciona
- [ ] Dashboard muestra datos
- [ ] PWA instalable
- [ ] Service Worker activo
- [ ] Funciona offline después de primera carga

### Integración
- [ ] Frontend se conecta al backend correctamente
- [ ] WebSockets funcionan (chat en tiempo real)
- [ ] Notificaciones push funcionan
- [ ] Mapas funcionan (Leaflet)
- [ ] Subida de archivos funciona

---

## 🔹 PASO 4: Configuración Adicional (Opcional)

### Dominio Personalizado

**Backend:**
1. Coolify → Tu app backend → **Domains**
2. Agregar: `api.tudominio.com`
3. Configurar DNS: CNAME → Tu URL Coolify
4. SSL automático

**Frontend:**
1. Coolify → Tu app frontend → **Domains**
2. Agregar: `app.tudominio.com`
3. Configurar DNS: CNAME → Tu URL Coolify
4. SSL automático

### Actualizar URLs después de dominio personalizado

Si configuras dominios personalizados, actualiza:
1. Frontend: URL del backend
2. Backend: FRONTEND_URL en variables de entorno

---

## 🆘 Troubleshooting Rápido

### Backend no inicia
```
1. Revisar Logs en Coolify
2. Verificar DATABASE_URL
3. Confirmar todas las env vars están configuradas
```

### Frontend no se conecta al backend
```
1. Abrir DevTools → Console → Buscar errores
2. Verificar URL del backend en el código
3. Verificar CORS en backend
4. Verificar que backend está corriendo
```

### Build falla
```
Backend:
- Verificar requirements.txt
- Verificar Dockerfile
- Ver logs de build

Frontend:
- Verificar package.json
- npm install localmente para probar
- Aumentar RAM en Coolify si falla por memoria
```

---

## 📚 Documentación Completa

Para más detalles, consulta:

- **COOLIFY_DEPLOY.md** (Backend) - Guía detallada backend
- **COOLIFY_DEPLOY.md** (Frontend) - Guía detallada frontend
- **README.md** (Backend) - Documentación técnica backend
- **README.md** (Frontend) - Documentación técnica frontend
- **VERIFICACION_FINAL.md** - Checklist completo

---

## ✨ URLs Finales

Después del despliegue:

```
Backend API:     https://tu-backend.coolify.app
Backend Docs:    https://tu-backend.coolify.app/docs
Backend Health:  https://tu-backend.coolify.app/health

Frontend:        https://tu-frontend.coolify.app
Frontend Login:  https://tu-frontend.coolify.app/login
Frontend Dashboard: https://tu-frontend.coolify.app/dashboard
```

---

## 🎉 ¡Listo!

Tu plataforma de emergencias vehiculares está desplegada y funcionando en producción.

**Siguiente paso:** Probar todas las funcionalidades y compartir las URLs con tu equipo.

---

**Tiempo estimado total:** 30-45 minutos
**Dificultad:** Media
**Estado:** ✅ Listo para desplegar
