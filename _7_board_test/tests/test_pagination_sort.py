"""목록 페이징·정렬 테스트 — [115] 대시보드 20개씩 보기 + 컬럼 헤더 정렬.

기존 목록 API 는 `limit` 하나뿐이라 화면이 50건을 한 번에 받아 그렸다. 기록이
쌓이면 표가 끝없이 길어지고, '오래된 것부터' 보거나 '심각도 높은 것부터' 보는
방법이 아예 없다. 그래서 서버가 `page·per_page·sort·order` 를 받고 **총 건수**를
함께 돌려준다(총 건수를 모르면 화면이 '마지막 페이지'를 그릴 수 없다).

여기서 특히 못 박아 두는 두 가지 — 둘 다 눈에 잘 안 띄는 버그다:
  1) `severity` 는 글자순(Critical<High<Low<Medium)이 아니라 **심각도 서열**
     (Critical>High>Medium>Low)로 정렬된다. 문자열 정렬에 맡기면 Low 가
     High 보다 위로 올라온다.
  2) `created_at` 이 똑같은 행이 여러 개여도 페이지 경계에서 행이 **겹치거나
     빠지지 않는다**. 정렬키가 동률이면 DB 가 순서를 보장하지 않으므로
     `id` 를 2차 정렬키로 붙여 고정한다.
"""
from datetime import datetime, timedelta

import pytest

from app import create_app
from extensions import db
from models import Incident, SecurityEvent

BASE = datetime(2026, 10, 1, 9, 0, 0)
SEVERITIES = ['Low', 'Medium', 'High', 'Critical']


@pytest.fixture
def app_client(tmp_path):
  """(app, test_client) 쌍 — 시딩은 app_context 안에서 직접 한다.

  조회 API 를 검사하는 테스트라 생성은 API 를 거치지 않는다. 그래야
  `created_at` 을 원하는 값으로 못 박아 정렬 결과를 단정할 수 있다.
  """
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
  yield application, application.test_client()
  with application.app_context():
    db.session.remove()
    db.engine.dispose()


def seed_incidents(application, n=25, same_time=False, student='lab'):
  """인시던트 n 건. created_at 은 1분 간격(같은 시각 테스트는 same_time=True)."""
  with application.app_context():
    for i in range(n):
      db.session.add(Incident(
          title=f'ticket {i}',
          src_ip=f'203.0.113.{i + 1}',
          severity=SEVERITIES[i % 4],
          status='open' if i % 2 == 0 else 'closed',
          event_count=i,
          student=student,
          created_at=BASE if same_time else BASE + timedelta(minutes=i)))
    db.session.commit()


def seed_events(application, n=25, student='lab'):
  """보안 이벤트 n 건. decision 은 번갈아, severity 는 4종 순환."""
  with application.app_context():
    for i in range(n):
      db.session.add(SecurityEvent(
          student=student,
          src_ip=f'198.51.100.{i + 1}',
          fail_count=i,
          decision='deny' if i % 2 == 0 else 'allow',
          severity=SEVERITIES[i % 4],
          reason=f'seed {i}',
          created_at=BASE + timedelta(minutes=i)))
    db.session.commit()


def get(client, path):
  res = client.get(path)
  assert res.status_code == 200, res.get_data(as_text=True)
  return res.get_json()


# ─────────────────────────── 페이징 ───────────────────────────

def test_default_page_size_is_20(app_client):
  """기본 한 페이지 20건 — 25건을 넣으면 1페이지에 20건만 온다."""
  app, client = app_client
  seed_incidents(app, 25)

  body = get(client, '/api/security/incidents')
  assert len(body['incidents']) == 20
  assert body['count'] == 20          # 기존 키(현재 페이지 건수) 유지
  assert body['page'] == 1
  assert body['per_page'] == 20
  assert body['total'] == 25          # 총 건수를 알려줘야 마지막 페이지를 그린다
  assert body['total_pages'] == 2


def test_last_page_has_remainder(app_client):
  """마지막 페이지는 남은 5건만."""
  app, client = app_client
  seed_incidents(app, 25)

  body = get(client, '/api/security/incidents?page=2')
  assert len(body['incidents']) == 5
  assert body['page'] == 2
  assert body['total'] == 25


def test_page_beyond_last_is_empty_but_200(app_client):
  """범위를 넘은 페이지는 빈 목록 — 화면이 에러로 깨지지 않게."""
  app, client = app_client
  seed_incidents(app, 25)

  body = get(client, '/api/security/incidents?page=99')
  assert body['incidents'] == []
  assert body['total'] == 25


def test_empty_table_reports_one_page(app_client):
  """기록이 0건이어도 total_pages 는 1 — '1 / 0 페이지' 같은 표시를 막는다."""
  app, client = app_client

  body = get(client, '/api/security/incidents')
  assert body['total'] == 0
  assert body['total_pages'] == 1
  assert body['incidents'] == []


def test_per_page_capped_at_100(app_client):
  """per_page 상한 100 — 큰 값을 넣어 DB 를 통째로 긁어가지 못한다."""
  app, client = app_client
  seed_incidents(app, 25)

  body = get(client, '/api/security/incidents?per_page=500')
  assert body['per_page'] == 100


def test_page_zero_or_negative_falls_back_to_first(app_client):
  """page=0 · page=-3 은 1페이지로 보정(400 대신 안전한 기본값)."""
  app, client = app_client
  seed_incidents(app, 25)

  for bad in ('0', '-3', 'abc'):
    body = get(client, f'/api/security/incidents?page={bad}')
    assert body['page'] == 1, bad


def test_legacy_limit_still_works(app_client):
  """기존 화면·테스트가 쓰던 limit 호환 — limit=2 면 2건."""
  app, client = app_client
  seed_incidents(app, 25)

  body = get(client, '/api/security/incidents?limit=2')
  assert body['count'] == 2
  assert body['per_page'] == 2


# ─────────────────────────── 정렬 ───────────────────────────

def test_created_at_desc_is_default(app_client):
  """기본 정렬은 생성시간 내림차순(최신 먼저)."""
  app, client = app_client
  seed_incidents(app, 5)

  body = get(client, '/api/security/incidents')
  times = [t['created_at'] for t in body['incidents']]
  assert times == sorted(times, reverse=True)
  assert body['sort'] == 'created_at'
  assert body['order'] == 'desc'


def test_created_at_asc(app_client):
  """오름차순 — 가장 오래된 것이 먼저."""
  app, client = app_client
  seed_incidents(app, 5)

  body = get(client, '/api/security/incidents?sort=created_at&order=asc')
  times = [t['created_at'] for t in body['incidents']]
  assert times == sorted(times)
  assert body['order'] == 'asc'


def test_severity_sorted_by_rank_not_alphabet(app_client):
  """심각도는 글자순이 아니라 서열 — desc 면 Critical 이 맨 위, Low 가 맨 아래.

  글자순이면 Critical < High < Low < Medium 이므로 desc 에서 Medium 이
  1위가 되고 Critical 이 꼴찌가 된다. 그 오답을 여기서 잡는다.
  """
  app, client = app_client
  seed_incidents(app, 8)       # 4종 심각도 x 2건

  desc = get(client, '/api/security/incidents?sort=severity&order=desc')
  assert [t['severity'] for t in desc['incidents']][:2] == ['Critical', 'Critical']
  assert [t['severity'] for t in desc['incidents']][-2:] == ['Low', 'Low']

  asc = get(client, '/api/security/incidents?sort=severity&order=asc')
  assert [t['severity'] for t in asc['incidents']][:2] == ['Low', 'Low']
  assert [t['severity'] for t in asc['incidents']][-2:] == ['Critical', 'Critical']


def test_sort_by_event_count(app_client):
  """숫자 컬럼 정렬 — 관련 이벤트 많은 티켓부터."""
  app, client = app_client
  seed_incidents(app, 10)

  body = get(client, '/api/security/incidents?sort=event_count&order=desc')
  counts = [t['event_count'] for t in body['incidents']]
  assert counts == sorted(counts, reverse=True)


def test_invalid_sort_returns_400(app_client):
  """허용 목록에 없는 컬럼은 400 — 조용히 기본 정렬로 넘기지 않는다.

  오타(sort=createdat)를 400 으로 돌려주면 화면 개발 중에 바로 드러난다.
  임의 컬럼명을 그대로 ORDER BY 에 넣지 않는다는 뜻도 된다.
  """
  app, client = app_client
  seed_incidents(app, 3)

  res = client.get('/api/security/incidents?sort=password')
  assert res.status_code == 400
  assert 'sort' in res.get_json()['msg']


def test_invalid_order_returns_400(app_client):
  app, client = app_client
  seed_incidents(app, 3)

  res = client.get('/api/security/incidents?order=sideways')
  assert res.status_code == 400


def test_pages_do_not_overlap_when_created_at_identical(app_client):
  """★ 생성시간이 전부 같아도 페이지 1+2 가 25건을 정확히 덮는다.

  정렬키가 동률일 때 DB 는 순서를 보장하지 않는다. 그러면 같은 행이 1·2페이지에
  두 번 나오고 다른 행은 아예 안 보인다. id 2차 정렬키로 순서를 고정해야 한다.
  """
  app, client = app_client
  seed_incidents(app, 25, same_time=True)

  p1 = get(client, '/api/security/incidents?sort=created_at&order=desc&page=1')
  p2 = get(client, '/api/security/incidents?sort=created_at&order=desc&page=2')
  ids = [t['id'] for t in p1['incidents']] + [t['id'] for t in p2['incidents']]

  assert len(ids) == 25
  assert len(set(ids)) == 25          # 중복 없음
  assert set(ids) == set(range(1, 26))  # 누락 없음


def test_severity_sort_is_also_stable_across_pages(app_client):
  """동률이 많은 심각도 정렬에서도 페이지 경계가 안전해야 한다."""
  app, client = app_client
  seed_incidents(app, 25)            # 심각도 4종이 6~7건씩 동률

  p1 = get(client, '/api/security/incidents?sort=severity&order=desc&page=1')
  p2 = get(client, '/api/security/incidents?sort=severity&order=desc&page=2')
  ids = [t['id'] for t in p1['incidents']] + [t['id'] for t in p2['incidents']]
  assert len(set(ids)) == 25


# ─────────────────── 필터 + 정렬 + 페이징 조합 ───────────────────

def test_filter_narrows_total_not_just_page(app_client):
  """필터를 걸면 total 도 필터 기준으로 줄어야 한다(전체 건수를 쓰면 안 됨)."""
  app, client = app_client
  seed_incidents(app, 25)            # open 13건 / closed 12건

  body = get(client, '/api/security/incidents?status=open')
  assert body['total'] == 13
  assert body['total_pages'] == 1
  assert all(t['status'] == 'open' for t in body['incidents'])


def test_severity_filter(app_client):
  """심각도 필터 — 대시보드에서 Critical 만 보고 싶을 때."""
  app, client = app_client
  seed_incidents(app, 24)            # 4종 x 6건

  body = get(client, '/api/security/incidents?severity=Critical')
  assert body['total'] == 6
  assert all(t['severity'] == 'Critical' for t in body['incidents'])


def test_filter_sort_and_page_together(app_client):
  app, client = app_client
  seed_incidents(app, 25)

  body = get(client,
             '/api/security/incidents?status=closed&sort=created_at&order=asc'
             '&per_page=5&page=2')
  assert body['total'] == 12
  assert body['per_page'] == 5
  assert body['page'] == 2
  assert len(body['incidents']) == 5
  assert all(t['status'] == 'closed' for t in body['incidents'])
  times = [t['created_at'] for t in body['incidents']]
  assert times == sorted(times)


# ─────────────────── 최근 이벤트 쪽도 같은 규칙 ───────────────────

def test_events_paging(app_client):
  app, client = app_client
  seed_events(app, 25)

  body = get(client, '/api/security/events')
  assert len(body['events']) == 20
  assert body['count'] == 20          # 기존 키 유지
  assert body['total'] == 25
  assert body['total_pages'] == 2

  page2 = get(client, '/api/security/events?page=2')
  assert len(page2['events']) == 5


def test_events_sort_by_fail_count_and_severity(app_client):
  app, client = app_client
  seed_events(app, 12)

  by_fail = get(client, '/api/security/events?sort=fail_count&order=desc')
  fails = [e['fail_count'] for e in by_fail['events']]
  assert fails == sorted(fails, reverse=True)

  by_sev = get(client, '/api/security/events?sort=severity&order=desc')
  assert by_sev['events'][0]['severity'] == 'Critical'


def test_events_decision_filter_with_total(app_client):
  app, client = app_client
  seed_events(app, 25)               # deny 13 / allow 12

  body = get(client, '/api/security/events?decision=deny')
  assert body['total'] == 13
  assert all(e['decision'] == 'deny' for e in body['events'])


def test_events_legacy_limit_still_works(app_client):
  """기존 화면이 쓰던 limit=50 호환 — 50 은 상한 100 안이라 그대로."""
  app, client = app_client
  seed_events(app, 25)

  body = get(client, '/api/security/events?limit=50')
  assert body['count'] == 25
  assert body['per_page'] == 50


def test_events_invalid_sort_returns_400(app_client):
  app, client = app_client
  seed_events(app, 3)

  res = client.get('/api/security/events?sort=password')
  assert res.status_code == 400


# ─────────────────── 화면에 실제로 붙어 있는가 ───────────────────

def test_dashboard_page_has_pager_and_sortable_headers(app_client):
  """★ API 만 고치고 템플릿을 안 고치면 '기능은 되는데 화면엔 안 보이는' 상태가
  된다. 페이저 자리·정렬 머리글·심각도 필터가 HTML 에 실제로 박혀 있는지 본다.
  """
  app, client = app_client
  res = client.get('/dashboard')
  assert res.status_code == 200
  html = res.get_data(as_text=True)

  # 공용 함수 partial 이 include 됐는가
  for fn in ('function renderPager', 'function bindSortHeaders',
             'function paintSortHeaders', 'function tableQuery'):
    assert fn in html, fn

  # 두 표가 각자 페이저 자리를 갖고 있는가
  assert 'id="incident-pager"' in html
  assert 'id="event-pager"' in html

  # 머리글 클릭 정렬이 연결될 thead 와 정렬 컬럼
  assert 'id="incident-head"' in html
  assert 'id="event-head"' in html
  for col in ('created_at', 'severity', 'src_ip', 'id'):
    assert f'data-sort="{col}"' in html, col

  # 심각도 필터 드롭다운(두 표 각각)
  assert 'id="inc-severity"' in html
  assert 'id="ev-severity"' in html


def test_dashboard_sort_columns_match_server_whitelist(app_client):
  """화면이 쓰는 data-sort 값이 서버 허용 목록 안에 있는가.

  하나라도 벗어나면 그 머리글을 누르는 순간 400 이 되어 표가 빈다.
  """
  import re

  from controllers.security_controller import _EVENT_SORTS, _INCIDENT_SORTS

  app, client = app_client
  html = client.get('/dashboard').get_data(as_text=True)
  used = set(re.findall(r'data-sort="([^"]+)"', html))

  allowed = set(_EVENT_SORTS) | set(_INCIDENT_SORTS)
  assert used, '정렬 가능한 머리글이 하나도 없다'
  assert used <= allowed, f'서버가 모르는 정렬 컬럼: {used - allowed}'
