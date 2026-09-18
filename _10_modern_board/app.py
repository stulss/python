"""엔트리포인트 — 앱 팩토리(create_app) 패턴.

구조
  config.py       설정 (.env 로딩)
  extensions.py   db, jwt, cors 인스턴스
  models/         User, Post, Comment, SecurityEvent, SecurityLog, BlockedIP, Incident
  controllers/    page, auth, post, security, admin, gold, public, openapi (블루프린트)
  templates/      화면 (index.html)
  static/         CSS, JS 모듈

실행: python run.py 또는 python app.py -> http://localhost:5000
"""
import os
from flask import Flask, jsonify, request
from sqlalchemy import inspect, text

from config import Config
from controllers import all_blueprints
from extensions import db, jwt, cors
from models import BlockedIP


def _client_ip():
    """요청의 실제 클라이언트 IP 추출. 프록시 환경의 X-Forwarded-For 지원."""
    xff = request.headers.get('X-Forwarded-For', '')
    if xff:
        return xff.split(',')[0].strip()
    return request.remote_addr or ''


def _ensure_schema():
    """기존 DB 테이블에 필요한 신규 컬럼이 없으면 자동 추가 (가벼운 자동 마이그레이션).
    db.create_all()은 신규 테이블만 생성하고 기존 테이블의 ALTER는 수행하지 않으므로
    인스펙터를 통해 컬럼 유무를 검사한 후 안전하게 추가합니다.
    """
    try:
        insp = inspect(db.engine)
        with db.engine.begin() as conn:
            # 1. users 테이블 스키마 보강
            if insp.has_table('users'):
                user_cols = {c['name'] for c in insp.get_columns('users')}
                user_adds = {
                    'role': "ALTER TABLE users ADD COLUMN role VARCHAR(20) NOT NULL DEFAULT 'user'",
                    'role_granted_by': "ALTER TABLE users ADD COLUMN role_granted_by VARCHAR(80) NULL",
                    'role_granted_at': "ALTER TABLE users ADD COLUMN role_granted_at DATETIME NULL",
                    'role_reason': "ALTER TABLE users ADD COLUMN role_reason VARCHAR(200) NULL",
                    'nickname': "ALTER TABLE users ADD COLUMN nickname VARCHAR(50) NULL",
                    'is_locked': "ALTER TABLE users ADD COLUMN is_locked TINYINT(1) NOT NULL DEFAULT 0",
                    'locked_at': "ALTER TABLE users ADD COLUMN locked_at DATETIME NULL",
                    'lock_reason': "ALTER TABLE users ADD COLUMN lock_reason VARCHAR(200) NULL",
                    'failed_logins': "ALTER TABLE users ADD COLUMN failed_logins INT NOT NULL DEFAULT 0",
                }
                for name, ddl in user_adds.items():
                    if name not in user_cols:
                        try:
                            conn.execute(text(ddl))
                        except Exception as e:
                            print(f"[_ensure_schema] users 컬럼 '{name}' 추가 중 안내: {e}")

            # 2. security_events 테이블 스키마 보강 (_7_board_test 호환 필드)
            if insp.has_table('security_events'):
                sec_cols = {c['name'] for c in insp.get_columns('security_events')}
                sec_adds = {
                    'users': "ALTER TABLE security_events ADD COLUMN users VARCHAR(255) NULL",
                    'last_seen': "ALTER TABLE security_events ADD COLUMN last_seen VARCHAR(50) NULL",
                    'window_min': "ALTER TABLE security_events ADD COLUMN window_min INT NULL",
                    'source': "ALTER TABLE security_events ADD COLUMN source VARCHAR(50) DEFAULT 'login_guard' NULL",
                }
                for name, ddl in sec_adds.items():
                    if name not in sec_cols:
                        try:
                            conn.execute(text(ddl))
                        except Exception as e:
                            print(f"[_ensure_schema] security_events 컬럼 '{name}' 추가 중 안내: {e}")
    except Exception as e:
        print(f"[_ensure_schema Error] {e}")


def create_app(config_class=Config):
    app = Flask(__name__, template_folder='templates', static_folder='static')
    app.config.from_object(config_class)

    # 확장 기능 초기화
    db.init_app(app)
    jwt.init_app(app)
    cors.init_app(app, resources={r"/api/*": {"origins": "*"}})

    # 컨트롤러(블루프린트) 전체 일괄 등록
    for bp in all_blueprints:
        app.register_blueprint(bp)

    # 테이블 생성 및 스키마 자동 동기화
    with app.app_context():
        db.create_all()
        _ensure_schema()

    @app.before_request
    def _block_ip_guard():
        """실차단(Active Response): 차단된 IP 의 요청은 403 Forbidden 차단.
        관리자 API(/api/admin/*) 및 정적 자산(/static/*)은 안전장치로 예외 처리.
        """
        if request.path.startswith('/api/admin') or request.path.startswith('/static'):
            return None
        ip = _client_ip()
        if ip and db.session.get(BlockedIP, ip):
            return jsonify({
                'msg': '차단된 IP 입니다 (관리자에게 문의하세요).',
                'error': '차단된 IP 입니다 (관리자에게 문의하세요).',
                'ip': ip,
                'blocked': True
            }), 403
        return None

    # JWT 에러 핸들러
    @jwt.expired_token_loader
    def expired_token_callback(jwt_header, jwt_payload):
        return jsonify({
            'error': '인증 토큰이 만료되었습니다. 다시 로그인해주세요.',
            'msg': '인증 토큰이 만료되었습니다.',
            'code': 'TOKEN_EXPIRED'
        }), 401

    @jwt.invalid_token_loader
    def invalid_token_callback(error):
        return jsonify({
            'error': '유효하지 않은 토큰입니다.',
            'msg': '유효하지 않은 토큰입니다.',
            'code': 'INVALID_TOKEN'
        }), 401

    @jwt.unauthorized_loader
    def missing_token_callback(error):
        return jsonify({
            'error': '인증 헤더(Bearer Token)가 누락되었습니다.',
            'msg': '인증 헤더가 누락되었습니다.',
            'code': 'AUTHORIZATION_REQUIRED'
        }), 401

    # 일반 오류 처리
    @app.errorhandler(404)
    def not_found_error(error):
        return jsonify({'error': '요청한 리소스를 찾을 수 없습니다.', 'msg': 'Not Found'}), 404

    @app.errorhandler(500)
    def internal_error(error):
        db.session.rollback()
        return jsonify({'error': '서버 내부 오류가 발생했습니다.', 'msg': 'Internal Server Error'}), 500

    return app


app = create_app()

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
