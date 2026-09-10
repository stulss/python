"""보안 이벤트 REST — n8n 이 판정한 허용/거부 결과를 저장·조회하는 곳.

인증: 헤더 X-API-Key (사람이 아니라 n8n 봇이 부르므로 로그인 대신 공유 비밀 1개)
"""
import os
from functools import wraps

from config import Config
from db import get_db_connection
from flask import Blueprint, jsonify, request
from werkzeug.security import generate_password_hash

security_bp = Blueprint("security", __name__, url_prefix="/api/security")

BOT_USERNAME = "soarbot"


def _get_or_create_bot_user(cursor):
  """거부(deny) 공지글 작성자로 쓸 시스템 계정. 없으면 만든다."""
  cursor.execute(
      "SELECT id FROM users WHERE username = %s LIMIT 1", (BOT_USERNAME,)
  )
  row = cursor.fetchone()
  if row:
    return row["id"]

  cursor.execute(
      """
            INSERT INTO users (username, password_hash, nickname)
            VALUES (%s, %s, %s)
        """,
      (BOT_USERNAME, generate_password_hash(os.urandom(16).hex()), "보안봇"),
  )
  return cursor.lastrowid


def _create_security_post(cursor, ev):
  """이벤트(허용·거부 모두)를 게시판 '보안' 공지글로 자동 등록."""
  bot_id = _get_or_create_bot_user(cursor)
  if ev["decision"] == "deny":
    title = f"🚫 [보안][{ev['student']}] {ev['src_ip']} 접근 거부 ({ev['severity']})"
  else:
    title = f"✅ [보안][{ev['student']}] {ev['src_ip']} 접근 허용 ({ev['severity']})"
  content = (
      f"{ev.get('reason') or ''}\n"
      f"실패 횟수: {ev.get('fail_count')}\n"
      f"(n8n SOAR 워크플로우가 자동 등록한 글입니다)"
  )
  cursor.execute(
      """
            INSERT INTO posts (user_id, title, content, category)
            VALUES (%s, %s, %s, '보안')
        """,
      (bot_id, title, content),
  )
  return cursor.lastrowid


def require_api_key(fn):
  """X-API-Key 가 설정값과 같을 때만 통과. 키가 비었거나 다르면 401(fail-closed)."""

  @wraps(fn)
  def wrapper(*args, **kwargs):
    expected = Config.SECURITY_API_KEY
    if not expected or request.headers.get("X-API-Key", "") != expected:
      return jsonify({"success": False, "message": "API 키가 없거나 잘못되었습니다."}), 401
    return fn(*args, **kwargs)

  return wrapper


@security_bp.route("/events", methods=["POST"])
@require_api_key
def create_security_event():
  """이벤트 1건 저장. student·src_ip·decision(allow|deny) 은 필수."""
  data = request.get_json(silent=True) or {}
  student = (data.get("student") or "").strip()
  src_ip = (data.get("src_ip") or "").strip()
  decision = data.get("decision")

  if not student or not src_ip or decision not in ("allow", "deny"):
    return (
        jsonify({
            "success": False,
            "message": "student, src_ip, decision(allow|deny) 은 필수입니다.",
        }),
        400,
    )

  conn = get_db_connection()
  try:
    with conn.cursor() as cursor:
      cursor.execute(
          """
                INSERT INTO security_events
                    (student, src_ip, fail_count, decision, severity, reason, rule_id, generated_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """,
          (
              student[:50],
              src_ip[:45],
              int(data.get("fail_count") or 0),
              decision,
              data.get("severity", "Low"),
              data.get("reason"),
              data.get("rule"),
              data.get("generated_at"),
          ),
      )
      event_id = cursor.lastrowid

      # 허용·거부 모두 게시판에 '보안' 공지글로 남긴다 — 이벤트 저장과 한 트랜잭션
      post_id = _create_security_post(
          cursor,
          {
              "student": student,
              "src_ip": src_ip,
              "decision": decision,
              "severity": data.get("severity", "Low"),
              "reason": data.get("reason"),
              "fail_count": int(data.get("fail_count") or 0),
          },
      )

      conn.commit()

      return (
          jsonify({
              "success": True,
              "id": event_id,
              "student": student,
              "src_ip": src_ip,
              "decision": decision,
              "post_id": post_id,
          }),
          201,
      )
  except Exception as e:
    conn.rollback()
    return jsonify({"success": False, "message": f"서버 오류: {str(e)}"}), 500
  finally:
    conn.close()


@security_bp.route("/events", methods=["GET"])
def list_security_events():
  """조회는 키 없이(수업 확인용). ?student= 로 본인 것만 고른다."""
  student = request.args.get("student")
  decision = request.args.get("decision")
  limit = min(request.args.get("limit", default=20, type=int), 100)

  where_clauses = ["1=1"]
  params = []
  if student:
    where_clauses.append("student = %s")
    params.append(student)
  if decision in ("allow", "deny"):
    where_clauses.append("decision = %s")
    params.append(decision)
  params.append(limit)

  conn = get_db_connection()
  try:
    with conn.cursor() as cursor:
      cursor.execute(
          f"""
                SELECT id, student, src_ip, fail_count, decision, severity,
                       reason, rule_id, generated_at, created_at
                FROM security_events
                WHERE {' AND '.join(where_clauses)}
                ORDER BY id DESC
                LIMIT %s
            """,
          params,
      )
      rows = cursor.fetchall()
      for r in rows:
        if r.get("created_at"):
          r["created_at"] = r["created_at"].strftime("%Y-%m-%d %H:%M:%S")
      return jsonify({"success": True, "count": len(rows), "events": rows})
  except Exception as e:
    return jsonify({"success": False, "message": str(e)}), 500
  finally:
    conn.close()


@security_bp.route("/events/summary", methods=["GET"])
def security_events_summary():
  """(심화 S1) 허용/거부 건수 + 거부 상위 IP 5개."""
  student = request.args.get("student")

  conn = get_db_connection()
  try:
    with conn.cursor() as cursor:
      if student:
        cursor.execute(
            "SELECT decision, COUNT(*) AS cnt FROM security_events"
            " WHERE student = %s GROUP BY decision",
            (student,),
        )
      else:
        cursor.execute(
            "SELECT decision, COUNT(*) AS cnt FROM security_events GROUP BY decision"
        )
      by_decision = {row["decision"]: row["cnt"] for row in cursor.fetchall()}

      if student:
        cursor.execute(
            """
                    SELECT src_ip, SUM(fail_count) AS fails
                    FROM security_events
                    WHERE decision = 'deny' AND student = %s
                    GROUP BY src_ip ORDER BY fails DESC LIMIT 5
                """,
            (student,),
        )
      else:
        cursor.execute(
            """
                    SELECT src_ip, SUM(fail_count) AS fails
                    FROM security_events
                    WHERE decision = 'deny'
                    GROUP BY src_ip ORDER BY fails DESC LIMIT 5
                """
        )
      top = cursor.fetchall()

      return jsonify({
          "success": True,
          "student": student,
          "by_decision": by_decision,
          "top_deny_ips": [
              {"src_ip": r["src_ip"], "fails": int(r["fails"])} for r in top
          ],
      })
  except Exception as e:
    return jsonify({"success": False, "message": str(e)}), 500
  finally:
    conn.close()


@security_bp.route("/students", methods=["GET"])
def list_students():
  """대시보드 드롭다운용 — 기록이 있는 학생 목록."""
  conn = get_db_connection()
  try:
    with conn.cursor() as cursor:
      cursor.execute(
          "SELECT DISTINCT student FROM security_events ORDER BY student"
      )
      rows = cursor.fetchall()
      return jsonify({"success": True, "students": [r["student"] for r in rows]})
  except Exception as e:
    return jsonify({"success": False, "message": str(e)}), 500
  finally:
    conn.close()
