import os
from datetime import timedelta
from dotenv import load_dotenv

# .env 로드
load_dotenv()

class Config:
    SECRET_KEY = os.getenv('SECRET_KEY', 'default-dev-secret-key-2026')
    
    # Database
    SQLALCHEMY_DATABASE_URI = os.getenv(
        'DATABASE_URL', 
        'mysql+pymysql://root:123456@localhost:3306/modern_board_db'
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_recycle': 280,
        'pool_pre_ping': True,
    }
    
    # JWT Settings
    JWT_SECRET_KEY = os.getenv('JWT_SECRET_KEY', 'jwt-super-secret-key-2026')
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(
        minutes=int(os.getenv('JWT_ACCESS_TOKEN_EXPIRES_MINUTES', 1440))
    )
    JWT_HEADER_NAME = 'Authorization'
    JWT_HEADER_TYPE = 'Bearer'
    
    # Application settings
    JSON_AS_ASCII = False
    
    # n8n SOAR Integration
    N8N_API_KEY = os.getenv('N8N_API_KEY', '')
    N8N_BASE_URL = os.getenv('N8N_BASE_URL', 'http://localhost:5678/api/v1')
    N8N_WEBHOOK_URL_SECURITY = os.getenv('N8N_WEBHOOK_URL_SECURITY', 'http://localhost:5678/webhook/c0ab8317-528d-4a1f-a354-2719862ce37f')
    N8N_WEBHOOK_URL_REVOKE = os.getenv('N8N_WEBHOOK_URL_REVOKE', 'http://localhost:5678/webhook/5297c4cd-f3a1-48d5-8e88-efb0e21b7367')

    # Security & Admin API Keys (다중 키 지원)
    SECURITY_API_KEY = os.getenv('SECURITY_API_KEY', '')
    _sec_keys_raw = os.getenv('SECURITY_API_KEYS', '')
    SECURITY_API_KEYS = [k.strip() for k in _sec_keys_raw.split(',') if k.strip()] if _sec_keys_raw else ([SECURITY_API_KEY] if SECURITY_API_KEY else [])

    ADMIN_API_KEY = os.getenv('ADMIN_API_KEY', '')
    _adm_keys_raw = os.getenv('ADMIN_API_KEYS', '')
    ADMIN_API_KEYS = [k.strip() for k in _adm_keys_raw.split(',') if k.strip()] if _adm_keys_raw else ([ADMIN_API_KEY] if ADMIN_API_KEY else [])

    ADMIN_ALLOWLIST = [a.strip() for a in os.getenv('ADMIN_ALLOWLIST', 'admin,lsy,instructor,soarbot').split(',') if a.strip()]
    AUTO_POST_ON_DENY = os.getenv('AUTO_POST_ON_DENY', '1') == '1'

    # Graylog (SIEM)
    GELF_HOST = os.getenv('GELF_HOST', 'localhost')
    GELF_PORT = int(os.getenv('GELF_PORT', 12201))

    # Public API
    PUBLIC_API_KEY = os.getenv('PUBLIC_API_KEY', '')
    OPENAPI_SERVICE_KEY = os.getenv('PUBLIC_API_KEY', os.getenv('OPENAPI_SERVICE_KEY', ''))
