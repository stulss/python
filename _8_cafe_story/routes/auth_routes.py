from flask import Blueprint, request, jsonify, make_response, g
from werkzeug.security import generate_password_hash, check_password_hash
from db import get_db_connection
from auth import generate_token, jwt_required, parse_user_from_token
from config import Config

auth_bp = Blueprint("auth", __name__, url_prefix="/api/auth")


@auth_bp.route("/register", methods=["POST"])
def register():
    """
    회원가입 API
    - 요구사항: 최초 가입 시 무조건 '일반 유저' (role_level = 0)로 가입
    """
    data = request.get_json() or {}
    username = data.get("username", "").strip()
    password = data.get("password", "").strip()
    nickname = data.get("nickname", "").strip()

    if not username or not password or not nickname:
        return jsonify({"success": False, "message": "모든 항목을 입력해주세요."}), 400

    if len(username) < 3:
        return jsonify({"success": False, "message": "아이디는 3자 이상이어야 합니다."}), 400

    if len(password) < 4:
        return jsonify({"success": False, "message": "비밀번호는 4자 이상이어야 합니다."}), 400

    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            # 중복 아이디 체크
            cursor.execute("SELECT id FROM cafe_users WHERE username = %s LIMIT 1;", (username,))
            if cursor.fetchone():
                return jsonify({"success": False, "message": "이미 사용 중인 아이디입니다."}), 409

            # 비밀번호 해시 및 일반 회원(role_level=0)으로 강제 저장
            pwd_hash = generate_password_hash(password)
            default_role = Config.ROLE_USER  # 0: 일반유저

            cursor.execute("""
                INSERT INTO cafe_users (username, password_hash, nickname, role_level)
                VALUES (%s, %s, %s, %s);
            """, (username, pwd_hash, nickname, default_role))
            user_id = cursor.lastrowid
            conn.commit()

            # 가입 즉시 자동 로그인 토큰 발급
            token = generate_token(user_id, username, nickname, default_role)
            resp = make_response(jsonify({
                "success": True,
                "message": f"회원가입 성공! {nickname}님 환영합니다. (등급: 일반회원 Lv.0)",
                "token": token,
                "user": {
                    "id": user_id,
                    "username": username,
                    "nickname": nickname,
                    "role_level": default_role,
                    "role_name": Config.ROLE_NAMES[default_role]
                }
            }), 201)

            # 브라우저 페이지 탐색을 위해 쿠키도 함께 세팅
            resp.set_cookie(Config.COOKIE_NAME, token, max_age=86400, path="/", httponly=False)
            return resp
    except Exception as e:
        conn.rollback()
        return jsonify({"success": False, "message": f"서버 오류: {str(e)}"}), 500
    finally:
        conn.close()


@auth_bp.route("/login", methods=["POST"])
def login():
    """
    로그인 API
    - 아이디/비밀번호 확인 후 JWT 토큰 발급 및 쿠키 저장
    """
    data = request.get_json() or {}
    username = data.get("username", "").strip()
    password = data.get("password", "").strip()

    if not username or not password:
        return jsonify({"success": False, "message": "아이디와 비밀번호를 모두 입력해주세요."}), 400

    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT id, username, password_hash, nickname, role_level 
                FROM cafe_users 
                WHERE username = %s LIMIT 1;
            """, (username,))
            user = cursor.fetchone()

            if not user or not check_password_hash(user["password_hash"], password):
                return jsonify({"success": False, "message": "아이디 또는 비밀번호가 일치하지 않습니다."}), 401

            role_level = int(user["role_level"])
            role_name = Config.ROLE_NAMES.get(role_level, "일반회원")

            token = generate_token(user["id"], user["username"], user["nickname"], role_level)

            resp = make_response(jsonify({
                "success": True,
                "message": f"로그인 성공! {user['nickname']}님 환영합니다.",
                "token": token,
                "user": {
                    "id": user["id"],
                    "username": user["username"],
                    "nickname": user["nickname"],
                    "role_level": role_level,
                    "role_name": role_name
                }
            }))

            # 쿠키 세팅 (브라우저 직접 링크 이동 시 인증 유지용)
            resp.set_cookie(Config.COOKIE_NAME, token, max_age=86400, path="/", httponly=False)
            return resp
    except Exception as e:
        return jsonify({"success": False, "message": f"서버 오류: {str(e)}"}), 500
    finally:
        conn.close()


@auth_bp.route("/logout", methods=["POST"])
def logout():
    """로그아웃 API (쿠키 만료)"""
    resp = make_response(jsonify({"success": True, "message": "로그아웃되었습니다."}))
    resp.delete_cookie(Config.COOKIE_NAME, path="/")
    return resp


@auth_bp.route("/me", methods=["GET"])
def get_me():
    """현재 로그인 사용자 정보 조회"""
    user = parse_user_from_token()
    if not user:
        return jsonify({"success": False, "user": None}), 200
    return jsonify({"success": True, "user": user}), 200
