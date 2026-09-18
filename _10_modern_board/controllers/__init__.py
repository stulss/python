"""컨트롤러(블루프린트) 패키지 묶음.
app.py 가 all_blueprints 목록을 한 번에 등록합니다.
"""
from .admin_controller import admin_bp
from .auth_controller import auth_bp
from .gold_controller import gold_bp
from .page_controller import page_bp
from .post_controller import post_bp
from .public_controller import public_bp, openapi_bp
from .security_controller import security_bp
from .n8n_controller import n8n_bp

all_blueprints = (
    page_bp,
    auth_bp,
    post_bp,
    security_bp,
    admin_bp,
    gold_bp,
    public_bp,
    openapi_bp,
    n8n_bp,
)

__all__ = [
    'all_blueprints',
    'page_bp',
    'auth_bp',
    'post_bp',
    'security_bp',
    'admin_bp',
    'gold_bp',
    'public_bp',
    'openapi_bp',
    'n8n_bp',
]
