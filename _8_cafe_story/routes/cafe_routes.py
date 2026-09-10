from flask import Blueprint, request, jsonify, g
from db import get_db_connection
from auth import jwt_required, role_required
from config import Config

cafe_bp = Blueprint("cafe", __name__, url_prefix="/api")


@cafe_bp.route("/posts", methods=["GET"])
def get_posts():
    """게시글 목록 조회 (모든 사용자/게스트 조회 가능)"""
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT p.id, p.user_id, p.title, p.content, p.category, p.min_role, p.views,
                       p.created_at,
                       u.nickname AS author_nickname, u.username AS author_username, u.role_level AS author_role
                FROM cafe_posts p
                JOIN cafe_users u ON p.user_id = u.id
                ORDER BY p.id DESC;
            """)
            posts = cursor.fetchall()
            for p in posts:
                p["author_role_name"] = Config.ROLE_NAMES.get(p["author_role"], "일반회원")
                if p.get("created_at"):
                    p["created_at"] = str(p["created_at"])[:16]
            return jsonify({"success": True, "posts": posts})

    except Exception as e:
        return jsonify({"success": False, "message": f"게시글 조회 실패: {str(e)}"}), 500
    finally:
        conn.close()


@cafe_bp.route("/posts", methods=["POST"])
@jwt_required
def create_post():
    """게시글 작성 (로그인 유저 전용)"""
    data = request.get_json() or {}
    title = data.get("title", "").strip()
    content = data.get("content", "").strip()
    category = data.get("category", "이야기").strip()
    min_role = int(data.get("min_role", 0))

    if not title or not content:
        return jsonify({"success": False, "message": "제목과 내용을 모두 입력해주세요."}), 400

    # 골드 전용 글인 경우 작성자도 골드 이상이어야 함
    if min_role > g.current_user["role_level"]:
        return jsonify({
            "success": False, 
            "message": f"해당 등급(Lv.{min_role}) 전용 글을 작성할 권한이 없습니다."
        }), 403

    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("""
                INSERT INTO cafe_posts (user_id, title, content, category, min_role)
                VALUES (%s, %s, %s, %s, %s);
            """, (g.current_user["id"], title, content, category, min_role))
            post_id = cursor.lastrowid
            conn.commit()

            return jsonify({
                "success": True,
                "message": "카페 이야기가 등록되었습니다!",
                "post_id": post_id
            }), 201
    except Exception as e:
        conn.rollback()
        return jsonify({"success": False, "message": f"게시글 등록 실패: {str(e)}"}), 500
    finally:
        conn.close()


@cafe_bp.route("/posts/<int:post_id>", methods=["DELETE"])
@jwt_required
def delete_post(post_id):
    """게시글 삭제 (작성자 본인 또는 관리자(Lv.2)만 삭제 가능)"""
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT user_id FROM cafe_posts WHERE id = %s;", (post_id,))
            post = cursor.fetchone()
            if not post:
                return jsonify({"success": False, "message": "존재하지 않는 게시글입니다."}), 404

            # 권한 확인: 본인이거나 관리자
            if post["user_id"] != g.current_user["id"] and g.current_user["role_level"] < 2:
                return jsonify({"success": False, "message": "본인의 글이 아니거나 삭제 권한이 없습니다."}), 403

            cursor.execute("DELETE FROM cafe_posts WHERE id = %s;", (post_id,))
            conn.commit()

            return jsonify({"success": True, "message": "게시글이 삭제되었습니다."})
    except Exception as e:
        conn.rollback()
        return jsonify({"success": False, "message": f"게시글 삭제 실패: {str(e)}"}), 500
    finally:
        conn.close()


@cafe_bp.route("/gold/perks", methods=["GET"])
@role_required(min_level=1)  # 골드회원(Lv.1) 이상만 접근 가능한 API!
def get_gold_perks():
    """골드 등급 전용 혜택 데이터 API"""
    return jsonify({
        "success": True,
        "message": "골드 라운지 혜택 데이터 인증 성공",
        "perks": [
            {"title": "스페셜티 원두 20% 특별 할인", "code": "GOLD-BEAN-2026", "desc": "매장 및 온라인 원두 구매 시 무제한 할인"},
            {"title": "바리스타 시크릿 레시피 열람", "code": "BARISTA-SECRET-99", "desc": "세계 챔피언 핸드드립 추출 튜토리얼"},
            {"title": "카페 중간관리자 안건 투표권", "code": "COUNCIL-VOTE-ON", "desc": "신메뉴 선정 및 정기모임 기획 투표 참여"}
        ]
    })
