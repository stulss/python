from auth import jwt_required, optional_jwt
from db import get_db_connection
from flask import Blueprint, g, jsonify, request

post_bp = Blueprint("posts", __name__, url_prefix="/api")

CATEGORIES = ["공지", "자유", "질문", "팁", "정보", "보안"]


def format_post(row):
  """Post 날짜 필드 문자열 포맷팅"""
  if not row:
    return None
  post = dict(row)
  if "created_at" in post and post["created_at"]:
    post["created_at"] = post["created_at"].strftime("%Y-%m-%d %H:%M")
  if "updated_at" in post and post["updated_at"]:
    post["updated_at"] = post["updated_at"].strftime("%Y-%m-%d %H:%M")
  return post


@post_bp.route("/categories", methods=["GET"])
def get_categories():
  """카테고리 목록 및 카테고리별 게시글 수 조회"""
  conn = get_db_connection()
  try:
    with conn.cursor() as cursor:
      cursor.execute("""
                SELECT category, COUNT(*) as count 
                FROM posts 
                GROUP BY category;
            """)
      counts = {row["category"]: row["count"] for row in cursor.fetchall()}

      cursor.execute("SELECT COUNT(*) as total FROM posts;")
      total = cursor.fetchone()["total"]

      category_list = [{"name": "전체", "count": total}]
      for cat in CATEGORIES:
        category_list.append({"name": cat, "count": counts.get(cat, 0)})

      return jsonify({"success": True, "categories": category_list})
  except Exception as e:
    return jsonify({"success": False, "message": str(e)}), 500
  finally:
    conn.close()


@post_bp.route("/posts", methods=["GET"])
def get_posts():
  """게시글 목록 조회 (커서 기반 페이징, 카테고리 필터, 검색 지원)

  Query Params:
      - cursor: 이전 페이지의 마지막 게시글 id (기본값: None -> 최신 글부터)
      - limit: 가져올 개수 (기본값: 6, 최대 50)
      - category: 카테고리 필터 (기본값: 전체)
      - search: 검색어
      - search_type: 검색 조건 ('all', 'title', 'content', 'author')
  """
  cursor_id = request.args.get("cursor", type=int)
  limit = min(request.args.get("limit", default=6, type=int), 50)
  category = request.args.get("category", default="전체", type=str).strip()
  search = request.args.get("search", default="", type=str).strip()
  search_type = request.args.get("search_type", default="all", type=str).strip()

  conn = get_db_connection()
  try:
    with conn.cursor() as cursor:
      where_clauses = ["1=1"]
      params = []

      # 1. 카테고리 필터
      if category and category != "전체":
        where_clauses.append("p.category = %s")
        params.append(category)

      # 2. 검색 조건 필터
      if search:
        search_pattern = f"%{search}%"
        if search_type == "title":
          where_clauses.append("p.title LIKE %s")
          params.append(search_pattern)
        elif search_type == "content":
          where_clauses.append("p.content LIKE %s")
          params.append(search_pattern)
        elif search_type == "author":
          where_clauses.append("(u.nickname LIKE %s OR u.username LIKE %s)")
          params.extend([search_pattern, search_pattern])
        else:  # all
          where_clauses.append(
              "(p.title LIKE %s OR p.content LIKE %s OR u.nickname LIKE %s)"
          )
          params.extend([search_pattern, search_pattern, search_pattern])

      # 3. 커서 조건 (커서 기반 페이징의 핵심: id < cursor)
      if cursor_id:
        where_clauses.append("p.id < %s")
        params.append(cursor_id)

      where_sql = " AND ".join(where_clauses)

      # limit + 1 개를 조회하여 다음 페이지 존재 여부 확인
      query = f"""
                SELECT 
                    p.id, p.user_id, p.title, p.content, p.category, 
                    p.views, p.created_at, p.updated_at,
                    u.nickname AS author_nickname, u.username AS author_username
                FROM posts p
                JOIN users u ON p.user_id = u.id
                WHERE {where_sql}
                ORDER BY p.id DESC
                LIMIT %s;
            """
      params.append(limit + 1)

      cursor.execute(query, tuple(params))
      rows = cursor.fetchall()

      has_more = len(rows) > limit
      items = rows[:limit] if has_more else rows
      next_cursor = items[-1]["id"] if (has_more and items) else None

      # 전체 일치 개수 카운트 (검색/필터 상태 기준)
      count_where = [
          c for c in where_clauses if not c.startswith("p.id <")
      ]  # 커서 조건 제외
      count_params = (
          params[:-2]
          if cursor_id
          else (params[:-1] if len(params) > 0 else [])
      )
      count_sql = " AND ".join(count_where)

      cursor.execute(
          f"""
                SELECT COUNT(*) as total_count 
                FROM posts p 
                JOIN users u ON p.user_id = u.id 
                WHERE {count_sql};
            """,
          tuple(count_params),
      )
      total_count = cursor.fetchone()["total_count"]

      formatted_items = [format_post(item) for item in items]

      return jsonify({
          "success": True,
          "items": formatted_items,
          "has_more": has_more,
          "next_cursor": next_cursor,
          "limit": limit,
          "total_count": total_count,
      })
  except Exception as e:
    return jsonify({"success": False, "message": f"서버 오류: {str(e)}"}), 500
  finally:
    conn.close()


@post_bp.route("/posts/<int:post_id>", methods=["GET"])
@optional_jwt
def get_post_detail(post_id):
  """게시글 상세 조회 REST API (조회수 1 증가)"""
  conn = get_db_connection()
  try:
    with conn.cursor() as cursor:
      # 조회수 1 증가
      cursor.execute(
          "UPDATE posts SET views = views + 1 WHERE id = %s;", (post_id,)
      )
      conn.commit()

      # 게시글 상세 조회
      cursor.execute(
          """
                SELECT 
                    p.id, p.user_id, p.title, p.content, p.category, 
                    p.views, p.created_at, p.updated_at,
                    u.nickname AS author_nickname, u.username AS author_username
                FROM posts p
                JOIN users u ON p.user_id = u.id
                WHERE p.id = %s
                LIMIT 1;
            """,
          (post_id,),
      )
      post = cursor.fetchone()

      if not post:
        return (
            jsonify({
                "success": False,
                "message": "해당 게시글을 찾을 수 없습니다.",
            }),
            404,
        )

      formatted = format_post(post)

      # 현재 사용자가 작성자인지 여부 플래그
      is_author = False
      if g.current_user and g.current_user["id"] == post["user_id"]:
        is_author = True

      formatted["is_author"] = is_author

      return jsonify({"success": True, "post": formatted})
  except Exception as e:
    conn.rollback()
    return jsonify({"success": False, "message": f"서버 오류: {str(e)}"}), 500
  finally:
    conn.close()


@post_bp.route("/posts", methods=["POST"])
@jwt_required
def create_post():
  """게시글 작성 REST API (JWT 인증 필요)"""
  data = request.get_json() or {}
  title = data.get("title", "").strip()
  content = data.get("content", "").strip()
  category = data.get("category", "일반").strip()

  if not title or not content:
    return (
        jsonify({
            "success": False,
            "message": "제목과 내용을 모두 입력해주세요.",
        }),
        400,
    )

  if category not in CATEGORIES:
    category = "일반"

  user_id = g.current_user["id"]

  conn = get_db_connection()
  try:
    with conn.cursor() as cursor:
      cursor.execute(
          """
                INSERT INTO posts (user_id, title, content, category)
                VALUES (%s, %s, %s, %s);
            """,
          (user_id, title, content, category),
      )
      post_id = cursor.lastrowid
      conn.commit()

      return (
          jsonify({
              "success": True,
              "message": "게시글이 성공적으로 등록되었습니다.",
              "post_id": post_id,
          }),
          201,
      )
  except Exception as e:
    conn.rollback()
    return jsonify({"success": False, "message": f"서버 오류: {str(e)}"}), 500
  finally:
    conn.close()


@post_bp.route("/posts/<int:post_id>", methods=["PUT"])
@jwt_required
def update_post(post_id):
  """게시글 수정 REST API (작성자 본인 검증)"""
  data = request.get_json() or {}
  title = data.get("title", "").strip()
  content = data.get("content", "").strip()
  category = data.get("category", "일반").strip()

  if not title or not content:
    return (
        jsonify({
            "success": False,
            "message": "제목과 내용을 모두 입력해주세요.",
        }),
        400,
    )

  conn = get_db_connection()
  try:
    with conn.cursor() as cursor:
      cursor.execute(
          "SELECT user_id FROM posts WHERE id = %s LIMIT 1;", (post_id,)
      )
      post = cursor.fetchone()

      if not post:
        return (
            jsonify({
                "success": False,
                "message": "존재하지 않는 게시글입니다.",
            }),
            404,
        )

      if post["user_id"] != g.current_user["id"]:
        return (
            jsonify({
                "success": False,
                "message": "본인이 작성한 글만 수정할 수 있습니다.",
            }),
            403,
        )

      cursor.execute(
          """
                UPDATE posts 
                SET title = %s, content = %s, category = %s
                WHERE id = %s;
            """,
          (title, content, category, post_id),
      )
      conn.commit()

      return jsonify(
          {"success": True, "message": "게시글이 성공적으로 수정되었습니다."}
      )
  except Exception as e:
    conn.rollback()
    return jsonify({"success": False, "message": f"서버 오류: {str(e)}"}), 500
  finally:
    conn.close()


@post_bp.route("/posts/<int:post_id>", methods=["DELETE"])
@jwt_required
def delete_post(post_id):
  """게시글 삭제 REST API (작성자 본인 검증)"""
  conn = get_db_connection()
  try:
    with conn.cursor() as cursor:
      cursor.execute(
          "SELECT user_id FROM posts WHERE id = %s LIMIT 1;", (post_id,)
      )
      post = cursor.fetchone()

      if not post:
        return (
            jsonify({
                "success": False,
                "message": "존재하지 않는 게시글입니다.",
            }),
            404,
        )

      if post["user_id"] != g.current_user["id"]:
        return (
            jsonify({
                "success": False,
                "message": "본인이 작성한 글만 삭제할 수 있습니다.",
            }),
            403,
        )

      cursor.execute("DELETE FROM posts WHERE id = %s;", (post_id,))
      conn.commit()

      return jsonify(
          {"success": True, "message": "게시글이 성공적으로 삭제되었습니다."}
      )
  except Exception as e:
    conn.rollback()
    return jsonify({"success": False, "message": f"서버 오류: {str(e)}"}), 500
  finally:
    conn.close()
