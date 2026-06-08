import os
from dotenv import load_dotenv

load_dotenv()

# ── Configuraciones globales del proyecto ──────────────────────────────────────
DATABASE_URL: str = os.getenv("DATABASE_URL", "postgresql://postgres:password@localhost:5432/emergencias")
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

SECRET_KEY: str = os.getenv("SECRET_KEY", "default-secret-key")
ALGORITHM: str = os.getenv("ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30"))

GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")

STRIPE_SECRET_KEY: str = os.getenv("STRIPE_SECRET_KEY", "")

# Email
EMAIL_PROVIDER: str = os.getenv("EMAIL_PROVIDER", "brevo")
BREVO_API_KEY: str = os.getenv("BREVO_API_KEY", "")
RESEND_API_KEY: str = os.getenv("RESEND_API_KEY", "")
FRONTEND_URL: str = os.getenv("FRONTEND_URL", "http://localhost:4200")
EMAIL_FROM: str = os.getenv("EMAIL_FROM", "noreply@emergenciavehicular.com")
EMAIL_FROM_NAME: str = os.getenv("EMAIL_FROM_NAME", "Emergencia Vehicular")
