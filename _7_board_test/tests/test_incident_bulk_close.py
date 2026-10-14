"""인시던트 티켓 일괄 종료 API 테스트 — 대시보드 '선택 종료 / 전체 종료'.

POST /api/admin/incidents/close
  {ids: [1, 2]}                     → 고른 티켓만 종료
  {all_open: true, severity?, student?} → 조건에 맞는 열린 티켓 전부 종료

쓰기라서 단건 종료(/api/admin/incident/close)와 똑같이 관리자 키 또는 admin 로그인이
필요하다. 대시보드는 누구나 열 수 있지만 종료 버튼은 admin 만 통과한다.
"""
from datetime import timedelta

import pytest

from app import create_app
from extensions import db

ADMIN = {'X-API-Key': 'test-admin-key'}
SEC = {'X-API-Key': 'test-security-key'}
PW = 'pw12345'
URL = '/api/admin/incidents/close'


@pytest.fixture
def client(tmp_path):
  class TestConfig:
    SQLALCHEMY_DATABASE_URI = f"sqlite:///{tmp_path / 'test.db'}"
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    JWT_SECRET_KEY = 'test-secret-key'
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(hours=1)
    SECURITY_API_KEY = 'test-security-key'
    ADMIN_API_KEY = 'test-admin-key'
    ADMIN_ALLOWLIST = []
    AUTO_POST_ON_DENY = False
    PUBLIC_API_KEY = None
    PUBLIC_API_URL = 'http://example.invalid/'

  application = create_app(TestConfig)
  yield application.test_client()
  with application.app_context():
    db.session.remove()
    db.engine.dispose()


def seed(client, src_ip, severity='High', student='lab'):
  """보안 이벤트 1건 + 그 출발지의 열린 인시던트 티켓 1건."""
  res = client.post('/api/security/events', headers=SEC, json={
      'student': student, 'src_ip': src_ip, 'decision': 'deny',
      'severity': severity, 'reason': f'{severity} seed', 'source': 'ip-guard'})
  assert res.status_code == 201
  res = client.post('/api/admin/incident', headers=ADMIN,
                    json={'src_ip': src_ip, 'severity': severity, 'student': student})
  assert res.status_code in (200, 201)
  return res.get_json()['incident']


def statuses(client):
  body = client.get('/api/security/incidents?per_page=100').get_json()
  return {t['id']: t['status'] for t in body['incidents']}


def jwt_for(client, username, role=None):
  client.post('/api/auth/register', json={'username': username, 'password': PW})
  if role:
    client.post('/api/admin/grant', headers=ADMIN,
                json={'username': username, 'role': role, 'reason': 'test'})
  token = client.post('/api/auth/login', json={'username': username, 'password': PW}
                      ).get_json()['access_token']
  return {'Authorization': f'Bearer {token}'}


# ── 선택 종료 ─────────────────────────────────────────────
def test_close_selected_ids_only(client):
  a = seed(client, '203.0.113.1')
  b = seed(client, '203.0.113.2')
  c = seed(client, '203.0.113.3')

  res = client.post(URL, headers=ADMIN, json={'ids': [a['id'], c['id']]})
  assert res.status_code == 200
  body = res.get_json()
  assert sorted(body['closed']) == sorted([a['id'], c['id']])
  assert body['count'] == 2

  st = statuses(client)
  assert st[a['id']] == 'closed' and st[c['id']] == 'closed'
  assert st[b['id']] == 'open'                       # 고르지 않은 것은 그대로


def test_close_sets_closed_at(client):
  a = seed(client, '203.0.113.1')
  client.post(URL, headers=ADMIN, json={'ids': [a['id']]})
  row = client.get('/api/security/incidents').get_json()['incidents'][0]
  assert row['closed_at'] is not None


def test_already_closed_is_skipped_and_keeps_closed_at(client):
  """이미 종료된 티켓의 종료 시각을 덮어쓰면 '언제 끝났나' 기록이 바뀐다."""
  a = seed(client, '203.0.113.1')
  client.post('/api/admin/incident/close', headers=ADMIN, json={'id': a['id']})
  before = client.get('/api/security/incidents').get_json()['incidents'][0]['closed_at']

  res = client.post(URL, headers=ADMIN, json={'ids': [a['id']]})
  body = res.get_json()
  assert body['closed'] == [] and body['skipped'] == [a['id']]
  after = client.get('/api/security/incidents').get_json()['incidents'][0]['closed_at']
  assert after == before


def test_unknown_ids_are_reported(client):
  a = seed(client, '203.0.113.1')
  body = client.post(URL, headers=ADMIN, json={'ids': [a['id'], 9999]}).get_json()
  assert body['closed'] == [a['id']]
  assert body['not_found'] == [9999]


@pytest.mark.parametrize('payload', [
    {},                                  # 아무것도 안 고름
    {'ids': []},                         # 빈 선택
    {'ids': 'abc'},                      # 목록이 아님
    {'ids': [1, 'x']},                   # 숫자가 아닌 id
    {'all_open': False},
])
def test_bad_payload_is_400(client, payload):
  seed(client, '203.0.113.1')
  assert client.post(URL, headers=ADMIN, json=payload).status_code == 400
  assert set(statuses(client).values()) == {'open'}  # 아무것도 안 닫혔다


# ── 전체 종료 ─────────────────────────────────────────────
def test_close_all_open(client):
  ids = [seed(client, f'203.0.113.{i}')['id'] for i in range(1, 4)]
  res = client.post(URL, headers=ADMIN, json={'all_open': True})
  assert res.status_code == 200
  assert sorted(res.get_json()['closed']) == sorted(ids)
  assert set(statuses(client).values()) == {'closed'}


def test_close_all_open_respects_filters(client):
  """화면에서 '심각도 Critical' 로 좁혀 놓고 전체 종료하면 그 조건만 닫혀야 한다."""
  crit = seed(client, '203.0.113.1', 'Critical')
  high = seed(client, '203.0.113.2', 'High')
  other = seed(client, '203.0.113.3', 'Critical', student='other')

  res = client.post(URL, headers=ADMIN,
                    json={'all_open': True, 'severity': 'Critical', 'student': 'lab'})
  assert res.get_json()['closed'] == [crit['id']]
  st = statuses(client)
  assert st[high['id']] == 'open' and st[other['id']] == 'open'


def test_summary_reflects_bulk_close(client):
  seed(client, '203.0.113.1'); seed(client, '203.0.113.2')
  client.post(URL, headers=ADMIN, json={'all_open': True})
  s = client.get('/api/security/incidents/summary').get_json()
  assert s['by_status'].get('open', 0) == 0
  assert s['by_status']['closed'] == 2


# ── 인가 ─────────────────────────────────────────────────
def test_anonymous_cannot_close(client):
  a = seed(client, '203.0.113.1')
  assert client.post(URL, json={'ids': [a['id']]}).status_code == 401
  assert client.post(URL, json={'all_open': True}).status_code == 401
  assert statuses(client)[a['id']] == 'open'


def test_plain_user_cannot_close(client):
  a = seed(client, '203.0.113.1')
  res = client.post(URL, headers=jwt_for(client, 'plain'), json={'all_open': True})
  assert res.status_code in (401, 403)
  assert statuses(client)[a['id']] == 'open'


def test_admin_jwt_can_close(client):
  """대시보드는 X-API-Key 가 아니라 admin 로그인 토큰으로 부른다."""
  a = seed(client, '203.0.113.1')
  res = client.post(URL, headers=jwt_for(client, 'boss', 'admin'), json={'ids': [a['id']]})
  assert res.status_code == 200
  assert statuses(client)[a['id']] == 'closed'
