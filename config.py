import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    # WhatsApp Business API
    WHATSAPP_ACCESS_TOKEN = os.getenv("WHATSAPP_ACCESS_TOKEN", "EAAUsM4AyfcUBRv3nH7t8ZBMykm6cM0oqwBVRboPSjg3x1FzmZCFsd3AaINLokbTQF6mHt1mPBRfTbZCJODquYkb3odtVogxYZAFVLZB5iNF1778UmZC8vNG4IZCKoI9pQJe6EfvZBLA2Vxg5vddzkL0AZAdfPFHAG9F4ZCKzZCZAZBtyzKqEhodoZCUypV1N00AVO9ZBczkLe9i2DK8DTvNtFANrRm1Wtg0uiUseTyD5TZB3x2CYGdgdimR9i1tIzGZAZCXaGzMsiRL2VnFSDpsSJFAeFOQrdmwBBUUo1ShbCDSAZDZD")
    WHATSAPP_PHONE_NUMBER_ID = os.getenv("WHATSAPP_PHONE_NUMBER_ID", "954105454461091")
    WHATSAPP_VERIFY_TOKEN = os.getenv("WHATSAPP_VERIFY_TOKEN", "udyfoods_verify")

    # Ollama (local LLM)
    OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.2:3b")

    # Database
    DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./messages.db")  # SQLite

    # SMTP (for dashboard invites – not used by bot, but kept for future)
    SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
    SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
    SMTP_USER = os.getenv("SMTP_USER", "myworkflow53@gmail.com")
    SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "nmatumzrhuazryos")
    SMTP_USE_TLS = os.getenv("SMTP_USE_TLS", "True").lower() == "true"
    DASHBOARD_BASE_URL = os.getenv("DASHBOARD_BASE_URL", "https://your-ngrok-url.ngrok.io")

    # Default delivery fee (used if location not found)
    DEFAULT_DELIVERY_FEE = 1000