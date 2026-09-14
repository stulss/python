from datetime import datetime, timedelta, timezone
from functools import wraps
from flask import g, jsonify, request, render_template, redirect, url_for
import jwt
from config import Config


def generate_token(user_id: int, username: str, nickname: str, role_level: int) -> str:
    """JWT 토큰 생성 (사용자 ID, 이름, 닉네임, 등급 레벨 포함)"""
    now = datetime.now(timezone.utc)
    role_name = Config.ROLE_NAMES.get(role_level, "일반회원")
    payload = {
        "sub": str(user_id),
        "username": username,
        "nickname": nickname,
        "role_level": int(role_level),
        "role_name": role_name,
        "iat": now,
        "exp": now + timedelta(hours=Config.JWT_EXPIRES_HOURS),
    }
    return jwt.encode(payload, Config.JWT_SECRET_KEY, algorithm="HS256")


def decode_token(token: str):
    """JWT 토큰 검증 및 디코딩"""
    try:
        payload = jwt.decode(token, Config.JWT_SECRET_KEY, algorithms=["HS256"])
        return payload, None
    except jwt.ExpiredSignatureError:
        return None, "토큰이 만료되었습니다. 다시 로그인해주세요."
    except jwt.InvalidTokenError as e:
        return None, f"유효하지 않은 토큰입니다: {str(e)}"


def get_token_from_request():
    """Authorization 헤더 또는 쿠키에서 JWT 토큰 추출"""
    # 1. Authorization: Bearer <token> 헤더 확인
    auth_header = request.headers.get("Authorization")
    if auth_header:
        parts = auth_header.split()
        if len(parts) == 2 and parts[0].lower() == "bearer":
            return parts[1], None

    # 2. 브라우저 쿠키 cafe_token 확인
    token_cookie = request.cookies.get(Config.COOKIE_NAME)
    if token_cookie:
        return token_cookie, None

    return None, "인증 토큰이 제공되지 않았습니다."


def parse_user_from_token():
    """요청에서 토큰을 추출하여 사용자 정보 반환 (실패 시 None)"""
    token, err = get_token_from_request()
    if not token or err:
        return None
    payload, err = decode_token(token)
    if err or not payload:
        return None
    return {
        "id": int(payload["sub"]),
        "username": payload["username"],
        "nickname": payload["nickname"],
        "role_level": int(payload.get("role_level", 0)),
        "role_name": payload.get("role_name", Config.ROLE_NAMES.get(int(payload.get("role_level", 0)), "일반회원")),
    }


def jwt_required(f):
    """로그인 인증 필수 데코레이터 (API용)"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        user = parse_user_from_token()
        if not user:
            return (
                jsonify({"success": False, "message": "로그인이 필요한 서비스입니다.", "error_code": "UNAUTHORIZED"}),
                401,
            )
        g.current_user = user
        return f(*args, **kwargs)
    return decorated_function


def optional_jwt(f):
    """토큰이 있으면 유저 정보 세팅, 없어도 진행 (공통 페이지용)"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        g.current_user = parse_user_from_token()
        return f(*args, **kwargs)
    return decorated_function


def role_required(min_level: int, is_page: bool = False):
    """
    인가/접근 제어 데코레이터
    - min_level: 0 (일반), 1 (골드 이상), 2 (관리자만)
    - is_page: True면 HTML 예외화면(403) 렌더링, False면 JSON 403 반환
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            user = parse_user_from_token()
            g.current_user = user

            # 1. 비로그인 상태일 때
            if not user:
                if is_page:
                    return render_template(
                        "error_role.html",
                        error_type="unauthenticated",
                        required_level=min_level,
                        required_name=Config.ROLE_NAMES.get(min_level, "회원"),
                        current_user=None,
                        message="이 페이지에 접근하려면 먼저 로그인이 필요합니다."
                    ), 401
                return jsonify({
                    "success": False,
                    "message": "로그인이 필요합니다.",
                    "error_code": "UNAUTHORIZED"
                }), 401

            # 2. 권한 레벨 체크 (user['role_level'] < min_level)
            if user["role_level"] < min_level:
                req_name = Config.ROLE_NAMES.get(min_level, "필요 등급")
                cur_name = user["role_name"]
                if is_page:
                    return render_template(
                        "error_role.html",
                        error_type="forbidden",
                        required_level=min_level,
                        required_name=req_name,
                        current_user=user,
                        message=f"접근 권한이 없습니다! [{req_name} (Lv.{min_level})] 이상만 접근 가능합니다. (현재 등급: {cur_name} Lv.{user['role_level']})"
                    ), 403
                return jsonify({
                    "success": False,
                    "message": f"접근 권한이 부족합니다. [{req_name} (Lv.{min_level})] 이상만 이용할 수 있습니다.",
                    "current_role": user["role_level"],
                    "required_role": min_level,
                    "error_code": "FORBIDDEN"
                }), 403

            return f(*args, **kwargs)
        return decorated_function
    return decorator
