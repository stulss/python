"""관리자 회원 목록(페이징·검색·차단 필터) + 일괄 차단/해제 API 테스트.

GET  /api/admin/users     ?q= &role= &locked=1|0 &page= &per_page= &sort= &order=
POST /api/admin/users/lock   {ids: [..], reason?}
POST /api/admin/users/unlock {ids: [..]} | {all_locked: true, q?, role?}

'차단' = 계정 잠금(is_locked). 잠긴 계정은 로그인이 423 으로 거부된다.

★ 호환: page·per_page 를 주지 않으면 예전처럼 **전체**를 돌려준다.
  privilege_revoke_bot.py 가 `?role=admin` 으로 admin 전원을 읽는데, 기본 20건으로
  잘라 버리면 21번째 admin 부터는 과잉권한 탐지에서 조용히 빠진다.
"""
from datetime import timedelta

import pytest

from app import create_app
from extensions import db

ADMIN = {'X-API-Key': 'test-admin-key'}
PW = 'pw12345'
LIST = '/api/admin/users'
LOCK = '/api/admin/users/lock'
UNLOCK = '/api/admin/users/unlock'


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


def register(client, *names):
  for n in names:
    assert client.post('/api/auth/register',
                       json={'username': n, 'password': PW}).status_code in (200, 201)


def ids_of(client, *names):
  users = client.get(LIST, headers=ADMIN).get_json()['users']
  by = {u['username']: u['id'] for u in users}
  return [by[n] for n in names]


def locked_map(client):
  return {u['username']: u['is_locked']
          for u in client.get(LIST, headers=ADMIN).get_json()['users']}


def jwt_for(client, username, role=None):
  register(client, username)
  if role:
    client.post('/api/admin/grant', headers=ADMIN,
                json={'username': username, 'role': role, 'reason': 'test'})
  token = client.post('/api/auth/login', json={'username': username, 'password': PW}
                      ).get_json()['access_token']
  return {'Authorization': f'Bearer {token}'}


# ── 목록: 호환 ───────────────────────────────────────────
def test_without_paging_params_returns_everyone(client):
  """회수봇 호환 — 페이징 파라미터가 없으면 25명이어도 25명 전부."""
  register(client, *[f'u{i:02d}' for i in range(25)])
  body = client.get(LIST, headers=ADMIN).get_json()
  assert body['count'] == 25 and len(body['users']) == 25


def test_role_filter_still_works_without_paging(client):
  register(client, 'a1', 'a2', 'plain')
  for n in ('a1', 'a2'):
    client.post('/api/admin/grant', headers=ADMIN, json={'username': n, 'role': 'admin'})
  body = client.get(LIST + '?role=admin', headers=ADMIN).get_json()
  assert sorted(u['username'] for u in body['users']) == ['a1', 'a2']


# ── 목록: 페이징·검색·필터 ───────────────────────────────
def test_paging_meta(client):
  register(client, *[f'u{i:02d}' for i in range(25)])
  body = client.get(LIST + '?page=2&per_page=10&sort=id&order=asc', headers=ADMIN).get_json()
  assert body['count'] == 10
  assert body['total'] == 25 and body['total_pages'] == 3 and body['page'] == 2
  assert [u['username'] for u in body['users']][0] == 'u10'


def test_search_by_username_substring(client):
  register(client, 'alice', 'malice', 'bob')
  body = client.get(LIST + '?q=lic&page=1', headers=ADMIN).get_json()
  assert sorted(u['username'] for u in body['users']) == ['alice', 'malice']
  assert body['total'] == 2


def test_search_treats_wildcards_literally(client):
  """q='%' 가 LIKE 와일드카드로 먹으면 전원이 검색된다."""
  register(client, 'alice', 'bob')
  body = client.get(LIST + '?q=%25&page=1', headers=ADMIN).get_json()
  assert body['total'] == 0


def test_locked_filter(client):
  register(client, 'x', 'y', 'z')
  client.post(LOCK, headers=ADMIN, json={'ids': ids_of(client, 'y')})
  on = client.get(LIST + '?locked=1&page=1', headers=ADMIN).get_json()
  off = client.get(LIST + '?locked=0&page=1', headers=ADMIN).get_json()
  assert [u['username'] for u in on['users']] == ['y']
  assert sorted(u['username'] for u in off['users']) == ['x', 'z']


def test_unknown_sort_is_400(client):
  assert client.get(LIST + '?page=1&sort=password', headers=ADMIN).status_code == 400


# ── 일괄 차단 ────────────────────────────────────────────
def test_bulk_lock_selected(client):
  register(client, 'x', 'y', 'z')
  res = client.post(LOCK, headers=ADMIN, json={'ids': ids_of(client, 'x', 'z'),
                                               'reason': '수동 차단'})
  assert res.status_code == 200
  assert res.get_json()['count'] == 2
  assert locked_map(client) == {'x': True, 'y': False, 'z': True}


def test_locked_user_cannot_login(client):
  register(client, 'x')
  client.post(LOCK, headers=ADMIN, json={'ids': ids_of(client, 'x')})
  res = client.post('/api/auth/login', json={'username': 'x', 'password': PW})
  assert res.status_code == 423


def test_bulk_lock_skips_already_locked(client):
  register(client, 'x')
  [xid] = ids_of(client, 'x')
  client.post(LOCK, headers=ADMIN, json={'ids': [xid]})
  body = client.post(LOCK, headers=ADMIN, json={'ids': [xid]}).get_json()
  assert body['changed'] == [] and body['skipped'] == [xid]


def test_admin_cannot_lock_self(client):
  """자기 계정을 잠그면 그 자리에서 관리자 화면에서 쫓겨난다 — 거부한다."""
  h = jwt_for(client, 'boss', 'admin')
  register(client, 'x')
  boss, x = ids_of(client, 'boss', 'x')
  body = client.post(LOCK, headers=h, json={'ids': [boss, x]}).get_json()
  assert body['changed'] == [x] and body['self_skipped'] == [boss]
  assert locked_map(client)['boss'] is False


def test_bulk_lock_records_audit_event(client):
  register(client, 'x', 'y')
  client.post(LOCK, headers=ADMIN, json={'ids': ids_of(client, 'x', 'y')})
  events = client.get('/api/security/events').get_json()['events']
  assert any(e['source'] == 'admin-console' and 'x' in (e['users'] or '') for e in events)


# ── 일괄 해제 ────────────────────────────────────────────
def test_bulk_unlock_selected_resets_failed_logins(client):
  register(client, 'x', 'y')
  client.post(LOCK, headers=ADMIN, json={'ids': ids_of(client, 'x', 'y')})
  res = client.post(UNLOCK, headers=ADMIN, json={'ids': ids_of(client, 'x')})
  assert res.status_code == 200 and res.get_json()['count'] == 1
  assert locked_map(client) == {'x': False, 'y': True}
  x = [u for u in client.get(LIST, headers=ADMIN).get_json()['users'] if u['username'] == 'x'][0]
  assert x['failed_logins'] == 0 and x['lock_reason'] is None


def test_unlock_all_locked(client):
  register(client, 'x', 'y', 'z')
  client.post(LOCK, headers=ADMIN, json={'ids': ids_of(client, 'x', 'y', 'z')})
  body = client.post(UNLOCK, headers=ADMIN, json={'all_locked': True}).get_json()
  assert body['count'] == 3
  assert set(locked_map(client).values()) == {False}


def test_unlock_all_locked_respects_search(client):
  """검색으로 좁힌 상태에서 '전체 해제'는 그 검색 결과만 푼다."""
  register(client, 'alice', 'malice', 'bob')
  client.post(LOCK, headers=ADMIN, json={'ids': ids_of(client, 'alice', 'malice', 'bob')})
  client.post(UNLOCK, headers=ADMIN, json={'all_locked': True, 'q': 'lic'})
  assert locked_map(client) == {'alice': False, 'malice': False, 'bob': True}


@pytest.mark.parametrize('url', [LOCK, UNLOCK])
@pytest.mark.parametrize('payload', [{}, {'ids': []}, {'ids': 'x'}, {'ids': [1, 'a']},
                                     {'ids': [True]}])
def test_bad_payload_is_400(client, url, payload):
  register(client, 'x')
  assert client.post(url, headers=ADMIN, json=payload).status_code == 400


def test_lock_does_not_accept_all_flag(client):
  """'전원 차단'은 사고가 크다 — 차단은 고른 id 로만 한다."""
  register(client, 'x')
  assert client.post(LOCK, headers=ADMIN, json={'all_locked': True}).status_code == 400
  assert locked_map(client)['x'] is False


def test_unknown_ids_reported(client):
  register(client, 'x')
  [xid] = ids_of(client, 'x')
  body = client.post(LOCK, headers=ADMIN, json={'ids': [xid, 9999]}).get_json()
  assert body['changed'] == [xid] and body['not_found'] == [9999]


# ── 인가 ─────────────────────────────────────────────────
@pytest.mark.parametrize('url', [LOCK, UNLOCK])
def test_anonymous_and_plain_user_rejected(client, url):
  register(client, 'x')
  [xid] = ids_of(client, 'x')
  assert client.post(url, json={'ids': [xid]}).status_code == 401
  assert client.post(url, headers=jwt_for(client, 'plain'),
                     json={'ids': [xid]}).status_code in (401, 403)
  assert client.get(LIST + '?page=1', headers=jwt_for(client, 'plain2')).status_code in (401, 403)


# ── 일괄 삭제 ────────────────────────────────────────────
DELETE = '/api/admin/users/delete'


def write_post(client, username, title='hello'):
  token = client.post('/api/auth/login', json={'username': username, 'password': PW}
                      ).get_json()['access_token']
  res = client.post('/api/posts', headers={'Authorization': f'Bearer {token}'},
                    json={'title': title, 'content': 'c'})
  assert res.status_code in (200, 201), res.get_data(as_text=True)


def usernames(client):
  return sorted(u['username'] for u in client.get(LIST, headers=ADMIN).get_json()['users'])


def test_bulk_delete_selected(client):
  register(client, 'x', 'y', 'z')
  res = client.post(DELETE, headers=ADMIN, json={'ids': ids_of(client, 'x', 'z')})
  assert res.status_code == 200
  body = res.get_json()
  assert body['count'] == 2
  assert usernames(client) == ['y']


def test_delete_removes_their_posts_too(client):
  """posts.author_id 는 NOT NULL 외래키 — 글을 남겨 두면 고아 글이 되거나 FK 오류."""
  register(client, 'x', 'y')
  write_post(client, 'x', 'x-post'); write_post(client, 'x', 'x-post2')
  write_post(client, 'y', 'y-post')
  body = client.post(DELETE, headers=ADMIN, json={'ids': ids_of(client, 'x')}).get_json()
  assert body['posts_deleted'] == 2
  titles = [p['title'] for p in client.get('/api/posts').get_json()['posts']]
  assert titles == ['y-post']


def test_deleted_user_cannot_login(client):
  register(client, 'x')
  client.post(DELETE, headers=ADMIN, json={'ids': ids_of(client, 'x')})
  assert client.post('/api/auth/login',
                     json={'username': 'x', 'password': PW}).status_code == 401


def test_admin_cannot_delete_self(client):
  h = jwt_for(client, 'boss', 'admin')
  register(client, 'x')
  boss, x = ids_of(client, 'boss', 'x')
  body = client.post(DELETE, headers=h, json={'ids': [boss, x]}).get_json()
  assert body['changed'] == [x] and body['self_skipped'] == [boss]
  assert usernames(client) == ['boss']


def test_system_account_is_protected(client):
  """soarbot 은 보안 공지글 작성자 — 지우면 다음 자동 공지가 계정을 새로 만든다."""
  register(client, 'soarbot', 'x')
  sb, x = ids_of(client, 'soarbot', 'x')
  body = client.post(DELETE, headers=ADMIN, json={'ids': [sb, x]}).get_json()
  assert body['changed'] == [x] and body['protected'] == [sb]
  assert usernames(client) == ['soarbot']


def test_delete_records_audit_event(client):
  register(client, 'x')
  client.post(DELETE, headers=ADMIN, json={'ids': ids_of(client, 'x')})
  events = client.get('/api/security/events').get_json()['events']
  assert any(e['source'] == 'admin-console' and 'x' in (e['users'] or '')
             and '삭제' in e['reason'] for e in events)


def test_delete_unknown_ids_reported(client):
  register(client, 'x')
  [xid] = ids_of(client, 'x')
  body = client.post(DELETE, headers=ADMIN, json={'ids': [xid, 9999]}).get_json()
  assert body['changed'] == [xid] and body['not_found'] == [9999]


@pytest.mark.parametrize('payload', [{}, {'ids': []}, {'ids': 'x'}, {'ids': [True]},
                                     {'all': True}])
def test_delete_bad_payload_is_400(client, payload):
  register(client, 'x')
  assert client.post(DELETE, headers=ADMIN, json=payload).status_code == 400
  assert usernames(client) == ['x']


def test_delete_requires_admin(client):
  register(client, 'x')
  [xid] = ids_of(client, 'x')
  assert client.post(DELETE, json={'ids': [xid]}).status_code == 401
  assert client.post(DELETE, headers=jwt_for(client, 'plain'),
                     json={'ids': [xid]}).status_code in (401, 403)
  assert 'x' in usernames(client)
