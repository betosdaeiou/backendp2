# Guía para desarrollo con IA

Este documento evita errores comunes de imports y convenciones en este backend.

## Ejecutar el proyecto

Siempre desde la **raíz del repo** (`backendp2/`):

```bash
uvicorn src.main:app --reload --host 0.0.0.0 --port 8000
python -m src.seed
```

No ejecutar archivos sueltos con `python src/modules/.../routers/foo.py`.

---

## Regla de oro: models vs schemas

| Archivo | Tecnología | Para qué |
|---------|------------|----------|
| `src/modules/*/models.py` | SQLAlchemy | Base de datos: `db.query()`, `db.add()`, FK |
| `src/modules/*/schemas.py` | Pydantic | API: request/response, `response_model=` |

**Nunca** uses `schemas` para consultas a BD. **Nunca** uses `models` como `response_model` directo (usa schemas con `from_attributes = True`).

### Import recomendado para modelos (BD)

```python
# Opción 1 — preferida
from src.models import Incidente, Usuario, Taller, Tenant

# Opción 2 — también válida
from src.modules.operations.models import Incidente
from src.modules.iam.models import Usuario
```

### Import para schemas (API)

```python
from src.modules.operations.schemas import IncidenteCreate, IncidenteOut, IncidenteDetalle
from src.modules.iam.schemas import UsuarioCreate, Token
```

---

## Mapa de modelos por módulo

### `src/modules/iam/models.py`
`Usuario`, `Rol`, `Permiso`, `UsuarioTenant`

### `src/modules/saas/models.py`
`Tenant`, `PlanSaaS`, `Suscripcion`

### `src/modules/catalog/models.py`
`Taller`, `Mecanico`, `Conductor`, `Vehiculo`, `VehiculoConductor`, `Administrador`, `ServicioTaller`

### `src/modules/operations/models.py`
`Incidente`, `Evidencia`, `Cotizacion`, `Pago`, `Bitacora`, `Notificacion`, `MensajeChat`, `AnalisisIA`

**Registro central:** `src/models/__init__.py` re-exporta todos.

---

## Colisiones de nombres (importante)

Estos nombres existen en **models Y schemas** con significados distintos:

| Nombre | Modelo SQLAlchemy | Schema Pydantic |
|--------|-------------------|-----------------|
| `Usuario` | `iam/models.py` | `iam/schemas.py` → usar `UsuarioCreate`, `UsuarioUpdate` para API |
| `Rol` | `iam/models.py` | `iam/schemas.py` |
| `Permiso` | `iam/models.py` | `iam/schemas.py` |

Para incidentes, usar **`IncidenteOut`** / **`IncidenteDetalle`** en schemas, nunca un alias `Incidente` en schemas.

En routers que necesitan ambos:

```python
from src.models import Incidente
from src.modules.operations.schemas import IncidenteOut, IncidenteCreate
```

---

## Convención de campos (Id vs id)

Hay dos estilos en la BD. Respetar el existente, no unificar sin migración.

**PascalCase** (entidades IAM / catalog legacy):
```python
usuario.Id
usuario.Correo
usuario.Nombre
taller.Id
tenant.Id
```

**snake_case** (operations):
```python
incidente.id
incidente.tenant_id
incidente.estado
cotizacion.monto
```

---

## Estructura de paquetes

```
src/
├── core/           # database.py, config.py, security.py
├── models/         # re-export de todos los modelos SQLAlchemy
├── modules/
│   ├── iam/        # auth, usuarios, roles
│   ├── saas/       # tenants, planes, suscripciones
│   ├── catalog/    # talleres, mecánicos, vehículos, conductores
│   ├── operations/ # incidentes, pagos, chat, notificaciones, IA
│   ├── analytics/  # reportes (/reportes)
│   ├── offline_sync/
│   └── realtime/   # WebSockets
├── shared/         # utilidades transversales
└── broker/         # WebSocket manager
```

### Dependencias entre módulos

```
operations → catalog, iam, saas
catalog    → iam, saas
saas       → iam
analytics  → operations, catalog, iam
```

Usar imports absolutos con prefijo `src.`:

```python
from src.modules.operations.models import Incidente   # ✅
from ..models import Incidente                        # ❌ evitar
```

---

## Dónde poner código nuevo

| Qué agregas | Dónde |
|-------------|-------|
| Nueva tabla BD | `src/modules/<modulo>/models.py` + export en `src/models/__init__.py` |
| Request/response API | `src/modules/<modulo>/schemas.py` |
| Endpoint REST | `src/modules/<modulo>/routers/` |
| Lógica de negocio reutilizable | `src/modules/<modulo>/services/` |
| Utilidad transversal | `src/shared/` |

Registrar router nuevo en `src/main.py`.

---

## Analytics: no duplicar

- Reportes generales → `src/modules/analytics/routers.py` (prefijo `/reportes`)
- Analytics de operaciones → `src/modules/operations/routers/analytics.py` (prefijo `/analytics`)

Antes de crear un endpoint de métricas, revisar si ya existe en el otro módulo.

---

## Patrón típico de router

```python
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from src.core.database import get_db
from src.modules.iam.dependencies import get_current_user
from src.models import Incidente, Usuario
from src.modules.operations.schemas import IncidenteOut

router = APIRouter(prefix="/incidentes", tags=["Incidentes"])

@router.get("/{id}", response_model=IncidenteOut)
def get_incidente(id: int, db: Session = Depends(get_db), current_user: Usuario = Depends(get_current_user)):
    incidente = db.query(Incidente).filter(Incidente.id == id).first()
    ...
```

---

## Imports que NO existen (no inventar)

```python
from models import ...              # ❌
from src.models import IncidenteCreate  # ❌ IncidenteCreate está en schemas
from src.modules.models import ...  # ❌
from src.modules.operations.schemas import Incidente  # ❌ usar IncidenteOut
```

---

## Checklist antes de terminar un cambio

- [ ] Modelos BD importados desde `src.models` o `src.modules.*.models`
- [ ] Schemas API importados desde `src.modules.*.schemas`
- [ ] Campos con la capitalización correcta (`Id` vs `id`)
- [ ] Router registrado en `src/main.py` si es nuevo
- [ ] Nuevo modelo añadido a `src/models/__init__.py`
