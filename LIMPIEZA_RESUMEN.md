# 🧹 LIMPIEZA DE PROYECTO PARA DESPLIEGUE EN COOLIFY

## ✅ Archivos Eliminados

### Backend (backendp2)
Scripts de desarrollo (patch/fix):
- alter_db.py
- alter_incidente_db.py
- append_endpoint.py
- fix_db.py
- patch_analytics_router.py
- patch_catalog_routers.py
- patch_incidentes.py
- patch_models.py
- patch_models_incidente.py
- patch_routers.py
- query_db.py
- query_permisos.py
- refactor_states.py
- reset_and_seed.py
- reset_db.py
- test_talleres.py
- update_permisos.py

Archivos de desarrollo:
- database.db (BD SQLite de desarrollo)
- dev.db (BD SQLite de desarrollo)
- backend-segundo-parcial-si2.code-workspace (workspace VSCode)

### Frontend (frontendp2)
Scripts de desarrollo (patch):
- patch_app.py
- patch_app_config.py
- patch_dashboard_html.py
- patch_incidente.py
- patch_permissions.py
- patch_solicitudes.py
- patch_ts_marker.py
- replace_states_html.py

### Mobile (mobilep2)
Scripts de desarrollo (patch/fix):
- fix.py
- patch_api.py
- patch_api2.py
- patch_api_methods.py
- patch_estado.py
- patch_flutter_api.py
- patch_historial.py
- patch_login_screen.py
- patch_reportar.py
- patch_sync_service.py

Archivo temporal:
- build_log.txt

## 📦 Archivos Mantenidos (Importantes para Producción)

### Backend
- ✅ Dockerfile
- ✅ docker-compose.yml
- ✅ requirements.txt
- ✅ .env.example
- ✅ .dockerignore
- ✅ .gitignore
- ✅ Carpeta src/ (código fuente)

### Frontend
- ✅ Dockerfile (con build multi-stage y nginx)
- ✅ package.json / package-lock.json
- ✅ angular.json
- ✅ tsconfig.json
- ✅ .dockerignore
- ✅ .gitignore
- ✅ Carpeta src/ (código fuente)

### Mobile
- ✅ pubspec.yaml
- ✅ pubspec.lock
- ✅ android/ (configuración Android)
- ✅ ios/ (configuración iOS)
- ✅ lib/ (código fuente Dart/Flutter)
- ✅ .gitignore

## 🚀 Próximos Pasos para Coolify

### 1. Backend
```bash
# Coolify detectará automáticamente el Dockerfile
# Asegúrate de configurar las variables de entorno en Coolify:
- DATABASE_URL
- SECRET_KEY
- GEMINI_API_KEY
- EMAIL_PROVIDER y sus keys
- FIREBASE_SERVICE_ACCOUNT_BASE64
- STRIPE_SECRET_KEY
```

### 2. Frontend
```bash
# Coolify usará el Dockerfile multi-stage
# Configurar variable de entorno en tiempo de build si es necesario:
- API_URL (si no está hardcodeada)
```

### 3. Base de Datos
- Crear un servicio PostgreSQL en Coolify
- Conectar el backend al servicio de BD usando DATABASE_URL

## 📝 Notas Importantes

1. **Variables de Entorno**: Todas las variables en .env.example deben configurarse en Coolify
2. **Puerto Backend**: 8000 (expuesto en Dockerfile)
3. **Puerto Frontend**: 80 (nginx, expuesto en Dockerfile)
4. **Uploads**: El backend crea la carpeta /app/uploads automáticamente
5. **Mobile**: No se despliega en Coolify (es app Flutter, se compila localmente)

## ✨ Estado Final

- ✅ Proyectos limpios de archivos de desarrollo
- ✅ Dockerfiles optimizados y listos
- ✅ .dockerignore actualizados
- ✅ .gitignore actualizados
- ✅ Documentación de variables de entorno clara
- ✅ READMEs creados para cada proyecto
- ✅ Guías de despliegue en Coolify creadas
- ✅ Listo para despliegue en Coolify

## 📋 Checklist Pre-Despliegue

### Backend
- [ ] Revisar y actualizar .env.example si es necesario
- [ ] Verificar que todas las rutas de API funcionan
- [ ] Confirmar que el Dockerfile construye correctamente
- [ ] Preparar credenciales de Firebase en Base64
- [ ] Obtener API keys (Gemini, Brevo/Resend, Stripe)
- [ ] Crear servicio PostgreSQL en Coolify
- [ ] Configurar todas las variables de entorno en Coolify

### Frontend
- [ ] Actualizar URL del backend en el código
- [ ] Verificar que la aplicación compila sin errores
- [ ] Confirmar que el Dockerfile construye correctamente
- [ ] Probar la aplicación localmente
- [ ] Verificar que Service Worker funciona

### General
- [ ] Hacer commit de todos los cambios
- [ ] Push a repositorio Git
- [ ] Verificar que .gitignore excluye archivos sensibles
- [ ] Documentar cualquier configuración adicional necesaria

## 🔍 Verificaciones Realizadas

✅ Eliminados 39 archivos innecesarios (scripts patch y archivos temporales)
✅ Dockerfiles verificados y optimizados
✅ .dockerignore actualizados para excluir archivos de desarrollo
✅ Variables de entorno documentadas en .env.example
✅ Guías de despliegue creadas para Coolify
✅ READMEs completos con documentación técnica
