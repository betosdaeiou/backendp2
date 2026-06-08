import os
import json
import urllib.request

# Soporta Brevo (recomendado) y Resend como proveedores de email
EMAIL_PROVIDER = os.getenv("EMAIL_PROVIDER", "brevo")  # "brevo" o "resend"
BREVO_API_KEY = os.getenv("BREVO_API_KEY", "")
RESEND_API_KEY = os.getenv("RESEND_API_KEY", "")
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:4200")
EMAIL_FROM = os.getenv("EMAIL_FROM", "noreply@emergenciavehicular.com")
EMAIL_FROM_NAME = os.getenv("EMAIL_FROM_NAME", "Emergencia Vehicular")


def _build_html(token: str) -> str:
    reset_link = f"{FRONTEND_URL}/restablecer-password?token={token}"
    return f"""
    <div style="font-family: 'Segoe UI', Arial, sans-serif; max-width: 600px; margin: 0 auto; background: #0f172a; border-radius: 16px; overflow: hidden;">
        <div style="background: linear-gradient(135deg, #3b82f6, #8b5cf6); padding: 32px; text-align: center;">
            <h1 style="color: white; margin: 0; font-size: 24px;">Restablecer Contrasena</h1>
        </div>
        <div style="padding: 32px; color: #e2e8f0;">
            <p style="font-size: 16px; line-height: 1.6;">Hola,</p>
            <p style="font-size: 16px; line-height: 1.6;">
                Recibimos una solicitud para restablecer la contrasena de tu cuenta en 
                <strong>Emergencia Vehicular</strong>.
            </p>
            <div style="text-align: center; margin: 32px 0;">
                <a href="{reset_link}" 
                   style="background: linear-gradient(135deg, #3b82f6, #8b5cf6); color: white; padding: 14px 32px; 
                          border-radius: 12px; text-decoration: none; font-weight: bold; font-size: 16px;
                          display: inline-block; box-shadow: 0 4px 15px rgba(59, 130, 246, 0.4);">
                    Restablecer mi Contrasena
                </a>
            </div>
            <p style="font-size: 14px; color: #94a3b8; line-height: 1.6;">
                Este enlace expira en <strong>30 minutos</strong>. Si no solicitaste este cambio, puedes ignorar este correo.
            </p>
            <hr style="border: 1px solid #1e293b; margin: 24px 0;">
            <p style="font-size: 12px; color: #64748b; text-align: center;">
                Emergencia Vehicular 2026
            </p>
        </div>
    </div>
    """


def _http_post(url: str, headers: dict, body: dict) -> dict:
    """HTTP POST usando urllib (stdlib, no necesita instalar nada)."""
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req) as resp:
            return {"status": resp.status, "body": resp.read().decode()}
    except urllib.error.HTTPError as e:
        error_body = e.read().decode() if e.fp else str(e)
        raise Exception(f"HTTP {e.code}: {error_body}")


def _enviar_brevo(destinatario: str, html: str):
    _http_post(
        "https://api.brevo.com/v3/smtp/email",
        headers={
            "api-key": BREVO_API_KEY,
            "Content-Type": "application/json",
            "Accept": "application/json"
        },
        body={
            "sender": {"name": EMAIL_FROM_NAME, "email": EMAIL_FROM},
            "to": [{"email": destinatario}],
            "subject": "Restablecer Contrasena - Emergencia Vehicular",
            "htmlContent": html
        }
    )


def _enviar_resend(destinatario: str, html: str):
    _http_post(
        "https://api.resend.com/emails",
        headers={
            "Authorization": f"Bearer {RESEND_API_KEY}",
            "Content-Type": "application/json"
        },
        body={
            "from": f"{EMAIL_FROM_NAME} <{EMAIL_FROM}>",
            "to": [destinatario],
            "subject": "Restablecer Contrasena - Emergencia Vehicular",
            "html": html
        }
    )


def enviar_email_reset(destinatario: str, token: str):
    """Envia un correo con el link para restablecer la contrasena."""
    html = _build_html(token)

    if EMAIL_PROVIDER == "brevo":
        _enviar_brevo(destinatario, html)
    elif EMAIL_PROVIDER == "resend":
        _enviar_resend(destinatario, html)
    else:
        raise Exception(f"Proveedor de email no soportado: {EMAIL_PROVIDER}")
