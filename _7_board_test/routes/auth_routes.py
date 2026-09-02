from auth import generate_token, jwt_required
from db import get_db_connection
from flask import Blueprint, g, jsonify, request
from werkzeug.security import check_password_hash, generate_password_hash

auth_bp = Blueprint("auth", __name__, url_prefix="/api/auth")


@auth_bp.route("/register", methods=["POST"])
def register():
  """회원가입 REST API"""
  data = request.get_json() or {}
  username = data.get("username", "").strip()
  password = data.get("password", "").strip()
  nickname = data.get("nickname", "").strip()

  if not username or not password or not nickname:
    return (
        jsonify({"success": False, "message": "모든 필드를 입력해주세요."}),
        400,
    )

  if len(username) < 3:
    return (
        jsonify({
            "success": False,
            "message": "아이디는 최소 3자 이상이어야 합니다.",
        }),
        400,
    )

  if len(password) < 4:
    return (
        jsonify({
            "success": False,
            "message": "비밀번호는 최소 4자 이상이어야 합니다.",
        }),
        400,
    )

  conn = get_db_connection()
  try:
    with conn.cursor() as cursor:
      # 중복 아이디 체크
      cursor.execute(
          "SELECT id FROM users WHERE username = %s LIMIT 1;", (username,)
      )
      if cursor.fetchone():
        return (
            jsonify({
                "success": False,
                "message": "이미 존재하는 아이디입니다.",
            }),
            409,
        )

      # 비밀번호 암호화 후 유저 생성
      pwd_hash = generate_password_hash(password)
      cursor.execute(
          """
                INSERT INTO users (username, password_hash, nickname)
                VALUES (%s, %s, %s);
            """,
          (username, pwd_hash, nickname),
      )
      user_id = cursor.lastrowid
      conn.commit()

      # 회원가입 성공 시 바로 JWT 토큰 발급
      token = generate_token(user_id, username, nickname)
      return (
          jsonify({
              "success": True,
              "message": "회원가입이 완료되었습니다.",
              "token": token,
              "user": {"id": user_id, "username": username, "nickname": nickname},
          }),
          201,
      )
  except Exception as e:
    conn.rollback()
    return jsonify({"success": False, "message": f"서버 오류: {str(e)}"}), 500
  finally:
    conn.close()


@auth_bp.route("/login", methods=["POST"])
def login():
  """로그인 REST API (JWT 토큰 발급)"""
  data = request.get_json() or {}
  username = data.get("username", "").strip()
  password = data.get("password", "").strip()

  if not username or not password:
    return (
        jsonify({
            "success": False,
            "message": "아이디와 비밀번호를 입력해주세요.",
        }),
        400,
    )

  conn = get_db_connection()
  try:
    with conn.cursor() as cursor:
      cursor.execute(
          """
                SELECT id, username, password_hash, nickname 
                FROM users 
                WHERE username = %s LIMIT 1;
            """,
          (username,),
      )
      user = cursor.fetchone()

      if not user or not check_password_hash(user["password_hash"], password):
        return (
            jsonify({
                "success": False,
                "message": "아이디 또는 비밀번호가 일치하지 않습니다.",
            }),
            401,
        )

      # JWT 토큰 생성
      token = generate_token(user["id"], user["username"], user["nickname"])

      return jsonify({
          "success": True,
          "message": f"{user['nickname']}님 환영합니다!",
          "token": token,
          "user": {
              "id": user["id"],
              "username": user["username"],
              "nickname": user["nickname"],
          },
      })
  except Exception as e:
    return jsonify({"success": False, "message": f"서버 오류: {str(e)}"}), 500
  finally:
    conn.close()


@auth_bp.route("/me", methods=["GET"])
@jwt_required
def get_current_user_profile():
  """현재 로그인 사용자 정보 조회 REST API"""
  return jsonify({"success": True, "user": g.current_user})
