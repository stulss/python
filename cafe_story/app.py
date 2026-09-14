import os
import sys

if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

from flask import Flask, jsonify, render_template, request

from flask_cors import CORS
from config import Config
from db import init_db

# Blueprint 임포트
from routes.auth_routes import auth_bp
from routes.admin_routes import admin_bp
from routes.cafe_routes import cafe_bp
from routes.page_routes import page_bp

app = Flask(
    __name__,
    template_folder="templates",
    static_folder="static"
)
app.config.from_object(Config)

# CORS 설정
CORS(app, resources={r"/api/*": {"origins": "*"}})

# 블루프린트 등록
app.register_blueprint(auth_bp)
app.register_blueprint(admin_bp)
app.register_blueprint(cafe_bp)
app.register_blueprint(page_bp)


@app.errorhandler(404)
def not_found(e):
    if request.path.startswith("/api/"):
        return jsonify({"success": False, "message": "요청한 API 엔드포인트를 찾을 수 없습니다."}), 404
    return render_template("error_role.html", error_type="404", message="요청하신 페이지를 찾을 수 없습니다.", required_name="페이지", required_level=0, current_user=None), 404


@app.errorhandler(500)
def server_error(e):
    if request.path.startswith("/api/"):
        return jsonify({"success": False, "message": f"서버 내부 오류: {str(e)}"}), 500
    return render_template("error_role.html", error_type="500", message="서버 내부 오류가 발생했습니다.", required_name="오류", required_level=0, current_user=None), 500


if __name__ == "__main__":
    try:
        init_db()
    except Exception as e:
        print(f"[Warning] DB 초기화 경고: {e}")

    print(f"[SERVER] Cafe Story RBAC Server running at http://127.0.0.1:{Config.PORT}")
    app.run(host="0.0.0.0", port=Config.PORT, debug=Config.DEBUG)

