"""등급별 접근제어(RBAC) 공용 규칙 — 한 곳에서만 판정합니다.

등급 체계: user(1) < gold(2) < admin(3)
  · 필요 등급보다 내 등급이 같거나 높으면 통과
  · admin 은 골드 화면/기능도 이용 가능
  · 401 = 인증 실패 (미로그인)
  · 403 = 인가 실패 (권한 부족)
"""
from functools import wraps
from flask import jsonify, request
from flask_jwt_extended import get_jwt_identity, verify_jwt_in_request

from extensions import db
from models.user import User, ROLE_LEVEL, ROLE_LABEL, VALID_ROLES, role_level


def current_user():
    """JWT 가 유효하면 해당 User 객체 반환, 없거나 유효하지 않으면 None 반환."""
    try:
        verify_jwt_in_request(optional=True)
    except Exception:
        return None
    uid = get_jwt_identity()
    if not uid:
        return None
    try:
        return db.session.get(User, int(uid))
    except (TypeError, ValueError):
        return None


def role_required(required):
    """required 등급 이상만 통과시키는 데코레이터.
    미로그인 시 401, 등급 부족 시 403 반환.
    """
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            user = current_user()
            if user is None:
                return jsonify({
                    'msg': '로그인이 필요합니다.',
                    'error': '로그인이 필요합니다.',
                    'required_role': required,
                    'current_role': None,
                }), 401
            if role_level(user.role) < role_level(required):
                return jsonify({
                    'msg': f'{ROLE_LABEL.get(required, required)} 등급 이상만 이용할 수 있습니다.',
                    'error': f'{ROLE_LABEL.get(required, required)} 등급 이상만 이용할 수 있습니다.',
                    'required_role': required,
                    'current_role': user.role,
                }), 403
            request.current_user = user
            return fn(*args, **kwargs)
        return wrapper
    return decorator
