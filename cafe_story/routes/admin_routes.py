from flask import Blueprint, request, jsonify, g
from db import get_db_connection
from auth import role_required
from config import Config

admin_bp = Blueprint("admin", __name__, url_prefix="/api/admin")


@admin_bp.route("/users", methods=["GET"])
@role_required(min_level=2)  # 관리자(Lv.2)만 접근 가능!
def get_all_users():
    """
    관리자 전용: 전체 회원 목록 및 등급별 통계 조회
    - 요구사항: 회원정보를 불러와서 화면에 출력
    """
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            # 1. 전체 회원 목록 조회
            cursor.execute("""
                SELECT id, username, nickname, role_level, created_at
                FROM cafe_users 
                ORDER BY role_level DESC, id ASC;
            """)
            users = cursor.fetchall()

            for u in users:
                lvl = int(u["role_level"])
                u["role_name"] = Config.ROLE_NAMES.get(lvl, "일반회원")
                if u.get("created_at"):
                    u["created_at"] = str(u["created_at"])[:16]


            # 2. 통계 계산
            total = len(users)
            user_cnt = sum(1 for u in users if u["role_level"] == 0)
            gold_cnt = sum(1 for u in users if u["role_level"] == 1)
            admin_cnt = sum(1 for u in users if u["role_level"] == 2)

            return jsonify({
                "success": True,
                "users": users,
                "stats": {
                    "total": total,
                    "user_count": user_cnt,
                    "gold_count": gold_cnt,
                    "admin_count": admin_cnt
                }
            })
    except Exception as e:
        return jsonify({"success": False, "message": f"회원 목록 조회 실패: {str(e)}"}), 500
    finally:
        conn.close()


@admin_bp.route("/users/<int:user_id>/role", methods=["PUT", "PATCH"])
@role_required(min_level=2)  # 관리자(Lv.2)만 수정 가능!
def update_user_role(user_id):
    """
    관리자 전용: 회원 등급(role_level) 변경
    - 요구사항: 0: 일반, 1: 골드, 2: 관리자 수정 가능
    """
    data = request.get_json() or {}
    new_role = data.get("role_level")

    if new_role is None or new_role not in (0, 1, 2, "0", "1", "2"):
        return jsonify({"success": False, "message": "유효한 등급(0: 일반, 1: 골드, 2: 관리자)을 지정해주세요."}), 400

    new_role = int(new_role)

    # 자기 자신(현재 로그인한 관리자)의 등급을 강등하는 것은 방지 (운영자 잠금 방지 안전장치)
    if g.current_user["id"] == user_id and new_role < 2:
        return jsonify({"success": False, "message": "현재 로그인 중인 본인의 관리자 권한은 직접 강등할 수 없습니다."}), 400

    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            # 대상 유저 확인
            cursor.execute("SELECT id, username, nickname, role_level FROM cafe_users WHERE id = %s;", (user_id,))
            target = cursor.fetchone()
            if not target:
                return jsonify({"success": False, "message": "존재하지 않는 회원입니다."}), 404

            old_role = target["role_level"]
            cursor.execute("UPDATE cafe_users SET role_level = %s WHERE id = %s;", (new_role, user_id))
            conn.commit()

            old_name = Config.ROLE_NAMES.get(old_role, "알수없음")
            new_name = Config.ROLE_NAMES.get(new_role, "알수없음")

            return jsonify({
                "success": True,
                "message": f"[{target['nickname']}] 님의 등급이 '{old_name}(Lv.{old_role})'에서 '{new_name}(Lv.{new_role})' (으)로 성공적으로 변경되었습니다.",
                "user": {
                    "id": user_id,
                    "username": target["username"],
                    "nickname": target["nickname"],
                    "role_level": new_role,
                    "role_name": new_name
                }
            })
    except Exception as e:
        conn.rollback()
        return jsonify({"success": False, "message": f"등급 변경 실패: {str(e)}"}), 500
    finally:
        conn.close()


@admin_bp.route("/users/<int:user_id>", methods=["DELETE"])
@role_required(min_level=2)  # 관리자(Lv.2)만 삭제 가능!
def delete_user(user_id):
    """
    관리자 전용: 회원 삭제
    - 요구사항: 회원정보 삭제 가능하게 하기
    """
    # 자기 자신 삭제 방지
    if g.current_user["id"] == user_id:
        return jsonify({"success": False, "message": "현재 로그인 중인 본인 계정은 삭제할 수 없습니다."}), 400

    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT id, username, nickname FROM cafe_users WHERE id = %s;", (user_id,))
            target = cursor.fetchone()
            if not target:
                return jsonify({"success": False, "message": "존재하지 않는 회원입니다."}), 404

            cursor.execute("DELETE FROM cafe_users WHERE id = %s;", (user_id,))
            conn.commit()

            return jsonify({
                "success": True,
                "message": f"회원 [{target['nickname']}({target['username']})] 님이 정상적으로 삭제되었습니다."
            })
    except Exception as e:
        conn.rollback()
        return jsonify({"success": False, "message": f"회원 삭제 실패: {str(e)}"}), 500
    finally:
        conn.close()
