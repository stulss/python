"""관리자(인가/RBAC) REST — 회원 권한 부여·회수.

접근 방식 두 가지
  ① 기계 호출(n8n·회수봇)  : 헤더  X-API-Key: <ADMIN_API_KEY>
  ② 사람(관리자 페이지)     : JWT(로그인 토큰) + 그 계정의 role == 'admin'

시나리오
  - 관리자 페이지에서 특정 회원에게 admin 을 '부여'(인가) → 불필요한 과잉권한 발생
  - 파이썬 회수봇이 허용목록(ADMIN_ALLOWLIST) 밖 admin 을 탐지 → Graylog 신고
  - Graylog 이벤트 → n8n → 이 API 의 /revoke 를 호출해 실제 '회수'(최소권한 복원)
  - 회수 시 security_events 에 감사기록(source='privilege-guard') → 대시보드 노출
"""
from datetime import datetime, timedelta
from functools import wraps

from flask import Blueprint, current_app, jsonify, request

from extensions import db
from models import BlockedIP, Incident, Post, SecurityEvent, User

from .pagination import SortError, paginate
from .rbac import VALID_ROLES, current_user   # 등급 정의는 rbac 한 곳에서

admin_bp = Blueprint('admin', __name__, url_prefix='/api/admin')

# ('user', 'gold', 'admin') — models/user.py 의 ROLE_LEVEL 에서 온다.
ROLE_CHOICES = '|'.join(VALID_ROLES)


def _has_valid_key():
  """X-API-Key 가 ADMIN_API_KEY 와 일치하면 True(비어 있으면 항상 False = fail-closed)."""
  expected = current_app.config.get('ADMIN_API_KEY', '')
  return bool(expected) and request.headers.get('X-API-Key', '') == expected


def _current_admin_user():
  """JWT 가 있고 그 계정이 admin 이면 User, 아니면 None."""
  user = current_user()
  return user if (user and user.is_admin) else None


def admin_required(fn):
  """유효한 관리자 키(기계) 또는 admin JWT(사람)면 통과. 아니면 401/403."""
  @wraps(fn)
  def wrapper(*args, **kwargs):
    if _has_valid_key():
      request.actor = 'apikey'
      return fn(*args, **kwargs)
    admin = _current_admin_user()
    if admin:
      request.actor = admin.username
      request.actor_id = admin.id          # 자기 계정 차단 방지용
      return fn(*args, **kwargs)
    return jsonify({'msg': '관리자 인가가 필요합니다(X-API-Key 또는 admin 로그인).'}), 401
  return wrapper


# ── 목록·일괄 처리 공용 도구 (회원·차단 IP·인시던트가 같이 쓴다) ──────────────
_BULK_MAX = 500   # 한 번에 처리할 수 있는 항목 수 — 실수로 거대한 목록을 보내는 것 방지


def _parse_list(data, key, item_ok):
  """body[key] 가 1~_BULK_MAX 개짜리 목록이고 모든 항목이 item_ok 면 그 목록, 아니면 None."""
  items = data.get(key)
  if (isinstance(items, list) and 0 < len(items) <= _BULK_MAX
      and all(item_ok(i) for i in items)):
    return items
  return None


def _parse_ids(data):
  """body 의 ids 를 정수 목록으로. 형식이 틀리면 None(→ 라우트가 400).
  bool 은 int 의 하위형이라 True 가 1 로 통과하므로 따로 막는다."""
  return _parse_list(data, 'ids', lambda i: isinstance(i, int) and not isinstance(i, bool))


def _parse_ips(data):
  """body 의 ips 를 앞뒤 공백 없앤·중복 없는 문자열 목록으로. 형식이 틀리면 None."""
  items = _parse_list(data, 'ips', lambda i: isinstance(i, str) and i.strip())
  return None if items is None else list(dict.fromkeys(i.strip() for i in items))


def _bulk_ok(label, changed, **extra):
  """일괄 처리 응답 — 화면(bulkPost)이 count·changed·skipped… 를 같은 이름으로 읽는다."""
  return jsonify({'msg': f'{len(changed)}{label}', 'count': len(changed),
                  'changed': changed, 'actor': getattr(request, 'actor', 'unknown'),
                  **extra}), 200


def _list_or_page(query, key, all_order, sorts, id_column, default_sort):
  """목록 응답. page·per_page 가 **없으면 예전처럼 전체**(봇·스크립트 호환),
  있으면 공용 paginate 규약(page·per_page·sort·order + total…)."""
  if 'page' not in request.args and 'per_page' not in request.args:
    rows = query.order_by(all_order).all()
    return jsonify({'count': len(rows), key: [r.to_dict() for r in rows]})
  try:
    rows, meta = paginate(query, request.args, sorts, id_column, default_sort=default_sort)
  except SortError as e:
    return jsonify({'msg': str(e)}), 400
  return jsonify({'count': len(rows), key: [r.to_dict() for r in rows], **meta})


def _requester_ip():
  """지금 요청한 사람의 IP — app._client_ip 와 같은 규칙(XFF 첫 홉, 없으면 remote_addr).
  app 모듈을 import 하면 순환 참조라 규칙만 같게 둔다."""
  xff = request.headers.get('X-Forwarded-For', '')
  return xff.split(',')[0].strip() if xff else (request.remote_addr or '')


def _allowlist(param=None):
  """정책 허용목록. 쿼리/바디로 넘기면 우선, 없으면 config(.env)."""
  if param:
    return [u.strip() for u in param.split(',') if u.strip()]
  return current_app.config.get('ADMIN_ALLOWLIST', [])


# 회원 목록 정렬 허용 컬럼(화이트리스트) — 관리자 화면 표 머리글의 data-sort 와 같다.
_USER_SORTS = {
    'id': User.id,
    'username': User.username,
    'role': User.role,
    'is_locked': User.is_locked,
    'locked_at': User.locked_at,
    'failed_logins': User.failed_logins,
}


def _user_filters(q, src):
  """회원 목록·일괄 해제가 같이 쓰는 필터. src = request.args 또는 JSON body.
    q      : 아이디 부분 검색(%·_ 는 글자 그대로 — autoescape)
    role   : user|gold|admin
    locked : '1'|'0' (차단됨/정상)"""
  term = (src.get('q') or '').strip()
  if term:
    q = q.filter(User.username.contains(term, autoescape=True))
  if src.get('role') in VALID_ROLES:
    q = q.filter(User.role == src['role'])
  locked = str(src.get('locked', ''))
  if locked in ('1', '0'):
    q = q.filter(User.is_locked.is_(locked == '1'))
  return q


@admin_bp.route('/users', methods=['GET'])
@admin_required
def list_users():
  """회원 목록. 필터: ?q=(아이디 검색) &role= &locked=1|0

  페이징: ?page= &per_page= (공용 paginate 규약, sort=id|username|role|is_locked|
  locked_at|failed_logins). ★ page·per_page 를 **안 주면 예전처럼 전체** —
  privilege_revoke_bot.py 가 ?role=admin 으로 admin 전원을 읽기 때문이다
  (20건으로 잘리면 21번째 admin 부터 과잉권한 탐지에서 빠진다)."""
  return _list_or_page(_user_filters(User.query, request.args), 'users',
                       User.id.asc(), _USER_SORTS, User.id, 'id')


@admin_bp.route('/users/lock', methods=['POST'])
@admin_required
def lock_users_bulk():
  """회원 일괄 차단(계정 잠금). body: {ids: [..], reason?}

  '전원 차단(all)' 은 일부러 없다 — 사고 범위가 너무 크다. 고른 id 로만 잠근다.
  자기 계정은 건너뛴다(self_skipped) — 잠그는 순간 관리자 화면에서 쫓겨난다.
  감사기록: security_events 에 한 줄(source='admin-console') → 대시보드에 보인다."""
  data = request.get_json(silent=True) or {}
  ids = _parse_ids(data)
  if ids is None:
    return jsonify({'msg': f'ids(정수 목록, 1~{_BULK_MAX}개)가 필요합니다.'}), 400

  actor = getattr(request, 'actor', 'unknown')
  me = getattr(request, 'actor_id', None)
  wanted = set(ids)
  users = User.query.filter(User.id.in_(wanted)).all()
  not_found = sorted(wanted - {u.id for u in users})
  self_skipped = [u.id for u in users if u.id == me]
  skipped = sorted(u.id for u in users if u.is_locked and u.id != me)
  targets = [u for u in users if not u.is_locked and u.id != me]

  now = datetime.now()
  reason = (data.get('reason') or f'관리자 수동 차단 by {actor}')[:200]
  for u in targets:
    u.is_locked = True
    u.locked_at = now
    u.lock_reason = reason
  if targets:
    names = ', '.join(sorted(u.username for u in targets))
    db.session.add(SecurityEvent(
        student=actor[:50], src_ip='0.0.0.0', fail_count=0, decision='deny',
        severity='Medium', reason=f'관리자 계정 차단 {len(targets)}건: {reason}'[:200],
        users=names[:255], source='admin-console'))
  db.session.commit()
  return _bulk_ok('명 차단', sorted(u.id for u in targets), skipped=skipped,
                  not_found=not_found, self_skipped=self_skipped)


# 지우면 안 되는 시스템 계정 — soarbot 은 '보안' 자동 공지글의 작성자다.
_PROTECTED_USERS = ('soarbot',)


@admin_bp.route('/users/delete', methods=['POST'])
@admin_required
def delete_users_bulk():
  """회원 일괄 삭제. body: {ids: [..]}

  - 그 회원의 게시글도 함께 지운다. posts.author_id 는 NOT NULL 외래키라
    글을 남기면 MySQL 은 FK 오류, SQLite 는 작성자 없는 고아 글이 된다.
  - 본인(self_skipped)·시스템 계정(protected)은 건너뛴다.
  - '전원 삭제(all)' 는 일부러 없다 — 되돌릴 수 없다. 고른 id 로만 지운다.
  - 감사기록: security_events 에 한 줄(source='admin-console')."""
  data = request.get_json(silent=True) or {}
  ids = _parse_ids(data)
  if ids is None:
    return jsonify({'msg': f'ids(정수 목록, 1~{_BULK_MAX}개)가 필요합니다.'}), 400

  actor = getattr(request, 'actor', 'unknown')
  me = getattr(request, 'actor_id', None)
  wanted = set(ids)
  users = User.query.filter(User.id.in_(wanted)).all()
  not_found = sorted(wanted - {u.id for u in users})
  self_skipped = [u.id for u in users if u.id == me]
  protected = sorted(u.id for u in users if u.username in _PROTECTED_USERS and u.id != me)
  targets = [u for u in users if u.id != me and u.username not in _PROTECTED_USERS]
  target_ids = [u.id for u in targets]

  posts_deleted = 0
  if targets:
    names = ', '.join(sorted(u.username for u in targets))
    # 글을 먼저 지운다 — 회원이 먼저 사라지면 FK 가 걸린다.
    posts_deleted = (Post.query.filter(Post.author_id.in_(target_ids))
                     .delete(synchronize_session=False))
    User.query.filter(User.id.in_(target_ids)).delete(synchronize_session=False)
    db.session.add(SecurityEvent(
        student=actor[:50], src_ip='0.0.0.0', fail_count=0, decision='deny',
        severity='Medium',
        reason=f'관리자 회원 삭제 {len(targets)}명(게시글 {posts_deleted}개 포함)'[:200],
        users=names[:255], source='admin-console'))
  db.session.commit()
  return _bulk_ok('명 삭제', sorted(target_ids), posts_deleted=posts_deleted,
                  not_found=not_found, self_skipped=self_skipped, protected=protected)


@admin_bp.route('/users/unlock', methods=['POST'])
@admin_required
def unlock_users_bulk():
  """회원 일괄 차단 해제. 잠금 해제 + 로그인 실패 횟수 0 (단건 /unlock 과 같다).

  body: {ids: [..]}                         → 고른 회원만
        {all_locked: true, q?, role?}       → 조건에 맞는 차단 회원 전부(다른 페이지 포함)"""
  data = request.get_json(silent=True) or {}
  if data.get('all_locked') is True:
    targets = _user_filters(User.query, data).filter(User.is_locked.is_(True)).all()
    skipped, not_found = [], []
  else:
    ids = _parse_ids(data)
    if ids is None:
      return jsonify({'msg': f'ids(정수 목록, 1~{_BULK_MAX}개) 또는 '
                             'all_locked: true 가 필요합니다.'}), 400
    wanted = set(ids)
    users = User.query.filter(User.id.in_(wanted)).all()
    not_found = sorted(wanted - {u.id for u in users})
    skipped = sorted(u.id for u in users if not u.is_locked)
    targets = [u for u in users if u.is_locked]

  for u in targets:
    u.is_locked = False
    u.failed_logins = 0
    u.lock_reason = None
  db.session.commit()
  return _bulk_ok('명 차단 해제', sorted(u.id for u in targets),
                  skipped=skipped, not_found=not_found)


@admin_bp.route('/violations', methods=['GET'])
@admin_required
def list_violations():
  """정책 위반(허용목록 밖 admin) 목록. 회수봇이 참고용으로 쓸 수 있다.
  ?allowlist=lsy,instructor 로 기준을 넘기면 그걸 우선 적용."""
  allow = _allowlist(request.args.get('allowlist'))
  admins = User.query.filter_by(role='admin').all()
  bad = [u for u in admins if u.username not in allow]
  return jsonify({
      'allowlist': allow,
      'count': len(bad),
      'violations': [u.to_dict() for u in bad],
  })


@admin_bp.route('/grant', methods=['POST'])
@admin_required
def grant_role():
  """회원에게 역할 부여(인가). body: {username, role, reason}
  시나리오상 여기서 admin 을 잘못/과하게 부여해 '불필요한 권한'을 만든다."""
  data = request.get_json(silent=True) or {}
  username = (data.get('username') or '').strip()
  role = (data.get('role') or '').strip()
  if not username or role not in VALID_ROLES:
    return jsonify({'msg': f'username, role({ROLE_CHOICES}) 은 필수입니다.'}), 400

  user = User.query.filter_by(username=username).first()
  if not user:
    return jsonify({'msg': f'없는 사용자: {username}'}), 404

  old = user.role
  user.role = role
  user.role_granted_by = getattr(request, 'actor', 'unknown')
  user.role_granted_at = datetime.now()
  user.role_reason = (data.get('reason') or '')[:200]
  db.session.commit()
  return jsonify({'msg': '역할 부여 완료', 'username': username,
                  'old_role': old, 'new_role': role,
                  'granted_by': user.role_granted_by}), 200


@admin_bp.route('/revoke', methods=['POST'])
@admin_required
def revoke_role():
  """과잉권한 회수(최소권한 복원) → role 을 'user' 로. n8n 이 호출.
  body: {username, reason, student, severity, src_ip}
  회수가 실제로 일어나면 security_events 에 감사기록(source='privilege-guard')을 남긴다."""
  data = request.get_json(silent=True) or {}
  username = (data.get('username') or '').strip()
  if not username:
    return jsonify({'msg': 'username 은 필수입니다.'}), 400

  user = User.query.filter_by(username=username).first()
  if not user:
    return jsonify({'msg': f'없는 사용자: {username}'}), 404

  old = user.role
  actor = getattr(request, 'actor', 'unknown')
  if old == 'user':
    # 이미 최소권한 — 변경 없음(감사기록도 남기지 않아 소음 방지)
    return jsonify({'msg': '이미 user 권한(회수 불필요)', 'username': username,
                    'old_role': old, 'new_role': 'user', 'revoked': False}), 200

  user.role = 'user'
  user.role_granted_by = actor
  user.role_granted_at = datetime.now()
  user.role_reason = (data.get('reason') or f'{old}→user 회수 by {actor}')[:200]

  # 감사기록: 대시보드에서 보이도록 security_events 재사용
  ev = SecurityEvent(
      student=(data.get('student') or actor)[:50],
      src_ip=data.get('src_ip') or '0.0.0.0',
      fail_count=0, decision='deny',
      severity=data.get('severity', 'High'),
      reason=(data.get('reason') or f'과잉권한 회수: {username} {old}→user')[:200],
      users=username, source=data.get('source', 'privilege-guard'),
      generated_at=data.get('generated_at'),
  )
  db.session.add(ev)
  db.session.commit()
  return jsonify({'msg': '권한 회수 완료', 'username': username,
                  'old_role': old, 'new_role': 'user', 'revoked': True,
                  'event_id': ev.id, 'revoked_by': actor}), 200


@admin_bp.route('/lock', methods=['POST'])
@admin_required
def lock_account():
  """계정 잠금(브루트포스 대응) → is_locked=True. n8n 이 호출.
  body: {username, reason, student, src_ip, fail_count, severity}
  잠금이 실제로 일어나면 security_events 에 감사기록(source='login-guard')을 남긴다."""
  data = request.get_json(silent=True) or {}
  username = (data.get('username') or '').strip()
  if not username:
    return jsonify({'msg': 'username 은 필수입니다.'}), 400
  user = User.query.filter_by(username=username).first()
  if not user:
    return jsonify({'msg': f'없는 사용자: {username}'}), 404

  actor = getattr(request, 'actor', 'unknown')
  if user.is_locked:
    return jsonify({'msg': '이미 잠긴 계정', 'username': username,
                    'locked': True, 'changed': False}), 200

  user.is_locked = True
  user.locked_at = datetime.now()
  user.lock_reason = (data.get('reason') or f'브루트포스 자동 잠금 by {actor}')[:200]
  ev = SecurityEvent(
      student=(data.get('student') or actor)[:50],
      src_ip=data.get('src_ip') or '0.0.0.0',
      fail_count=int(data.get('fail_count') or 0), decision='deny',
      severity=data.get('severity', 'High'),
      reason=(data.get('reason') or f'계정 잠금: {username} (브루트포스)')[:200],
      users=username, source=data.get('source', 'login-guard'),
      generated_at=data.get('generated_at'),
  )
  db.session.add(ev)
  db.session.commit()
  return jsonify({'msg': '계정 잠금 완료', 'username': username, 'locked': True,
                  'changed': True, 'event_id': ev.id, 'locked_by': actor}), 200


@admin_bp.route('/unlock', methods=['POST'])
@admin_required
def unlock_account():
  """계정 잠금 해제 → is_locked=False + 실패 카운트 초기화. body: {username}"""
  data = request.get_json(silent=True) or {}
  username = (data.get('username') or '').strip()
  if not username:
    return jsonify({'msg': 'username 은 필수입니다.'}), 400
  user = User.query.filter_by(username=username).first()
  if not user:
    return jsonify({'msg': f'없는 사용자: {username}'}), 404

  user.is_locked = False
  user.failed_logins = 0
  user.lock_reason = None
  db.session.commit()
  return jsonify({'msg': '잠금 해제 완료', 'username': username, 'locked': False,
                  'unlocked_by': getattr(request, 'actor', 'unknown')}), 200


@admin_bp.route('/block', methods=['POST'])
@admin_required
def block_ip():
  """공격 IP 실차단(active response) → blocked_ips 에 추가. n8n 이 호출.
  body: {ip, reason, student, severity}. 이후 그 IP 요청은 미들웨어가 403(관리자 API 제외)."""
  data = request.get_json(silent=True) or {}
  ip = (data.get('ip') or data.get('src_ip') or '').strip()
  if not ip:
    return jsonify({'msg': 'ip(또는 src_ip) 는 필수입니다.'}), 400
  actor = getattr(request, 'actor', 'unknown')

  if not db.session.get(BlockedIP, ip):
    db.session.add(BlockedIP(ip=ip, reason=(data.get('reason') or f'자동 차단 by {actor}')[:200],
                             blocked_by=actor))
    ev = SecurityEvent(
        student=(data.get('student') or actor)[:50], src_ip=ip,
        fail_count=int(data.get('fail_count') or 0), decision='deny',
        severity=data.get('severity', 'High'),
        reason=(data.get('reason') or f'IP 실차단: {ip}')[:200],
        users='', source=data.get('source', 'ip-guard'),
        generated_at=data.get('generated_at'))
    db.session.add(ev)
    db.session.commit()
    return jsonify({'msg': 'IP 차단 완료', 'ip': ip, 'blocked': True,
                    'changed': True, 'event_id': ev.id, 'blocked_by': actor}), 200
  return jsonify({'msg': '이미 차단된 IP', 'ip': ip, 'blocked': True, 'changed': False}), 200


@admin_bp.route('/unblock', methods=['POST'])
@admin_required
def unblock_ip():
  """IP 차단 해제. body: {ip}"""
  data = request.get_json(silent=True) or {}
  ip = (data.get('ip') or data.get('src_ip') or '').strip()
  if not ip:
    return jsonify({'msg': 'ip 는 필수입니다.'}), 400
  row = db.session.get(BlockedIP, ip)
  if row:
    db.session.delete(row)
    db.session.commit()
  return jsonify({'msg': '차단 해제 완료', 'ip': ip, 'blocked': False,
                  'unblocked_by': getattr(request, 'actor', 'unknown')}), 200


@admin_bp.route('/blocked', methods=['GET'])
@admin_required
def list_blocked():
  """차단된 IP 목록. 검색: ?q=(IP·사유·차단자 부분 일치)

  페이징: ?page= &per_page= &sort=blocked_at|ip|blocked_by &order=
  page·per_page 가 없으면 예전처럼 전체(최신 차단 먼저) — 회원 목록과 같은 규약."""
  return _list_or_page(_blocked_filters(BlockedIP.query, request.args), 'blocked',
                       BlockedIP.blocked_at.desc(), _BLOCKED_SORTS, BlockedIP.ip,
                       'blocked_at')


# 차단 IP 목록 정렬 허용 컬럼 — 관리자 화면 표 머리글의 data-sort 와 같다.
# 동률 2차 정렬키는 기본키 ip(겹치지 않는다).
_BLOCKED_SORTS = {
    'blocked_at': BlockedIP.blocked_at,
    'ip': BlockedIP.ip,
    'blocked_by': BlockedIP.blocked_by,
}


def _blocked_filters(q, src):
  """차단 IP 목록·전체 해제가 같이 쓰는 검색. q 는 IP·사유·차단자 부분 일치."""
  term = (src.get('q') or '').strip()
  if term:
    q = q.filter(db.or_(BlockedIP.ip.contains(term, autoescape=True),
                        BlockedIP.reason.contains(term, autoescape=True),
                        BlockedIP.blocked_by.contains(term, autoescape=True)))
  return q


@admin_bp.route('/blocked/block', methods=['POST'])
@admin_required
def block_ips_bulk():
  """IP 일괄 차단. body: {ips: ['1.2.3.4', '2001:db8::1', ..], reason?}

  - 형식이 IP 가 아니면 invalid 로 돌려주고 건너뛴다(오타가 표에 남지 않게).
  - 이미 차단된 IP 는 skipped — 처음 차단한 시각·사유를 덮어쓰지 않는다.
  - ★ 지금 요청한 사람의 IP 는 self_skipped — /api/admin 은 차단돼도 통하지만
    관리자 화면(/admin)·로그인은 403 이 되어 그 자리에서 화면을 잃는다.
  - '전부 차단(all)' 은 없다. 감사기록: IP 마다 security_events 한 줄(source='admin-console')."""
  import ipaddress

  data = request.get_json(silent=True) or {}
  ips = _parse_ips(data)
  if ips is None:
    return jsonify({'msg': f'ips(IP 문자열 목록, 1~{_BULK_MAX}개)가 필요합니다.'}), 400

  valid, invalid = [], []
  for raw in ips:
    try:
      valid.append(str(ipaddress.ip_address(raw)))   # 표기 정규화(IPv6 축약 등)
    except ValueError:
      invalid.append(raw)
  valid = list(dict.fromkeys(valid))

  me = _requester_ip()
  self_skipped = [ip for ip in valid if ip == me]
  existing = {r.ip for r in BlockedIP.query.filter(BlockedIP.ip.in_(valid))} if valid else set()
  skipped = sorted(ip for ip in valid if ip in existing and ip != me)
  targets = [ip for ip in valid if ip not in existing and ip != me]

  actor = getattr(request, 'actor', 'unknown')
  reason = (data.get('reason') or f'관리자 수동 차단 by {actor}')[:200]
  for ip in targets:
    db.session.add(BlockedIP(ip=ip, reason=reason, blocked_by=actor))
    db.session.add(SecurityEvent(
        student=actor[:50], src_ip=ip, fail_count=0, decision='deny', severity='Medium',
        reason=f'관리자 IP 차단: {reason}'[:200], users='', source='admin-console'))
  db.session.commit()
  return _bulk_ok('개 IP 차단', sorted(targets), skipped=skipped,
                  invalid=sorted(invalid), self_skipped=self_skipped)


@admin_bp.route('/blocked/unblock', methods=['POST'])
@admin_required
def unblock_ips_bulk():
  """IP 일괄 차단 해제(= 차단 목록에서 삭제).

  body: {ips: [..]}         → 고른 IP 만
        {all: true, q?}     → 검색 조건에 맞는 차단 IP 전부(다른 페이지 포함)
  형식 검사는 하지 않는다 — 예전에 형식 검사 없이 들어간 값도 지울 수 있어야 한다."""
  data = request.get_json(silent=True) or {}
  if data.get('all') is True:
    rows = _blocked_filters(BlockedIP.query, data).all()
    not_found = []
  else:
    ips = _parse_ips(data)
    if ips is None:
      return jsonify({'msg': f'ips(IP 문자열 목록, 1~{_BULK_MAX}개) 또는 '
                             'all: true 가 필요합니다.'}), 400
    rows = BlockedIP.query.filter(BlockedIP.ip.in_(ips)).all()
    not_found = sorted(set(ips) - {r.ip for r in rows})

  changed = sorted(r.ip for r in rows)
  for r in rows:
    db.session.delete(r)
  db.session.commit()
  return _bulk_ok('개 IP 차단 해제', changed, not_found=not_found)


_SEV_RANK = {'Low': 1, 'Medium': 2, 'High': 3, 'Critical': 4}


def _build_summary(src_ip, events):
  """security_events 를 사람이 읽는 인시던트 요약(타임라인·집계·조치)으로 취합."""
  by_source, actions = {}, set()
  worst = 'Low'
  lines = []
  for e in events:
    by_source[e.source] = by_source.get(e.source, 0) + 1
    if e.decision:
      actions.add(e.decision)
    if _SEV_RANK.get(e.severity, 1) > _SEV_RANK.get(worst, 1):
      worst = e.severity
    when = e.created_at.strftime('%Y-%m-%d %H:%M:%S') if e.created_at else (e.generated_at or '?')
    lines.append(f"- {when} [{e.severity}/{e.source}] {e.reason or ''} (users={e.users or '-'})")
  first = events[-1].created_at if events and events[-1].created_at else None
  last = events[0].created_at if events and events[0].created_at else None
  src_summary = ', '.join(f'{k}×{v}' for k, v in sorted(by_source.items()))
  summary = (
      f"[인시던트 요약] 출발지 {src_ip}\n"
      f"- 관련 이벤트: {len(events)}건 ({src_summary})\n"
      f"- 최초/최종: {first} ~ {last}\n"
      f"- 취해진 조치: {', '.join(sorted(actions)) or '없음'}\n"
      f"- 최고 심각도: {worst}\n"
      f"[타임라인]\n" + "\n".join(lines[:20])
  )
  return summary, worst, ', '.join(sorted(actions)) or '없음', len(events)


@admin_bp.route('/incident', methods=['POST'])
@admin_required
def create_incident():
  """인시던트 티켓 생성/갱신. body: {src_ip, title?, severity?, student?, hours?}

  같은 src_ip 의 '열린' 티켓이 있으면 갱신(중복 방지), 없으면 새로 만든다.
  요약은 최근 hours(기본 24) 시간의 security_events 를 자동 취합한다(사람이 읽는 리포트)."""
  data = request.get_json(silent=True) or {}
  src_ip = (data.get('src_ip') or data.get('ip') or '').strip()
  if not src_ip:
    return jsonify({'msg': 'src_ip 는 필수입니다.'}), 400
  actor = getattr(request, 'actor', 'unknown')
  hours = int(data.get('hours') or 24)
  since = datetime.now() - timedelta(hours=hours)
  # 같은 키의 '마지막으로 종료된 티켓' 이후 사건만 취합한다 — 이미 처리·종료한 사건을
  # 새 티켓이 다시 흡수하지 않게([129] E2E 에서 발견). 같은 초 경계는 포함(>=) 쪽으로:
  # 새 증거를 놓치는 것보다 한 건 겹치는 편이 안전하다.
  last_closed = (Incident.query
                 .filter(Incident.src_ip == src_ip, Incident.status == 'closed',
                         Incident.closed_at.isnot(None))
                 .order_by(Incident.closed_at.desc()).first())
  if last_closed and last_closed.closed_at > since:
    since = last_closed.closed_at
  events = (SecurityEvent.query
            .filter(SecurityEvent.src_ip == src_ip, SecurityEvent.created_at >= since)
            .order_by(SecurityEvent.created_at.desc()).all())
  summary, worst, actions, cnt = _build_summary(src_ip, events)
  severity = data.get('severity') or worst
  title = (data.get('title') or f'보안 인시던트: {src_ip} ({cnt}건)')[:200]

  inc = Incident.query.filter_by(src_ip=src_ip, status='open').first()
  created = False
  if not inc:
    inc = Incident(src_ip=src_ip, status='open'); db.session.add(inc); created = True
  inc.title = title
  # 심각도는 '내려가지 않는다': 요청값·취합 최고값·기존 티켓 값 중 가장 높은 것
  # (Critical 티켓에 나중에 Medium 경보가 합쳐져도 Critical 유지 — [129] E2E 에서 발견해 수정)
  inc.severity = max((severity, worst, inc.severity or 'Low'),
                     key=lambda s: _SEV_RANK.get(s, 0))
  inc.summary = summary
  inc.event_count = cnt
  inc.actions = actions[:255]
  inc.student = (data.get('student') or actor)[:50]
  db.session.commit()
  return jsonify({'msg': '인시던트 생성' if created else '인시던트 갱신',
                  'created': created, 'incident': inc.to_dict()}), (201 if created else 200)


@admin_bp.route('/incidents', methods=['GET'])
@admin_required
def list_incidents():
  """인시던트 목록. ?status=open|closed 로 필터."""
  status = request.args.get('status')
  q = Incident.query
  if status in ('open', 'closed'):
    q = q.filter_by(status=status)
  rows = q.order_by(Incident.updated_at.desc()).all()
  return jsonify({'count': len(rows), 'incidents': [r.to_dict() for r in rows]})


@admin_bp.route('/incident/close', methods=['POST'])
@admin_required
def close_incident():
  """인시던트 종료(status=closed). body: {id}"""
  data = request.get_json(silent=True) or {}
  inc = db.session.get(Incident, int(data.get('id') or 0))
  if not inc:
    return jsonify({'msg': '없는 인시던트'}), 404
  inc.status = 'closed'
  inc.closed_at = datetime.now()
  db.session.commit()
  return jsonify({'msg': '인시던트 종료', 'incident': inc.to_dict()}), 200


@admin_bp.route('/incidents/close', methods=['POST'])
@admin_required
def close_incidents_bulk():
  """인시던트 일괄 종료 — 대시보드의 '선택 종료 / 전체 종료' 버튼이 부른다.

  body: {ids: [1, 2, ...]}                       → 고른 티켓만
        {all_open: true, severity?, student?}    → 조건에 맞는 열린 티켓 전부
  이미 종료된 티켓은 건너뛴다(skipped) — 종료 시각을 덮어쓰면 '언제 끝났나'가 바뀐다.
  """
  data = request.get_json(silent=True) or {}
  ids = _parse_ids(data)
  q = Incident.query.filter(Incident.status == 'open')

  if data.get('all_open') is True:
    if data.get('severity'):
      q = q.filter(Incident.severity == data['severity'])
    if data.get('student'):
      q = q.filter(Incident.student == data['student'])
    targets, skipped, not_found = q.all(), [], []
  elif ids is not None:
    wanted = set(ids)
    targets = q.filter(Incident.id.in_(wanted)).all()
    known = {i for (i,) in db.session.query(Incident.id).filter(Incident.id.in_(wanted))}
    skipped = sorted(known - {t.id for t in targets})
    not_found = sorted(wanted - known)
  else:
    return jsonify({'msg': f'ids(정수 목록, 1~{_BULK_MAX}개) 또는 '
                           'all_open: true 가 필요합니다.'}), 400

  now = datetime.now()
  for inc in targets:
    inc.status = 'closed'
    inc.closed_at = now
  db.session.commit()
  closed = sorted(t.id for t in targets)
  return jsonify({'msg': f'인시던트 {len(closed)}건 종료', 'count': len(closed),
                  'closed': closed, 'skipped': skipped, 'not_found': not_found,
                  'actor': getattr(request, 'actor', 'unknown')}), 200
