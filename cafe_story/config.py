import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env", override=True)


class Config:
    """카페이야기 애플리케이션 환경설정"""

    # DB Config
    DB_HOST = os.getenv("DB_HOST", "localhost")
    DB_PORT = int(os.getenv("DB_PORT", 3306))
    DB_USER = os.getenv("DB_USER", "root")
    DB_PASSWORD = os.getenv("DB_PASSWORD", "123456")
    DB_NAME = os.getenv("DB_NAME", "cafe_story_db")

    # JWT Config
    JWT_SECRET_KEY = os.getenv(
        "JWT_SECRET_KEY", "cafe_story_rbac_super_secret_key_2026_!@#$"
    )
    JWT_EXPIRES_HOURS = int(os.getenv("JWT_EXPIRES_HOURS", 24))

    # Flask Config
    PORT = int(os.getenv("FLASK_PORT", 5000))
    DEBUG = os.getenv("FLASK_DEBUG", "True").lower() in ("true", "1", "yes")

    # 쿠키 이름
    COOKIE_NAME = "cafe_token"

    # 권한 레벨 정의
    ROLE_USER = 0    # 일반유저 (최초 가입 기본)
    ROLE_GOLD = 1    # 골드유저 (중간 관리자)
    ROLE_ADMIN = 2   # 관리자 (운영자)

    ROLE_NAMES = {
        0: "일반회원",
        1: "골드회원",
        2: "관리자"
    }

    ROLE_BADGES = {
        0: {"name": "일반회원", "level": 0, "class": "bg-emerald-100 text-emerald-800 border-emerald-300", "icon": "fa-seedling"},
        1: {"name": "골드회원", "level": 1, "class": "bg-amber-100 text-amber-900 border-amber-400 font-bold", "icon": "fa-crown"},
        2: {"name": "관리자", "level": 2, "class": "bg-rose-100 text-rose-800 border-rose-400 font-bold", "icon": "fa-shield-halved"}
    }
