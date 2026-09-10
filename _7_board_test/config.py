import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env file from current directory
BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env", override=True)


class Config:
  """Application Configuration"""

  # DB Config
  DB_HOST = os.getenv("DB_HOST", "localhost")
  DB_PORT = int(os.getenv("DB_PORT", 3306))
  DB_USER = os.getenv("DB_USER", "root")
  DB_PASSWORD = os.getenv("DB_PASSWORD", "123456")
  DB_NAME = os.getenv("DB_NAME", "board_db")

  # JWT Config
  JWT_SECRET_KEY = os.getenv(
      "JWT_SECRET_KEY", "board_super_secret_jwt_key_2026_!@#$%"
  )
  JWT_EXPIRES_HOURS = int(os.getenv("JWT_EXPIRES_HOURS", 24))

  # Public Open API Config (data.go.kr)
  OPENAPI_SERVICE_KEY = os.getenv(
      "OPENAPI_SERVICE_KEY",
      "XCwvFxJAAOHXzppLdloapsDqYy3PjNXTLTkF7dY5q13G2%2B1gNPxWZPU%2BU3x5mEtISC8ComH1N1Ti%2BIqbyQsKIg%3D%3D"
  )

  # Flask Config
  PORT = int(os.getenv("FLASK_PORT", 5000))
  DEBUG = os.getenv("FLASK_DEBUG", "True").lower() in ("true", "1", "yes")

  # 보안 이벤트 REST 용 API 키 (n8n 이 공유) — 비어 있으면 POST 는 항상 401 (fail-closed)
  SECURITY_API_KEY = os.getenv("SECURITY_API_KEY", "")

  @classmethod
  def get_db_dict(cls, include_db=True):
    conf = {
        "host": cls.DB_HOST,
        "port": cls.DB_PORT,
        "user": cls.DB_USER,
        "password": cls.DB_PASSWORD,
        "charset": "utf8mb4",
    }
    if include_db:
      conf["database"] = cls.DB_NAME
    return conf
