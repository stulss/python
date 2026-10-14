"""관리자 차단 IP 목록(페이징·검색) + 일괄 차단/삭제 API 테스트.

GET  /api/admin/blocked           ?q= &page= &per_page= &sort=blocked_at|ip|blocked_by &order=
POST /api/admin/blocked/block     {ips: [..], reason?}
POST /api/admin/blocked/unblock   {ips: [..]} | {all: true, q?}

차단 IP 표는 '행이 있으면 차단'이라 삭제 = 차단 해제다.

★ 호환: page·per_page 가 없으면 예전처럼 전체(최신 차단 먼저).
★ 자기 IP 차단 금지: /api/admin/* 는 차단돼도 통하지만 관리자 화면(/admin)·로그인은
  막힌다 — 자기 IP 를 차단하면 그 자리에서 관리자 화면을 열 수 없게 된다.
"""
from datetime import timedelta

import pytest

from app import create_app
from extensions import db

ADMIN = {'X-API-Key': 'test-admin-key'}
PW = 'pw12345'
LIST = '/api/admin/blocked'
BLOCK = '/api/admin/blocked/block'
UNBLOCK = '/api/admin/blocked/unblock'


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


def block(client, *ips, reason=None):
  body = {'ips': list(ips)}
  if reason:
    body['reason'] = reason
  res = client.post(BLOCK, headers=ADMIN, json=body)
  assert res.status_code == 200, res.get_data(as_text=True)
  return res.get_json()


def blocked_ips(client):
  return sorted(r['ip'] for r in client.get(LIST, headers=ADMIN).get_json()['blocked'])


def jwt_for(client, username, role=None):
  client.post('/api/auth/register', json={'username': username, 'password': PW})
  if role:
    client.post('/api/admin/grant', headers=ADMIN,
                json={'username': username, 'role': role, 'reason': 'test'})
  token = client.post('/api/auth/login', json={'username': username, 'password': PW}
                      ).get_json()['access_token']
  return {'Authorization': f'Bearer {token}'}


# ── 목록 ────────────────────────────────────────────────
def test_without_paging_returns_all(client):
  block(client, *[f'198.51.100.{i}' for i in range(1, 26)])
  body = client.get(LIST, headers=ADMIN).get_json()
  assert body['count'] == 25 and len(body['blocked']) == 25


def test_paging_meta(client):
  block(client, *[f'198.51.100.{i}' for i in range(1, 26)])
  body = client.get(LIST + '?page=2&per_page=10&sort=ip&order=asc', headers=ADMIN).get_json()
  assert body['count'] == 10 and body['total'] == 25 and body['total_pages'] == 3


def test_search_matches_ip_and_reason(client):
  block(client, '198.51.100.1', '198.51.100.2', reason='nikto scan')
  block(client, '203.0.113.9', reason='brute force')
  by_ip = client.get(LIST + '?q=203.0&page=1', headers=ADMIN).get_json()
  by_reason = client.get(LIST + '?q=nikto&page=1', headers=ADMIN).get_json()
  assert [r['ip'] for r in by_ip['blocked']] == ['203.0.113.9']
  assert by_reason['total'] == 2


def test_search_treats_wildcards_literally(client):
  block(client, '198.51.100.1')
  assert client.get(LIST + '?q=%25&page=1', headers=ADMIN).get_json()['total'] == 0


def test_unknown_sort_is_400(client):
  assert client.get(LIST + '?page=1&sort=reason', headers=ADMIN).status_code == 400


# ── 일괄 차단 ────────────────────────────────────────────
def test_bulk_block(client):
  body = block(client, '198.51.100.1', '2001:db8::1', reason='수동')
  assert sorted(body['changed']) == ['198.51.100.1', '2001:db8::1'] and body['count'] == 2
  assert blocked_ips(client) == ['198.51.100.1', '2001:db8::1']


def test_bulk_block_actually_blocks_requests(client):
  block(client, '198.51.100.7')
  res = client.get('/api/posts', headers={'X-Forwarded-For': '198.51.100.7'})
  assert res.status_code == 403


def test_bulk_block_skips_existing_and_invalid(client):
  block(client, '198.51.100.1')
  body = block(client, '198.51.100.1', 'not-an-ip', '999.1.1.1', '198.51.100.2')
  assert body['changed'] == ['198.51.100.2']
  assert body['skipped'] == ['198.51.100.1']
  assert sorted(body['invalid']) == ['999.1.1.1', 'not-an-ip']


def test_cannot_block_own_ip(client):
  """관리자 화면을 쓰는 사람의 IP 를 막으면 그 화면이 바로 403 이 된다."""
  res = client.post(BLOCK, headers={**ADMIN, 'X-Forwarded-For': '198.51.100.50'},
                    json={'ips': ['198.51.100.50', '198.51.100.51']})
  body = res.get_json()
  assert body['changed'] == ['198.51.100.51'] and body['self_skipped'] == ['198.51.100.50']
  assert blocked_ips(client) == ['198.51.100.51']


def test_bulk_block_records_audit_events(client):
  block(client, '198.51.100.1', '198.51.100.2')
  events = client.get('/api/security/events').get_json()['events']
  mine = [e for e in events if e['source'] == 'admin-console']
  assert sorted(e['src_ip'] for e in mine) == ['198.51.100.1', '198.51.100.2']


# ── 일괄 삭제(차단 해제) ─────────────────────────────────
def test_bulk_unblock_selected(client):
  block(client, '198.51.100.1', '198.51.100.2', '198.51.100.3')
  body = client.post(UNBLOCK, headers=ADMIN,
                     json={'ips': ['198.51.100.1', '198.51.100.3', '198.51.100.99']}).get_json()
  assert body['changed'] == ['198.51.100.1', '198.51.100.3']
  assert body['not_found'] == ['198.51.100.99']
  assert blocked_ips(client) == ['198.51.100.2']


def test_unblock_all(client):
  block(client, '198.51.100.1', '198.51.100.2')
  body = client.post(UNBLOCK, headers=ADMIN, json={'all': True}).get_json()
  assert body['count'] == 2 and blocked_ips(client) == []


def test_unblock_all_respects_search(client):
  block(client, '198.51.100.1', '198.51.100.2')
  block(client, '203.0.113.9')
  client.post(UNBLOCK, headers=ADMIN, json={'all': True, 'q': '198.51'})
  assert blocked_ips(client) == ['203.0.113.9']


@pytest.mark.parametrize('url', [BLOCK, UNBLOCK])
@pytest.mark.parametrize('payload', [{}, {'ips': []}, {'ips': '1.2.3.4'}, {'ips': [1]},
                                     {'all': False}])
def test_bad_payload_is_400(client, url, payload):
  block(client, '198.51.100.1')
  assert client.post(url, headers=ADMIN, json=payload).status_code == 400
  assert blocked_ips(client) == ['198.51.100.1']


def test_block_does_not_accept_all_flag(client):
  assert client.post(BLOCK, headers=ADMIN, json={'all': True}).status_code == 400


# ── 인가 ─────────────────────────────────────────────────
@pytest.mark.parametrize('url', [BLOCK, UNBLOCK])
def test_anonymous_and_plain_user_rejected(client, url):
  block(client, '198.51.100.1')
  assert client.post(url, json={'ips': ['198.51.100.2']}).status_code == 401
  assert client.post(url, headers=jwt_for(client, 'plain'),
                     json={'ips': ['198.51.100.2']}).status_code in (401, 403)
  assert client.get(LIST + '?page=1', headers=jwt_for(client, 'plain2')).status_code in (401, 403)
  assert blocked_ips(client) == ['198.51.100.1']


def test_admin_jwt_can_block(client):
  res = client.post(BLOCK, headers=jwt_for(client, 'boss', 'admin'),
                    json={'ips': ['198.51.100.1']})
  assert res.status_code == 200 and blocked_ips(client) == ['198.51.100.1']


# ── 화면 머리글 ↔ 서버 정렬 화이트리스트 ─────────────────
def test_admin_page_sort_headers_match_server_whitelists(client):
  """data-sort 가 서버 허용 목록 밖이면 그 머리글을 누르는 순간 400 → 표가 빈다."""
  import re
  from controllers.admin_controller import _BLOCKED_SORTS, _USER_SORTS

  html = client.get('/admin').get_data(as_text=True)
  for head_id, allowed in (('user-head', _USER_SORTS), ('blocked-head', _BLOCKED_SORTS)):
    thead = re.search(rf'<thead id="{head_id}".*?</thead>', html, re.S).group(0)
    sorts = re.findall(r'data-sort="([^"]+)"', thead)
    assert sorts and set(sorts) <= set(allowed), (head_id, sorts)
