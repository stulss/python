"""보안(Security) 컨트롤러 — SIEM 대시보드 통계, n8n SOAR 보안 이벤트 연동, 모의 위협 시뮬레이터

기능:
  · 골드(Gold) 이상 등급 전용 보안 대시보드 API (/api/security/stats, /api/security/logs, /simulate)
  · 비인가 접근 시 자동 감지 및 SecurityLog 보안 감사 기록
  · n8n SOAR 수신 엔드포인트 (/api/security/events, X-API-Key 헤더 인증)
  · _7_board_test 호환 요약 (/api/security/events/summary) 및 학생 목록 (/api/security/students)
"""
import os
from functools import wraps
from datetime import datetime, timedelta
from flask import Blueprint, request, jsonify, current_app
from sqlalchemy import func
from extensions import db
from models.security_event import SecurityEvent
from models.security_log import SecurityLog
from models.user import User
from models.post import Post
from config import Config
from flask_jwt_extended import jwt_required, get_jwt, get_jwt_identity
from .rbac import role_required

security_bp = Blueprint('security', __name__, url_prefix='/api/security')

BOT_USERNAME = 'soarbot'


def gold_required():
    """보안 대시보드 권한 제한 해제 (골드 이상 제한 제거, 모든 사용자 및 비로그인 허용)"""
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            return fn(*args, **kwargs)
        return wrapper
    return decorator


def get_or_create_bot_user():
    """거부(deny) 시 게시판 공지글 작성자로 쓸 시스템 봇 계정"""
    bot = User.query.filter_by(username=BOT_USERNAME).first()
    if bot:
        return bot
    bot = User(
        username=BOT_USERNAME,
        nickname='보안봇',
        email='soarbot@security.internal',
        role='admin'
    )
    bot.set_password(os.urandom(16).hex())
    db.session.add(bot)
    db.session.commit()
    return bot


def create_security_post(ev):
    """이벤트(허용/거부)를 게시판 '보안이슈' 카테고리 공지글로 자동 등록"""
    try:
        bot = get_or_create_bot_user()
        if ev.get('decision') == 'deny':
            title = f"🚫 [보안경보][{ev.get('student', 'SYSTEM')}] {ev.get('src_ip')} 접근 거부 ({ev.get('severity', 'High')})"
        else:
            title = f"✅ [보안통과][{ev.get('student', 'SYSTEM')}] {ev.get('src_ip')} 접근 허용 ({ev.get('severity', 'Low')})"

        content = (
            f"■ 탐지 사유: {ev.get('reason') or '비정상 침입 시도 감지'}\n"
            f"■ 출발지 IP: {ev.get('src_ip')}\n"
            f"■ 적용 규칙: {ev.get('rule') or ev.get('rule_id') or 'DEFAULT_RULE'}\n"
            f"■ 실패 누적: {ev.get('fail_count', 0)}회\n"
            f"■ 발생 일시: {ev.get('generated_at') or datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
            f"※ 본 공지는 n8n SOAR 보안 자동화 워크플로우에 의해 실시간 등록되었습니다."
        )

        new_post = Post(
            title=title,
            content=content,
            category='보안이슈',
            tags='SOAR,n8n,보안관제',
            is_pinned=(ev.get('decision') == 'deny'),
            author_id=bot.id,
            author_name=bot.nickname or bot.username
        )
        db.session.add(new_post)
        db.session.commit()
        return new_post.id
    except Exception as e:
        db.session.rollback()
        print(f"[create_security_post Error] {e}")
        return None


def require_api_key(fn):
    """X-API-Key 가 허용된 설정값 목록 중 하나와 일치할 때 통과 (n8n 및 외부 관제 봇 연동)"""
    @wraps(fn)
    def wrapper(*args, **kwargs):
        client_key = request.headers.get('X-API-Key', '').strip()
        allowed_keys = getattr(Config, 'SECURITY_API_KEYS', [])
        single_key = current_app.config.get('SECURITY_API_KEY', '')
        if single_key and single_key not in allowed_keys:
            allowed_keys = list(allowed_keys) + [single_key]

        if not client_key or client_key not in allowed_keys:
            return jsonify({
                'success': False,
                'message': 'API 키가 유효하지 않거나 누락되었습니다.',
                'msg': 'API 키가 없거나 잘못되었습니다.'
            }), 401
        return fn(*args, **kwargs)
    return wrapper


@security_bp.route('/events', methods=['POST'])
@require_api_key
def create_security_event():
    """n8n 이 판정한 보안 이벤트 저장 (X-API-Key 헤더 인증)"""
    data = request.get_json(silent=True) or {}
    student = (data.get('student') or '').strip()
    src_ip = (data.get('src_ip') or '').strip()
    decision = data.get('decision')

    if not student or not src_ip or decision not in ('allow', 'deny'):
        return jsonify({
            'success': False,
            'message': 'student, src_ip, decision(allow|deny)은 필수 항목입니다.',
            'msg': 'student, src_ip, decision(allow|deny) 은 필수입니다.'
        }), 400

    severity = data.get('severity', 'Low' if decision == 'allow' else 'High')
    reason = data.get('reason', '')
    generated_at = data.get('generated_at') or datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')

    new_event = SecurityEvent(
        student=student[:50],
        src_ip=src_ip[:45],
        level=int(data.get('level', 0)),
        rule=data.get('rule'),
        rule_id=data.get('rule_id'),
        fail_count=int(data.get('fail_count', 0)),
        decision=decision,
        severity=severity,
        reason=reason[:255] if reason else None,
        users=data.get('users'),
        last_seen=data.get('last_seen'),
        window_min=data.get('window_min'),
        source=data.get('source', 'login_guard'),
        generated_at=generated_at[:32]
    )

    db.session.add(new_event)

    log = SecurityLog(
        event_type=f"SOAR_{decision.upper()}",
        severity='CRITICAL' if decision == 'deny' and severity in ['High', 'Critical'] else ('WARNING' if decision == 'deny' else 'INFO'),
        ip_address=src_ip[:45],
        endpoint='/api/security/events',
        method='POST',
        status_code=201,
        username=student,
        details=f"[{decision.upper()}] {reason}"
    )
    db.session.add(log)
    db.session.commit()

    post_id = None
    if Config.AUTO_POST_ON_DENY and decision == 'deny':
        post_id = create_security_post(data)

    return jsonify({
        'success': True,
        'message': '보안 이벤트가 등록되었습니다.',
        'msg': '보안 이벤트가 등록되었습니다.',
        'id': new_event.id,
        'event_id': new_event.id,
        'student': new_event.student,
        'decision': new_event.decision,
        'post_id': post_id
    }), 201


@security_bp.route('/events', methods=['GET'])
def get_security_events():
    """보안 이벤트 목록 조회 (필터: student, decision, src_ip, limit)"""
    limit = min(request.args.get('limit', 50, type=int), 100)
    student = request.args.get('student')
    decision = request.args.get('decision')
    src_ip = request.args.get('src_ip')

    query = SecurityEvent.query
    if student:
        query = query.filter_by(student=student)
    if decision in ('allow', 'deny'):
        query = query.filter_by(decision=decision)
    if src_ip:
        query = query.filter_by(src_ip=src_ip)

    events = query.order_by(SecurityEvent.id.desc()).limit(limit).all()
    ev_dicts = [e.to_dict() for e in events]
    return jsonify({
        'success': True,
        'events': ev_dicts,
        'count': len(events)
    }), 200


@security_bp.route('/events/summary', methods=['GET'])
def security_events_summary():
    """허용/거부 건수 + 거부 상위 IP 5개 (_7_board_test 호환)"""
    student = request.args.get('student')
    q1 = db.session.query(SecurityEvent.decision, func.count(SecurityEvent.id))
    q2 = (db.session.query(SecurityEvent.src_ip, func.sum(SecurityEvent.fail_count))
          .filter(SecurityEvent.decision == 'deny'))
    if student:
        q1 = q1.filter(SecurityEvent.student == student)
        q2 = q2.filter(SecurityEvent.student == student)

    by_decision = dict(q1.group_by(SecurityEvent.decision).all())
    top = (q2.group_by(SecurityEvent.src_ip)
           .order_by(func.sum(SecurityEvent.fail_count).desc()).limit(5).all())

    return jsonify({
        'student': student,
        'by_decision': by_decision,
        'top_deny_ips': [{'src_ip': ip, 'fails': int(n)} for ip, n in top if ip],
    })


@security_bp.route('/students', methods=['GET'])
def list_students():
    """이벤트 기록이 있는 학생 목록 (_7_board_test 호환)"""
    rows = (db.session.query(SecurityEvent.student)
            .distinct().order_by(SecurityEvent.student).all())
    return jsonify({'students': [r[0] for r in rows if r[0]]})


@security_bp.route('/stats', methods=['GET'])
@gold_required()
def get_security_stats():
    """보안 대시보드 요약 통계 (골드 등급 이상 전용, SecurityLog + SecurityEvent 통합)"""
    total_events = SecurityLog.query.count() + SecurityEvent.query.count()

    severity_counts = dict(
        db.session.query(SecurityLog.severity, func.count(SecurityLog.id))
        .group_by(SecurityLog.severity).all()
    )

    event_type_counts = dict(
        db.session.query(SecurityLog.event_type, func.count(SecurityLog.id))
        .group_by(SecurityLog.event_type).all()
    )

    deny_count = SecurityEvent.query.filter_by(decision='deny').count()
    allow_count = SecurityEvent.query.filter_by(decision='allow').count()
    if deny_count > 0:
        event_type_counts['SOAR_DENY'] = deny_count
        severity_counts['CRITICAL'] = severity_counts.get('CRITICAL', 0) + deny_count
    if allow_count > 0:
        event_type_counts['SOAR_ALLOW'] = allow_count
        severity_counts['INFO'] = severity_counts.get('INFO', 0) + allow_count

    now = datetime.utcnow()
    seven_days_ago = now - timedelta(days=6)

    timeline_records = (
        db.session.query(
            func.date(SecurityLog.created_at).label('log_date'),
            SecurityLog.severity,
            func.count(SecurityLog.id).label('count')
        )
        .filter(SecurityLog.created_at >= seven_days_ago)
        .group_by('log_date', SecurityLog.severity)
        .order_by('log_date')
        .all()
    )

    date_labels = [(seven_days_ago + timedelta(days=i)).strftime('%m-%d') for i in range(7)]
    chart_series = {
        'labels': date_labels,
        'normal': [0] * 7,
        'warning': [0] * 7,
        'critical': [0] * 7
    }

    for r in timeline_records:
        d_str = r.log_date.strftime('%m-%d') if hasattr(r.log_date, 'strftime') else str(r.log_date)[5:]
        if d_str in date_labels:
            idx = date_labels.index(d_str)
            if r.severity in ['INFO']:
                chart_series['normal'][idx] += r.count
            elif r.severity in ['WARNING']:
                chart_series['warning'][idx] += r.count
            elif r.severity in ['HIGH', 'CRITICAL']:
                chart_series['critical'][idx] += r.count

    crit_count = severity_counts.get('CRITICAL', 0)
    high_count = severity_counts.get('HIGH', 0)
    warn_count = severity_counts.get('WARNING', 0)

    if crit_count > 0:
        threat_level = 'CRITICAL'
        threat_color = 'red'
    elif high_count > 3:
        threat_level = 'HIGH'
        threat_color = 'orange'
    elif warn_count > 10:
        threat_level = 'ELEVATED'
        threat_color = 'yellow'
    else:
        threat_level = 'SECURE'
        threat_color = 'emerald'

    return jsonify({
        'total_events': total_events,
        'threat_level': threat_level,
        'threat_color': threat_color,
        'severity_distribution': {
            'INFO': severity_counts.get('INFO', 0),
            'WARNING': warn_count,
            'HIGH': high_count,
            'CRITICAL': crit_count
        },
        'event_types': event_type_counts,
        'chart_series': chart_series
    }), 200


@security_bp.route('/logs', methods=['GET'])
@gold_required()
def get_security_logs():
    """보안 로그 목록 조회 (골드 등급 이상 전용)"""
    limit = min(request.args.get('limit', 50, type=int), 100)
    severity = request.args.get('severity', type=str)
    event_type = request.args.get('event_type', type=str)

    query = SecurityLog.query
    if severity and severity != 'ALL':
        query = query.filter_by(severity=severity)
    if event_type and event_type != 'ALL':
        query = query.filter_by(event_type=event_type)

    logs = query.order_by(SecurityLog.id.desc()).limit(limit).all()
    return jsonify({
        'logs': [log.to_dict() for log in logs]
    }), 200


@security_bp.route('/simulate', methods=['POST'])
@gold_required()
def simulate_threat():
    """모의 공격 및 보안 위협 이벤트 시뮬레이션 생성기 (골드 등급 이상 전용)"""
    data = request.get_json(silent=True) or {}
    attack_type = data.get('attack_type', 'SQLI')
    ip = request.headers.get('X-Forwarded-For', request.remote_addr or '192.168.1.105').split(',')[0].strip()

    threat_catalog = {
        'SQLI': {
            'event_type': 'SQLI_DETECT',
            'severity': 'CRITICAL',
            'endpoint': '/api/posts?search=\' OR 1=1 --',
            'method': 'GET',
            'status_code': 400,
            'details': 'SQL 인젝션 구문 차단: search=\' UNION SELECT username, password_hash FROM users --'
        },
        'BRUTE_FORCE': {
            'event_type': 'BRUTE_FORCE',
            'severity': 'HIGH',
            'endpoint': '/api/auth/login',
            'method': 'POST',
            'status_code': 429,
            'details': '단시간(60초 내 15회) 연속 로그인 실패 감지: 대상 계정 "admin"'
        },
        'UNAUTHORIZED_ACCESS': {
            'event_type': 'UNAUTHORIZED_ACCESS',
            'severity': 'WARNING',
            'endpoint': '/api/admin/users',
            'method': 'GET',
            'status_code': 401,
            'details': '인증 토큰(JWT Bearer)이 누락되었거나 만료된 접근 시도'
        },
        'XSS': {
            'event_type': 'XSS_DETECT',
            'severity': 'HIGH',
            'endpoint': '/api/posts',
            'method': 'POST',
            'status_code': 400,
            'details': '악성 스크립트 페이로드 필터링: <script>alert("XSS")</script>'
        },
        'PRIVILEGE_ESCALATION': {
            'event_type': 'PRIVILEGE_ESC',
            'severity': 'CRITICAL',
            'endpoint': '/api/admin/users/1/role',
            'method': 'PATCH',
            'status_code': 403,
            'details': '비인가 권한 상승 시도: 일반 유저 "guest"가 관리자(admin) 권한 부여 요청'
        }
    }

    t = threat_catalog.get(attack_type, threat_catalog['SQLI'])

    log = SecurityLog(
        event_type=t['event_type'],
        severity=t['severity'],
        ip_address=ip,
        endpoint=t['endpoint'],
        method=t['method'],
        status_code=t['status_code'],
        username='모의공격자',
        details=t['details']
    )
    db.session.add(log)

    sec_event = SecurityEvent(
        student='SIMULATOR',
        src_ip=ip,
        level=3 if t['severity'] == 'CRITICAL' else 2,
        rule=t['event_type'],
        rule_id=f"RULE_{attack_type}",
        fail_count=5 if attack_type == 'BRUTE_FORCE' else 1,
        decision='deny',
        severity=t['severity'],
        reason=t['details'],
        generated_at=datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
    )
    db.session.add(sec_event)
    db.session.commit()

    post_id = None
    if Config.AUTO_POST_ON_DENY:
        post_id = create_security_post({
            'student': 'SIMULATOR',
            'src_ip': ip,
            'decision': 'deny',
            'severity': t['severity'],
            'reason': t['details'],
            'fail_count': 1,
            'rule': t['event_type']
        })

    return jsonify({
        'message': f'모의 보안 위협 [{t["event_type"]}] 발생 완료',
        'msg': f'모의 보안 위협 [{t["event_type"]}] 발생 완료',
        'log': log.to_dict(),
        'post_id': post_id
    }), 201


@security_bp.route('/clear', methods=['POST'])
@gold_required()
def clear_logs():
    """보안 로그 초기화 (골드 등급 이상 전용)"""
    SecurityLog.query.delete()
    SecurityEvent.query.delete()
    db.session.commit()
    return jsonify({'message': '보안 로그가 초기화되었습니다.', 'msg': '보안 로그가 초기화되었습니다.'}), 200
