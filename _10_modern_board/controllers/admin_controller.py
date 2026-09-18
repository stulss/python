"""관리자(Admin/RBAC) 컨트롤러 — 회원 관리, 권한 부여/회수, 계정 잠금, IP 차단, 인시던트 관리

인증 방식:
  ① 기계 호출(n8n, 회수봇): X-API-Key 헤더
  ② 관리자 화면: JWT 토큰 (role == 'admin')
"""
from datetime import datetime
from functools import wraps
from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity, get_jwt

from extensions import db
from models.user import User, VALID_ROLES, ROLE_LABEL, ROLE_LEVEL
from models.post import Post, Comment
from models.security_log import SecurityLog
from models.security_event import SecurityEvent
from models.blocked_ip import BlockedIP
from models.incident import Incident
from .rbac import current_user

admin_bp = Blueprint('admin', __name__, url_prefix='/api/admin')


def _has_valid_key():
    client_key = request.headers.get('X-API-Key', '').strip()
    if not client_key:
        return False
    allowed_keys = list(current_app.config.get('ADMIN_API_KEYS', []))
    single_key = current_app.config.get('ADMIN_API_KEY', '')
    if single_key and single_key not in allowed_keys:
        allowed_keys.append(single_key)
    return client_key in allowed_keys


def _current_admin_user():
    user = current_user()
    return user if (user and user.is_admin) else None


def admin_required(fn=None):
    """관리자 권한 데코레이터: X-API-Key 또는 admin JWT 토큰 허용"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            if _has_valid_key():
                request.actor = 'apikey'
                return func(*args, **kwargs)
            admin = _current_admin_user()
            if admin:
                request.actor = admin.username
                return func(*args, **kwargs)

            # 비인가 접근 시 감사 로그
            ip = request.headers.get('X-Forwarded-For', request.remote_addr or '127.0.0.1').split(',')[0].strip()
            user = current_user()
            uname = user.username if user else 'anonymous'
            uid = user.id if user else None
            try:
                log = SecurityLog(
                    event_type='UNAUTHORIZED_ADMIN_ACCESS',
                    severity='HIGH',
                    ip_address=ip,
                    endpoint=request.path,
                    method=request.method,
                    status_code=403,
                    user_id=uid,
                    username=uname,
                    details=f'Unauthorized admin access attempt by {uname}'
                )
                db.session.add(log)
                db.session.commit()
            except Exception:
                db.session.rollback()

            return jsonify({
                'error': '관리자 인가가 필요합니다(X-API-Key 또는 admin 로그인).',
                'msg': '관리자 인가가 필요합니다(X-API-Key 또는 admin 로그인).'
            }), 403
        return wrapper

    if fn is not None:
        return decorator(fn)
    return decorator


def _allowlist(param=None):
    if param:
        return [u.strip() for u in param.split(',') if u.strip()]
    return current_app.config.get('ADMIN_ALLOWLIST', ['admin', 'soarbot'])


@admin_bp.route('/stats', methods=['GET'])
@admin_required
def get_stats():
    """관리자 대시보드 통계"""
    total_users = User.query.count()
    active_users = User.query.filter_by(is_active=True).count()
    admin_users = User.query.filter_by(role='admin').count()
    gold_users = User.query.filter_by(role='gold').count()
    locked_users = User.query.filter_by(is_locked=True).count()
    blocked_ips = BlockedIP.query.count()

    total_posts = Post.query.count()
    total_comments = Comment.query.count()
    pinned_posts = Post.query.filter_by(is_pinned=True).count()

    return jsonify({
        'users': {
            'total': total_users,
            'active': active_users,
            'admins': admin_users,
            'gold': gold_users,
            'locked': locked_users
        },
        'posts': {
            'total': total_posts,
            'pinned': pinned_posts
        },
        'comments': {
            'total': total_comments
        },
        'security': {
            'blocked_ips': blocked_ips
        },
        'system': {
            'status': 'HEALTHY',
            'db_engine': 'MySQL 8.0',
            'api_version': '2.0.0-RBAC'
        }
    }), 200


@admin_bp.route('/users', methods=['GET'])
@admin_required
def get_users():
    """회원 목록 조회 (?role= 로 필터 가능)"""
    role = request.args.get('role')
    q = User.query
    if role in VALID_ROLES:
        q = q.filter_by(role=role)
    users = q.order_by(User.id.desc()).all()
    user_dicts = [u.to_dict() for u in users]
    return jsonify({
        'count': len(users),
        'users': user_dicts
    }), 200


@admin_bp.route('/users/<int:user_id>/role', methods=['PATCH', 'PUT'])
@admin_required
def update_user_role(user_id):
    """회원 역할 변경 (user <-> gold <-> admin)"""
    user = User.query.get(user_id)
    if not user:
        return jsonify({'error': '사용자를 찾을 수 없습니다.', 'msg': '사용자를 찾을 수 없습니다.'}), 404

    data = request.get_json(silent=True) or {}
    new_role = data.get('role')
    if new_role not in VALID_ROLES:
        return jsonify({'error': f'유효하지 않은 역할입니다. ({", ".join(VALID_ROLES)} 중 선택)', 'msg': '유효하지 않은 역할입니다.'}), 400

    actor = getattr(request, 'actor', 'admin')
    user.role = new_role
    user.role_granted_by = actor
    user.role_granted_at = datetime.utcnow()
    user.role_reason = data.get('reason', f'관리자 {actor}에 의한 역할 변경')
    db.session.commit()

    return jsonify({
        'message': f'{user.username}의 권한이 {new_role}로 변경되었습니다.',
        'msg': f'{user.username}의 권한이 {new_role}로 변경되었습니다.',
        'user': user.to_dict()
    }), 200


@admin_bp.route('/users/<int:user_id>/status', methods=['PATCH', 'PUT'])
@admin_bp.route('/users/<int:user_id>/toggle-active', methods=['PATCH', 'PUT', 'POST'])
@admin_required
def toggle_user_status(user_id):
    """회원 활성화/정지 전환"""
    user = User.query.get(user_id)
    if not user:
        return jsonify({'error': '사용자를 찾을 수 없습니다.', 'msg': '사용자를 찾을 수 없습니다.'}), 404

    actor = getattr(request, 'actor', 'admin')
    if user.username == actor or (isinstance(actor, int) and user.id == actor):
        return jsonify({'error': '자기 자신의 계정은 비활성화할 수 없습니다.', 'msg': '자기 자신의 계정은 비활성화할 수 없습니다.'}), 400

    user.is_active = not user.is_active
    db.session.commit()

    status_str = '활성화' if user.is_active else '정지'
    return jsonify({
        'message': f'{user.username} 계정이 {status_str}되었습니다.',
        'msg': f'{user.username} 계정이 {status_str}되었습니다.',
        'user': user.to_dict()
    }), 200


@admin_bp.route('/users/<int:user_id>', methods=['DELETE'])
@admin_required
def delete_user(user_id):
    """회원 강제 탈퇴/삭제"""
    user = User.query.get(user_id)
    if not user:
        return jsonify({'error': '사용자를 찾을 수 없습니다.', 'msg': '사용자를 찾을 수 없습니다.'}), 404

    actor = getattr(request, 'actor', 'admin')
    if user.username == actor:
        return jsonify({'error': '자기 자신은 삭제할 수 없습니다.', 'msg': '자기 자신은 삭제할 수 없습니다.'}), 400

    db.session.delete(user)
    db.session.commit()

    return jsonify({
        'message': f'{user.username} 계정이 삭제되었습니다.',
        'msg': f'{user.username} 계정이 삭제되었습니다.'
    }), 200


@admin_bp.route('/posts', methods=['GET'])
@admin_required
def get_all_posts():
    """관리자용 전체 게시글 조회"""
    posts = Post.query.order_by(Post.id.desc()).all()
    return jsonify({
        'count': len(posts),
        'posts': [p.to_dict(include_content=False) for p in posts]
    }), 200


@admin_bp.route('/posts/<int:post_id>', methods=['DELETE'])
@admin_required
def delete_post_admin(post_id):
    """관리자 게시글 강제 삭제"""
    post = Post.query.get(post_id)
    if not post:
        return jsonify({'error': '게시글을 찾을 수 없습니다.', 'msg': '게시글을 찾을 수 없습니다.'}), 404

    db.session.delete(post)
    db.session.commit()
    return jsonify({'message': '게시글이 관리자에 의해 강제 삭제되었습니다.', 'msg': '게시글이 삭제되었습니다.'}), 200


# ── _7_board_test 호환 RBAC & 보안 관리 엔드포인트 ──

@admin_bp.route('/violations', methods=['GET'])
@admin_required
def list_violations():
    """정책 위반(허용목록 밖 admin) 조회"""
    allow = _allowlist(request.args.get('allowlist'))
    admins = User.query.filter_by(role='admin').all()
    bad = [u for u in admins if u.username not in allow]
    return jsonify({
        'allowlist': allow,
        'count': len(bad),
        'violations': [u.to_dict() for u in bad],
    }), 200


@admin_bp.route('/grant', methods=['POST'])
@admin_required
def grant_role():
    """역할 부여: {username, role, reason}"""
    data = request.get_json(silent=True) or {}
    username = (data.get('username') or '').strip()
    role = (data.get('role') or '').strip()
    if not username or role not in VALID_ROLES:
        return jsonify({'msg': f'username, role({", ".join(VALID_ROLES)}) 은 필수입니다.'}), 400

    user = User.query.filter_by(username=username).first()
    if not user:
        return jsonify({'msg': f"사용자 '{username}' 을 찾을 수 없습니다."}), 404

    actor = getattr(request, 'actor', 'admin')
    user.role = role
    user.role_granted_by = actor
    user.role_granted_at = datetime.utcnow()
    user.role_reason = data.get('reason', '')
    db.session.commit()

    return jsonify({
        'msg': f"'{username}' 에게 '{ROLE_LABEL.get(role, role)}' 역할 부여 완료.",
        'user': user.to_dict(),
    }), 200


@admin_bp.route('/revoke', methods=['POST'])
@admin_required
def revoke_role():
    """과잉권한 회수(최소권한 복원) → role 을 'user' 로 강등. n8n 워크플로우가 호출.
    body: {username, reason, student, severity, src_ip, source}
    n8n '메세지 회수' 노드 규격에 맞춰 old_role, new_role, event_id 반환
    """
    data = request.get_json(silent=True) or {}
    username = (data.get('username') or '').strip()
    if not username:
        return jsonify({'msg': 'username 은 필수입니다.'}), 400

    user = User.query.filter_by(username=username).first()
    if not user:
        return jsonify({'msg': f"사용자 '{username}' 을 찾을 수 없습니다."}), 404

    old = user.role
    actor = getattr(request, 'actor', 'privilege-guard')

    if old == 'user':
        return jsonify({
            'msg': '이미 user 권한(회수 불필요)',
            'username': username,
            'old_role': old,
            'new_role': 'user',
            'revoked': False,
            'user': user.to_dict()
        }), 200

    user.role = 'user'
    user.role_granted_by = f'{actor} (회수)'
    user.role_granted_at = datetime.utcnow()
    user.role_reason = (data.get('reason') or f'{old}→user 회수 by {actor}')[:200]

    # 보안 감사 이벤트 기록
    ev = SecurityEvent(
        student=(data.get('student') or 'SYSTEM')[:50],
        src_ip=data.get('src_ip') or request.remote_addr or '127.0.0.1',
        fail_count=0,
        decision='deny',
        severity=data.get('severity', 'High'),
        reason=(data.get('reason') or f"과잉권한 자동 회수: '{username}' ({old} → user)")[:200],
        users=username,
        source=data.get('source', 'privilege-guard'),
        generated_at=data.get('generated_at') or datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
    )
    db.session.add(ev)
    db.session.commit()

    return jsonify({
        'msg': f"'{username}' 의 '{ROLE_LABEL.get(old, old)}' 권한을 회수했습니다.",
        'username': username,
        'old_role': old,
        'new_role': 'user',
        'revoked': True,
        'event_id': ev.id,
        'revoked_by': actor,
        'user': user.to_dict(),
        'student': (data.get('student') or 'SYSTEM'),
        'src_ip': data.get('src_ip') or request.remote_addr or '127.0.0.1',
        'level': 10,
        'rule': data.get('rule') or 'UNAUTHORIZED_ADMIN',
        'fail_count': 0,
        'decision': 'deny',
        'severity': data.get('severity', 'High'),
        'reason': (data.get('reason') or f"과잉권한 자동 회수: '{username}' ({old} → user)")[:200],
    }), 200


@admin_bp.route('/lock', methods=['POST'])
@admin_required
def lock_user():
    """계정 잠금 (브루트포스 차단)"""
    data = request.get_json(silent=True) or {}
    username = (data.get('username') or '').strip()
    if not username:
        return jsonify({'msg': 'username 은 필수입니다.'}), 400

    user = User.query.filter_by(username=username).first()
    if not user:
        return jsonify({'msg': f"사용자 '{username}' 을 찾을 수 없습니다."}), 404

    user.is_locked = True
    user.locked_at = datetime.utcnow()
    user.lock_reason = data.get('reason', '브루트포스 공격 감지로 인한 자동 잠금')
    db.session.commit()

    return jsonify({
        'msg': f"계정 '{username}' 이 잠겼습니다.",
        'user': user.to_dict()
    }), 200


@admin_bp.route('/unlock', methods=['POST'])
@admin_required
def unlock_user():
    """계정 잠금 해제"""
    data = request.get_json(silent=True) or {}
    username = (data.get('username') or '').strip()
    if not username:
        return jsonify({'msg': 'username 은 필수입니다.'}), 400

    user = User.query.filter_by(username=username).first()
    if not user:
        return jsonify({'msg': f"사용자 '{username}' 을 찾을 수 없습니다."}), 404

    user.is_locked = False
    user.locked_at = None
    user.lock_reason = None
    user.failed_logins = 0
    db.session.commit()

    return jsonify({
        'msg': f"계정 '{username}' 의 잠금이 해제되었습니다.",
        'user': user.to_dict()
    }), 200


# ── IP 차단 (실차단 / Active Response) ──

@admin_bp.route('/blocked-ips', methods=['GET'])
@admin_required
def list_blocked_ips():
    rows = BlockedIP.query.order_by(BlockedIP.blocked_at.desc()).all()
    return jsonify({'count': len(rows), 'blocked_ips': [r.to_dict() for r in rows]})


@admin_bp.route('/blocked-ips', methods=['POST'])
@admin_required
def block_ip():
    data = request.get_json(silent=True) or {}
    ip = (data.get('ip') or '').strip()
    if not ip:
        return jsonify({'msg': 'ip 는 필수입니다.'}), 400

    actor = getattr(request, 'actor', 'admin')
    row = db.session.get(BlockedIP, ip)
    if row:
        row.reason = data.get('reason', row.reason)
        row.blocked_by = actor
        row.blocked_at = datetime.utcnow()
    else:
        row = BlockedIP(
            ip=ip,
            reason=data.get('reason', '비정상 침입 시도 감지'),
            blocked_by=actor,
            blocked_at=datetime.utcnow()
        )
        db.session.add(row)
    db.session.commit()

    return jsonify({'msg': f"IP '{ip}' 가 차단되었습니다.", 'blocked_ip': row.to_dict()}), 201


@admin_bp.route('/blocked-ips/<string:ip>', methods=['DELETE'])
@admin_required
def unblock_ip(ip):
    row = db.session.get(BlockedIP, ip.strip())
    if not row:
        return jsonify({'msg': f"차단 목록에서 IP '{ip}' 를 찾을 수 없습니다."}), 404
    db.session.delete(row)
    db.session.commit()
    return jsonify({'msg': f"IP '{ip}' 차단이 해제되었습니다."}), 200


# ── 인시던트(Incident) 티켓 관리 ──

@admin_bp.route('/incidents', methods=['GET'])
@admin_required
def list_incidents():
    status = request.args.get('status')
    q = Incident.query
    if status in ('open', 'closed'):
        q = q.filter_by(status=status)
    rows = q.order_by(Incident.id.desc()).limit(100).all()
    return jsonify({'count': len(rows), 'incidents': [r.to_dict() for r in rows]})


@admin_bp.route('/incidents', methods=['POST'])
@admin_required
def create_or_update_incident():
    data = request.get_json(silent=True) or {}
    src_ip = (data.get('src_ip') or '').strip()
    title = (data.get('title') or '').strip() or f'보안 인시던트 ({src_ip})'

    inc = None
    if src_ip:
        inc = Incident.query.filter_by(src_ip=src_ip, status='open').order_by(Incident.id.desc()).first()

    if inc is None:
        inc = Incident(
            title=title,
            src_ip=src_ip or None,
            severity=data.get('severity', 'Medium'),
            summary=data.get('summary', ''),
            actions=data.get('actions', ''),
            student=data.get('student', 'SYSTEM'),
            event_count=int(data.get('event_count') or 1)
        )
        db.session.add(inc)
    else:
        inc.title = title
        inc.severity = data.get('severity', inc.severity)
        inc.summary = data.get('summary', inc.summary)
        inc.actions = data.get('actions', inc.actions)
        inc.event_count = (inc.event_count or 0) + int(data.get('event_count') or 1)
        inc.updated_at = datetime.utcnow()

    db.session.commit()
    return jsonify({'msg': '인시던트가 기록되었습니다.', 'incident': inc.to_dict()}), 201


@admin_bp.route('/incidents/<int:inc_id>/close', methods=['POST'])
@admin_required
def close_incident(inc_id):
    inc = Incident.query.get(inc_id)
    if not inc:
        return jsonify({'msg': '인시던트를 찾을 수 없습니다.'}), 404

    inc.status = 'closed'
    inc.closed_at = datetime.utcnow()
    db.session.commit()
    return jsonify({'msg': f'인시던트 #{inc_id} 가 종료되었습니다.', 'incident': inc.to_dict()}), 200
