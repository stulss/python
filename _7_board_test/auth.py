from datetime import datetime, timedelta, timezone
from functools import wraps
from flask import g, jsonify, request
import jwt
from config import Config


def generate_token(user_id: int, username: str, nickname: str) -> str:
  """JWT 토큰 생성 (sub 클레임은 문자열로 저장)"""
  now = datetime.now(timezone.utc)
  payload = {
      "sub": str(user_id),
      "username": username,
      "nickname": nickname,
      "iat": now,
      "exp": now + timedelta(hours=Config.JWT_EXPIRES_HOURS),
  }
  token = jwt.encode(payload, Config.JWT_SECRET_KEY, algorithm="HS256")
  return token


def decode_token(token: str):
  """JWT 토큰 검증 및 디코딩"""
  try:
    payload = jwt.decode(token, Config.JWT_SECRET_KEY, algorithms=["HS256"])
    return payload, None
  except jwt.ExpiredSignatureError:
    return None, "토큰이 만료되었습니다. 다시 로그인해주세요."
  except jwt.InvalidTokenError as e:
    return None, f"유효하지 않은 토큰입니다: {str(e)}"


def get_token_from_header():
  """HTTP Authorization 헤더에서 Bearer 토큰 추출"""
  auth_header = request.headers.get("Authorization")
  if not auth_header:
    return None, "Authorization 헤더가 필요합니다."

  parts = auth_header.split()
  if len(parts) != 2 or parts[0].lower() != "bearer":
    return None, "Authorization 헤더 형식은 'Bearer <token>' 이어야 합니다."

  return parts[1], None


def jwt_required(f):
  """JWT 인증 필수 데코레이터"""

  @wraps(f)
  def decorated_function(*args, **kwargs):
    token, err = get_token_from_header()
    if err:
      return (
          jsonify({"success": False, "message": err, "error_code": "NO_TOKEN"}),
          401,
      )

    payload, err = decode_token(token)
    if err:
      return (
          jsonify({
              "success": False,
              "message": err,
              "error_code": "INVALID_TOKEN",
          }),
          401,
      )

    # Flask 전역 g 객체에 현재 인증된 사용자 정보 저장 (id를 정수로 변환)
    g.current_user = {
        "id": int(payload["sub"]),
        "username": payload["username"],
        "nickname": payload["nickname"],
    }
    return f(*args, **kwargs)

  return decorated_function


def optional_jwt(f):
  """JWT 토큰이 있으면 사용자 정보를 넣고 없어도 통과하는 데코레이터"""

  @wraps(f)
  def decorated_function(*args, **kwargs):
    g.current_user = None
    token, err = get_token_from_header()
    if token and not err:
      payload, _ = decode_token(token)
      if payload:
        g.current_user = {
            "id": int(payload["sub"]),
            "username": payload["username"],
            "nickname": payload["nickname"],
        }
    return f(*args, **kwargs)

  return decorated_function
