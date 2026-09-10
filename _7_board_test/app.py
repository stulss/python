import os
from config import Config
from db import init_db
from flask import Flask, jsonify, render_template
from flask_cors import CORS
from routes.auth_routes import auth_bp
from routes.post_routes import post_bp
from routes.openapi_routes import openapi_bp
from routes.security_routes import security_bp

# Flask 앱 생성 (templates와 static 폴더 명시)
app = Flask(
    __name__,
    template_folder="templates",
    static_folder="static",
)
app.config.from_object(Config)

# CORS 설정 (RESTful API 지원)
CORS(app, resources={r"/api/*": {"origins": "*"}})

# Blueprint 등록
app.register_blueprint(auth_bp)
app.register_blueprint(post_bp)
app.register_blueprint(openapi_bp)
app.register_blueprint(security_bp)


@app.route("/")
def index():
  """게시판 메인 웹 페이지 (Tailwind CSS 반응형 UI)"""
  return render_template("index.html")


@app.route("/dashboard")
def dashboard():
  """보안 대시보드 — n8n 이 저장한 허용/거부 기록을 보여준다."""
  return render_template("dashboard.html")


@app.errorhandler(404)
def not_found(e):
  return (
      jsonify(
          {"success": False, "message": "요청한 리소스를 찾을 수 없습니다."}
      ),
      404,
  )


@app.errorhandler(500)
def server_error(e):
  return (
      jsonify(
          {"success": False, "message": f"서버 내부 오류가 발생했습니다: {e}"}
      ),
      500,
  )


if __name__ == "__main__":
  # 애플리케이션 시작 시 DB 및 테이블 자동 생성
  try:
    init_db()
  except Exception as e:
    print(f"[Warning] DB 초기화 중 오류: {e}")

  print(f"🚀 Flask RESTful Board Server running at http://127.0.0.1:{Config.PORT}")
  app.run(host="0.0.0.0", port=Config.PORT, debug=Config.DEBUG)

