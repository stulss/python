from flask import Blueprint, render_template, g, request
from auth import optional_jwt, role_required
from config import Config

page_bp = Blueprint("pages", __name__)


@page_bp.route("/")
@optional_jwt
def index():
    """카페이야기 메인 페이지 (누구나 접근 가능)"""
    return render_template(
        "index.html",
        current_user=g.current_user,
        role_badges=Config.ROLE_BADGES,
        role_names=Config.ROLE_NAMES
    )


@page_bp.route("/gold")
@role_required(min_level=1, is_page=True)  # 골드(Lv.1) 이상 필수, 부족 시 error_role.html(403) 렌더링!
def gold_lounge():
    """골드 라운지 페이지 (골드 Lv.1, 관리자 Lv.2 만 접근 가능)"""
    return render_template(
        "gold.html",
        current_user=g.current_user,
        role_badges=Config.ROLE_BADGES,
        role_names=Config.ROLE_NAMES
    )


@page_bp.route("/admin")
@role_required(min_level=2, is_page=True)  # 관리자(Lv.2) 필수, 부족 시 error_role.html(403) 렌더링!
def admin_center():
    """관리자 센터 페이지 (관리자 Lv.2 만 접근 가능)"""
    return render_template(
        "admin.html",
        current_user=g.current_user,
        role_badges=Config.ROLE_BADGES,
        role_names=Config.ROLE_NAMES
    )


@page_bp.route("/unauthorized")
@optional_jwt
def unauthorized():
    """권한 부족 안내 범용 페이지"""
    reason = request.args.get("reason", "접근 권한이 없습니다.")
    return render_template(
        "error_role.html",
        error_type="custom",
        message=reason,
        current_user=g.current_user,
        required_level=1,
        required_name="필요 등급"
    ), 403


@page_bp.route("/switch-account")
def switch_account():
    """테스트 및 스크린샷 캡처용 계정 즉시 전환 헬퍼 라우트"""
    from flask import redirect, make_response
    from auth import generate_token
    from db import get_db_connection

    username = request.args.get("user", "user1")
    next_url = request.args.get("next", "/")

    resp = make_response(redirect(next_url))

    if username == "guest":
        resp.delete_cookie(Config.COOKIE_NAME, path="/")
        return resp

    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT id, username, nickname, role_level FROM cafe_users WHERE username = %s LIMIT 1;", (username,))
            user = cursor.fetchone()
            if user:
                token = generate_token(user["id"], user["username"], user["nickname"], user["role_level"])
                resp.set_cookie(Config.COOKIE_NAME, token, max_age=86400, path="/", httponly=False)
    finally:
        conn.close()

    return resp


@page_bp.route("/db-view")
def db_view():
    """DB 권한 상태 증빙 뷰"""
    return render_template("real_terminal.html")


@page_bp.route("/browser-view")
def browser_view():
    """실제 브라우저 프레임 뷰"""
    return render_template("browser_frame.html")



