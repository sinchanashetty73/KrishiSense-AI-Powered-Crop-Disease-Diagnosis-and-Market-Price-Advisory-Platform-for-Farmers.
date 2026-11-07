"""All settings come from environment variables (or a .env file).
Change values in the root .env file, not here."""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "sqlite:///./dev.db"
    jwt_secret: str = "change-me-in-production"
    jwt_expire_minutes: int = 60 * 24 * 7
    ml_service_url: str = "http://ml_service:8001"

    # Image storage: leave S3_BUCKET empty to store files locally in UPLOAD_DIR.
    s3_bucket: str = ""
    aws_region: str = "ap-south-1"
    upload_dir: str = "./uploads"

    # SMS: "log" only writes the message to the log (development). "sns" sends through Amazon SNS.
    # For India, SNS needs DLT registration: set the sender id, entity id and template id below.
    sms_provider: str = "log"
    sns_sender_id: str = ""
    sns_entity_id: str = ""
    sns_template_id: str = ""

    # Browser push (Web Push / VAPID). Generate keys with: python scripts/generate_vapid.py
    vapid_public_key: str = ""
    vapid_private_key: str = ""
    vapid_subject: str = "mailto:admin@example.com"

    # In development the OTP is returned in the API response. Set to false in production
    # and plug a real SMS provider into app/services/sms.py.
    dev_otp_echo: bool = True
    cors_origins: str = "*"
    confidence_threshold: float = 0.6
    max_upload_mb: int = 8

    # Seeds demo markets and SYNTHETIC prices so the app works on day one.
    # Set to false once you load real mandi data with the ingest job.
    seed_demo_data: bool = True


settings = Settings()
