from sqlalchemy.orm import Session
from src.modules.operations.models import Notificacion
from src.modules.iam.models import Usuario
from datetime import datetime
import os
import json

# ── Firebase Admin (inicialización lazy) ──────────────────────────────────────
_firebase_initialized = False

def _init_firebase():
    global _firebase_initialized
    if _firebase_initialized:
        return True
    try:
        import firebase_admin
        from firebase_admin import credentials

        if firebase_admin._apps:
            _firebase_initialized = True
            return True

        # Opción 1: variable de entorno con JSON en Base64 (Para entornos como Coolify/Docker)
        service_account_base64 = os.getenv("FIREBASE_SERVICE_ACCOUNT_BASE64")
        if service_account_base64:
            import base64
            decoded = base64.b64decode(service_account_base64).decode('utf-8')
            cred_dict = json.loads(decoded)
            cred = credentials.Certificate(cred_dict)
            firebase_admin.initialize_app(cred)
            _firebase_initialized = True
            print("[FCM] Firebase inicializado con FIREBASE_SERVICE_ACCOUNT_BASE64")
            return True

        # Opción 2: variable de entorno con JSON del service account
        service_account_json = os.getenv("FIREBASE_SERVICE_ACCOUNT_JSON")
        if service_account_json:
            cred_dict = json.loads(service_account_json)
            cred = credentials.Certificate(cred_dict)
            firebase_admin.initialize_app(cred)
            _firebase_initialized = True
            print("[FCM] Firebase inicializado con FIREBASE_SERVICE_ACCOUNT_JSON")
            return True

        # Opción 2: archivo en disco
        service_account_path = os.getenv("FIREBASE_SERVICE_ACCOUNT_PATH", "firebase-service-account.json")
        if os.path.exists(service_account_path):
            cred = credentials.Certificate(service_account_path)
            firebase_admin.initialize_app(cred)
            _firebase_initialized = True
            print(f"[FCM] Firebase inicializado con archivo: {service_account_path}")
            return True

        print("[FCM] ADVERTENCIA: No se encontró configuración de Firebase. Las notificaciones push no se enviarán.")
        return False
    except Exception as e:
        print(f"[FCM] Error inicializando Firebase: {e}")
        return False

# ─────────────────────────────────────────────────────────────────────────────

async def _broadcast_ws(tenant_id, room_id, payload):
    from src.broker.manager import manager
    if tenant_id:
        await manager.broadcast(payload, tenant_id, room_id)
    else:
        await manager.broadcast_all_tenants(payload, room_id)

def crear_notificacion(db: Session, usuario_id: int, titulo: str, descripcion: str, background_tasks = None):
    """
    Crea una notificación en la base de datos y envía push via FCM si hay token.
    Opcionalmente, emite la notificación por WebSockets usando background_tasks.
    """
    fecha_actual = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    from src.modules.iam.models import UsuarioTenant
    usuario = db.query(Usuario).filter(Usuario.Id == usuario_id).first()
    
    tenant_id = None
    if usuario:
        membership = db.query(UsuarioTenant).filter(UsuarioTenant.usuario_id == usuario.Id).first()
        tenant_id = membership.tenant_id if membership else None

    nueva_notificacion = Notificacion(
        titulo=titulo,
        descripcion=descripcion,
        usuario_id=usuario_id,
        fecha=fecha_actual,
        estado="No leída",
        tenant_id=tenant_id
    )

    db.add(nueva_notificacion)
    db.commit()
    db.refresh(nueva_notificacion)

    # Emitir por WebSockets si se provee background_tasks
    if background_tasks:
        background_tasks.add_task(
            _broadcast_ws,
            tenant_id,
            f"user_{usuario_id}",
            {
                "action": "nueva_notificacion",
                "titulo": titulo,
                "descripcion": descripcion,
                "notificacion_id": nueva_notificacion.id
            }
        )

    # Enviar push si el usuario tiene token FCM registrado
    if usuario and usuario.fcm_token:
        enviar_push_fcm(usuario.fcm_token, titulo, descripcion)

    return nueva_notificacion


def enviar_push_fcm(fcm_token: str, titulo: str, body: str):
    """
    Envía una notificación push real via Firebase Cloud Messaging (FCM v1).
    Requiere que Firebase esté inicializado con un service account.
    """
    if not _init_firebase():
        print(f"[FCM] Push omitido (Firebase no configurado): {titulo}")
        return

    try:
        from firebase_admin import messaging

        message = messaging.Message(
            notification=messaging.Notification(
                title=titulo,
                body=body,
            ),
            android=messaging.AndroidConfig(
                priority="high",
                notification=messaging.AndroidNotification(
                    sound="default",
                    channel_id="high_importance_channel",
                ),
            ),
            token=fcm_token,
        )

        response = messaging.send(message)
        print(f"[FCM] ✅ Push enviado exitosamente. Message ID: {response}")

    except Exception as e:
        print(f"[FCM] ❌ Error enviando push a token {fcm_token[:15]}...: {e}")

