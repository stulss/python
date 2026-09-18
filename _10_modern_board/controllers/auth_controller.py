"""인증(Authentication) 컨트롤러 — 회원가입 / 로그인 / 내 정보 조회

_7_board_test 와의 호환성:
  · 계정 잠금(is_locked) 체크 (브루트포스 차단 423 Locked)
  · 로그인 실패 횟수(failed_logins) 카운팅 및 성공 시 초기화
  · Graylog SIEM(GELF) UDP 로그 전송
  · role 및 role_label 반환
"""
from datetime import datetime
from flask import Blueprint, request, jsonify
from flask_jwt_extended import create_access_token, jwt_required, get_jwt_identity

from extensions import db
from models.user import User, ROLE_LABEL
from models.security_log import SecurityLog
from .gelf import send_gelf
from .rbac import current_user

auth_bp = Blueprint('auth', __name__, url_prefix='/api/auth')


def log_security(event_type, severity, details, user_id=None, username=None, status_code=200):
    """보안 감사 로그를 DB 에 기록하는 헬퍼 함수"""
    try:
        ip = request.headers.get('X-Forwarded-For', request.remote_addr or '127.0.0.1').split(',')[0].strip()
        log = SecurityLog(
            event_type=event_type,
            severity=severity,
            ip_address=ip,
            endpoint=request.path,
            method=request.method,
            status_code=status_code,
            user_id=user_id,
            username=username,
            details=details
        )
        db.session.add(log)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        print(f"[SecurityLog Error] {e}")


@auth_bp.route('/register', methods=['POST'])
def register():
    data = request.get_json(silent=True) or {}
    username = (data.get('username') or '').strip()
    password = (data.get('password') or '').strip()
    email = (data.get('email') or '').strip() or None
    nickname = (data.get('nickname') or '').strip() or username

    if not username or not password:
        return jsonify({'error': '아이디와 비밀번호를 모두 입력해주세요.', 'msg': 'username, password 는 필수입니다.'}), 400

    if len(username) < 3 or len(username) > 30:
        return jsonify({'error': '아이디는 3~30자 이내여야 합니다.', 'msg': '아이디는 3~30자 이내여야 합니다.'}), 400

    if len(password) < 4:
        return jsonify({'error': '비밀번호는 최소 4자 이상이어야 합니다.', 'msg': '비밀번호는 최소 4자 이상이어야 합니다.'}), 400

    if User.query.filter_by(username=username).first():
        return jsonify({'error': '이미 존재하는 아이디입니다.', 'msg': '이미 존재하는 사용자입니다.'}), 409

    if email and User.query.filter_by(email=email).first():
        return jsonify({'error': '이미 등록된 이메일입니다.', 'msg': '이미 등록된 이메일입니다.'}), 409

    new_user = User(
        username=username,
        nickname=nickname,
        email=email,
        role='user'
    )
    new_user.set_password(password)

    db.session.add(new_user)
    db.session.commit()

    log_security(
        event_type='USER_REGISTER',
        severity='INFO',
        details=f'New user registered: {username}',
        user_id=new_user.id,
        username=username,
        status_code=201
    )

    return jsonify({
        'message': '회원가입이 완료되었습니다.',
        'msg': '회원가입 성공',
        'user': new_user.to_dict()
    }), 201


@auth_bp.route('/login', methods=['POST'])
def login():
    data = request.get_json(silent=True) or {}
    username = (data.get('username') or '').strip()
    password = (data.get('password') or '').strip()

    if not username or not password:
        return jsonify({'error': '아이디와 비밀번호를 입력해주세요.', 'msg': '아이디와 비밀번호를 입력해주세요.'}), 400

    user = User.query.filter_by(username=username).first()
    src_ip = request.headers.get('X-Forwarded-For', request.remote_addr or '127.0.0.1').split(',')[0].strip()

    # ① 잠긴 계정(is_locked) 체크 (브루트포스 차단 - 423 Locked)
    if user and user.is_locked:
        send_gelf(f"login attempt on LOCKED account '{username}'",
                  rule='login-bruteforce', username=username, src_ip=src_ip, locked='1')
        log_security(
            event_type='LOGIN_LOCKED',
            severity='HIGH',
            details=f'Login attempt on locked account: {username}',
            user_id=user.id,
            username=username,
            status_code=423
        )
        return jsonify({
            'error': '계정이 잠겨 있습니다. 관리자에게 문의하세요.',
            'msg': '계정이 잠겨 있습니다. 관리자에게 문의하세요.',
            'locked': True
        }), 423

    # ② 계정 정지(is_active) 체크
    if user and not user.is_active:
        log_security(
            event_type='LOGIN_BLOCKED',
            severity='HIGH',
            details=f'Login attempt on suspended account: {username}',
            user_id=user.id,
            username=username,
            status_code=403
        )
        return jsonify({
            'error': '정지된 계정입니다. 관리자에게 문의하세요.',
            'msg': '정지된 계정입니다. 관리자에게 문의하세요.'
        }), 403

    # ③ 비밀번호 검증 실패
    if not user or not user.check_password(password):
        if user:
            user.failed_logins = (user.failed_logins or 0) + 1
            db.session.commit()
        send_gelf(f"failed login for '{username}' from {src_ip}",
                  rule='login-bruteforce', username=username or '(unknown)',
                  src_ip=src_ip, count=1)
        log_security(
            event_type='LOGIN_FAIL',
            severity='WARNING',
            details=f'Failed login attempt for username: {username}',
            username=username,
            status_code=401
        )
        return jsonify({
            'error': '아이디 또는 비밀번호가 일치하지 않습니다.',
            'msg': '아이디 또는 비밀번호가 잘못되었습니다.'
        }), 401

    # ④ 로그인 성공
    if user.failed_logins:
        user.failed_logins = 0
    user.last_login_at = datetime.utcnow()
    db.session.commit()

    additional_claims = {
        'username': user.username,
        'role': user.role
    }
    access_token = create_access_token(identity=str(user.id), additional_claims=additional_claims)

    log_security(
        event_type='LOGIN_SUCCESS',
        severity='INFO',
        details=f'User logged in: {username} (role: {user.role})',
        user_id=user.id,
        username=username,
        status_code=200
    )

    return jsonify({
        'message': '로그인 성공',
        'msg': '로그인 성공',
        'access_token': access_token,
        'token': access_token,
        'username': user.username,
        'role': user.role,
        'role_label': ROLE_LABEL.get(user.role, user.role),
        'user': user.to_dict()
    }), 200


@auth_bp.route('/me', methods=['GET'])
def me():
    """현재 로그인한 회원 정보 조회 및 역할/권한 확인"""
    user = current_user()
    if user is None:
        return jsonify({'error': '로그인이 필요합니다.', 'msg': '로그인이 필요합니다.'}), 401

    return jsonify({
        'id': user.id,
        'username': user.username,
        'nickname': user.nickname or user.username,
        'email': user.email,
        'role': user.role,
        'role_label': ROLE_LABEL.get(user.role, user.role),
        'is_gold': user.is_gold,
        'is_admin': user.is_admin,
        'user': user.to_dict()
    }), 200
