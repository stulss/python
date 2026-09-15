#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""[주석·설명용 사본] 자동 권한 회수봇 — privilege_revoke_bot.py

이 파일은 원본 privilege_revoke_bot.py 를 복사해 주석만 덧붙인 학습용 사본이다.
  · 실행 코드는 원본과 똑같다(주석과 이 설명 문자열만 추가).
  · 원본을 고쳐도 이 사본에는 반영되지 않는다. 실제 운영(작업 스케줄러)은 원본을 쓴다.

==============================================================================
0. 한 줄 요약
==============================================================================
  "admin 권한을 가지면 안 되는 계정이 admin 을 갖고 있는지 매시간 검사해서,
   발견하면 보안 로그 서버(Graylog)에 경보를 보내는 순찰 프로그램"

==============================================================================
1. 쉬운 비유 — 회사 건물의 '마스터키'
==============================================================================
  게시판(Flask 앱)           = 회사 건물
  admin 권한                 = 모든 문을 여는 마스터키
  ADMIN_ALLOWLIST(허용목록)  = 인사팀이 정한 "마스터키를 가져도 되는 사람" 명단
  이 봇                      = 매시간 순찰 도는 경비원
  X-API-Key                  = 경비원이 관리실 장부를 볼 때 보여주는 출입증
  Graylog                    = 보안관제실(보고를 받아 기록하고 경보를 울림)
  GELF 메시지                = 정해진 양식의 무전 보고
  n8n                        = 출동해서 실제로 키를 회수하는 보안팀

  경비원(봇)은 관리실 장부에서 '마스터키 소지자'만 뽑아 인사팀 명단과 대조한다.
  명단에 없는 사람이 키를 갖고 있으면 관제실(Graylog)에 무전을 친다.
  키를 실제로 빼앗는 건 보안팀(n8n)의 일이다 — 경비원은 '발견·보고'만 한다.
    --dry-run : 순찰만 돌고 무전은 치지 않는다(연습)
    --revoke  : 무전도 치고, 보안팀을 기다리지 않고 경비원이 직접 키까지 회수한다(대체 경로)

==============================================================================
2. 기본 개념
==============================================================================
  ■ 인증(Authentication) vs 인가(Authorization)
      인증 = "너 누구야?"          (로그인)     → 실패하면 401
      인가 = "너 이거 해도 돼?"    (권한 확인)  → 실패하면 403
      이 봇이 감시하는 건 '인가' 쪽 문제다: 로그인은 정상인데 권한이 너무 많은 경우.

  ■ RBAC(Role-Based Access Control, 역할 기반 접근제어)
      사람마다 권한을 따로 주지 않고 '역할(role)'에 권한을 묶어 둔다.
      이 게시판의 역할은 계단식이다:  user(1) < gold(2) < admin(3)   (models/user.py)

  ■ 최소권한 원칙(Principle of Least Privilege)
      "일에 필요한 만큼만 권한을 준다." 필요 없는 admin = 과잉권한 = 사고의 씨앗.
      계정이 털리면 공격자는 그 계정의 권한을 그대로 손에 넣기 때문이다.

  ■ 허용목록(Allowlist)
      "명단에 있는 것만 허용, 나머지는 전부 위반" 방식.
      반대인 차단목록(Blocklist, "명단에 있는 것만 막는다")보다 새는 곳이 적다.
      → 허용목록이 비어 있으면 모든 admin 이 위반으로 잡힌다(안전한 쪽으로 실패).

  ■ API 키 (X-API-Key 헤더)
      사람은 로그인(JWT 토큰)으로 들어오지만, 프로그램(봇·n8n)은 미리 나눠 가진
      비밀 문자열을 HTTP 헤더에 실어 보내 자신을 증명한다.
      서버는 설정된 키가 비어 있으면 무조건 거절한다(fail-closed, config.py).

  ■ SIEM / Graylog
      여러 곳의 로그를 한곳에 모아 검색하고 경보를 거는 시스템. Graylog 는 그중 하나.

  ■ GELF(Graylog Extended Log Format)
      Graylog 가 받는 JSON 로그 양식.
        필수 필드     : version, host, short_message
        사용자 정의   : 이름 앞에 밑줄(_) → Graylog 에서는 밑줄을 뗀 이름으로 보인다
                        (_rule → rule, _user → user).  단 _id 는 쓸 수 없다.
        level         : syslog 심각도 숫자(0 긴급 ~ 7 디버그). 4 = Warning(경고)

  ■ UDP
      "보내고 끝" 방식의 전송 — 우편함에 편지를 넣고 돌아서는 것. 받았는지 확인하지 않는다.
      빠르고 단순하지만, Graylog 가 꺼져 있어도 보내는 쪽에서는 에러가 나지 않는다.
      (HTTP 가 쓰는 TCP 는 전화 통화 — 상대가 안 받으면 바로 안다)

  ■ SOAR / n8n
      SOAR = 보안 경보에 대한 '대응'을 자동화하는 것. 여기서는 n8n 이 맡는다:
      Graylog 이벤트 → n8n 워크플로우 → POST /api/admin/revoke (실제 회수).

  ■ 탐지와 대응의 분리
      봇은 '탐지·신고'만, 회수는 n8n 이 한다. 역할을 나누면
        · 봇은 읽기 + 보고만 하므로 단순해지고,
        · 실제로 권한을 바꾸는 '쓰기' 동작이 한곳(n8n)에 모이며,
        · 모든 경보가 Graylog 에 남아 나중에 추적할 수 있다.

  ■ 감사기록(Audit trail)
      "누가·언제·왜" 권한을 바꿨는지 남기는 기록.
      users 테이블의 role_granted_by / role_granted_at / role_reason,
      회수가 일어나면 security_events 테이블(대시보드에 표시).

==============================================================================
3. 동작 원리 — 전체 흐름
==============================================================================

   윈도우 작업 스케줄러 (매시간)
        │  python privilege_revoke_bot.py
        ▼
   [회수봇] ──① GET /api/admin/users?role=admin  (헤더 X-API-Key)──▶ [게시판 Flask + MySQL]
   [회수봇] ◀── {"count": 2, "users": [{"username": "kim", "role": "admin", ...}, ...]}
        │
        │ ② admin 목록 중 허용목록(ADMIN_ALLOWLIST)에 없는 계정 = 위반
        │
        │ ③ 위반 1건 = GELF 메시지 1개 → UDP 12201 로 전송
        ▼
   [Graylog] ──④ 이벤트 규칙(rule=priv-unauthorized-admin) 발동──▶ [n8n]
                                                                      │
   [게시판] ◀──⑤ POST /api/admin/revoke {username, reason, ...}───────┘
       role: admin → user  +  security_events 에 감사기록

   · --dry-run : ①② 만 하고 끝 (③④⑤ 없음)
   · --revoke  : ③ 직후 봇이 ⑤를 직접 호출 (n8n 없이도 회수)

==============================================================================
4. 실행 방법과 출력 예시
==============================================================================
    python privilege_revoke_bot.py              # 탐지 + Graylog 신고
    python privilege_revoke_bot.py --dry-run    # 신고 없이 위반만 출력(연습용)
    python privilege_revoke_bot.py --revoke     # 신고 + 게시판 API 로 직접 회수
    python privilege_revoke_bot.py --help       # 옵션 도움말

  이 사본을 직접 돌릴 때는 파일 이름에 공백이 있으므로 따옴표로 감싼다:
    python "privilege_revoke_bot copy-주석설명용.py" --dry-run

  출력 예시 — 허용목록 = lsy 인데 lsy 가 kim 에게 admin 을 준 상황
    [!] 과잉권한 admin 1건 탐지: kim
        - kim → Graylog 신고(rule=priv-unauthorized-admin)
    --revoke 를 붙였다면 한 줄이 더 나온다:
          회수: admin→user (event 17)
    --dry-run 이었다면:
        - kim (부여자 lsy) [dry-run]

  위반이 없으면
    [OK] 과잉권한 위반 없음 (허용목록: ['lsy'])

==============================================================================
5. 종료 코드 — 작업 스케줄러 '마지막 실행 결과'에 찍히는 숫자
==============================================================================
  0 : 정상 종료 (위반 없음, 또는 신고까지 마침)
  1 : 게시판 조회 실패 (서버 꺼짐, 키 불일치로 401, 10초 시간초과 등)
  2 : 설정 오류 (.env 에 API 키가 없음). 알 수 없는 옵션을 줘도 argparse 가 2 로 끝낸다.
  ※ 신고 단계(Graylog 주소를 못 찾음)나 --revoke 회수 호출에서 난 예외는 따로 잡지 않는다.
    이때는 Traceback(에러 추적 메시지)과 함께 1 로 끝나고, 남은 위반 계정은 처리되지 않는다.

==============================================================================
6. .env 예시 (값은 가짜 — 실제 키를 여기나 깃에 적지 말 것)
==============================================================================
  게시판(config.py)과 같은 폴더의 .env 를 함께 읽으므로 한 파일로 서버·봇 설정이 맞춰진다.

    BOARD_URL=http://localhost:5000
    ADMIN_API_KEY=<게시판과 같은 관리자 키>
    ADMIN_ALLOWLIST=lsy,instructor
    GRAYLOG_HOST=localhost
    GRAYLOG_PORT=12201
    STUDENT=lsy
    BOARD_SRC_IP=127.0.0.1

==============================================================================
7. 자주 걸리는 함정
==============================================================================
  ① 허용목록이 비어 있으면 모든 admin 이 위반이다.
     그 상태로 --revoke 를 돌리면 강사·본인 계정의 admin 까지 전부 user 로 내려간다.
     (API 키로는 여전히 POST /api/admin/grant 를 호출할 수 있어 복구는 가능하다)
  ② UDP 는 '보내고 끝'이라 Graylog 가 꺼져 있어도 "Graylog 신고" 가 출력된다.
     출력만 믿지 말고 Graylog 검색창에서  rule:priv-unauthorized-admin  으로 도착을 확인한다.
     Graylog 에 GELF UDP 입력(포트 12201)이 만들어져 있어야 받는다.
  ③ .env 값에 따옴표를 쓰지 않는다.  ADMIN_API_KEY="abc" 라고 쓰면 이 봇은 따옴표까지 값으로 읽는다.
     게시판이 쓰는 python-dotenv 는 따옴표를 떼므로 서로 키가 달라져 401 이 난다.
  ④ 같은 이름의 환경변수가 이미 있으면 .env 보다 환경변수가 이긴다(setdefault).
  ⑤ --dry-run 과 --revoke 를 같이 주면 dry-run 이 먼저 걸려 신고도 회수도 하지 않는다.
  ⑥ --revoke 와 n8n 을 함께 쓰면 먼저 도착한 쪽만 실제로 회수하고,
     나중 호출은 "이미 user(회수 불필요)" 응답을 받는다(감사기록은 1건만 남는다).
"""

# ─────────────────────────────────────────────────────────────────────────────
# import — 모두 파이썬 표준 라이브러리. pip install 없이 어느 PC 에서나 돈다.
#   작업 스케줄러로 돌리는 봇은 가상환경·패키지가 꼬이면 아무도 모르게 멈추기 쉽다.
#   외부 패키지를 안 쓰면 그 위험 자체가 없다.
# ─────────────────────────────────────────────────────────────────────────────
import argparse          # 명령줄 옵션(--dry-run, --revoke) 해석
import json              # 파이썬 dict ⇄ JSON 문자열 변환
import os                # 환경변수(os.environ), 파일 경로 다루기
import socket            # UDP 로 Graylog 에 메시지 보내기, 내 PC 이름 알아내기
import sys               # sys.exit(종료 코드)
import urllib.request    # HTTP 요청 (requests 라이브러리 대신 쓰는 표준 모듈)

# 이 파일이 놓인 폴더의 절대경로.
# 작업 스케줄러는 '시작 위치'를 따로 안 정하면 C:\Windows\System32 같은 엉뚱한 폴더에서 실행한다.
# 그래서 현재 작업 폴더(cwd)가 아니라 "파일이 있는 곳" 기준으로 .env 를 찾는다.
HERE = os.path.dirname(os.path.abspath(__file__))


# ═════════════════════════════════════════════════════════════════════════════
# load_env() — .env 파일을 읽어 환경변수로 올린다
# ─────────────────────────────────────────────────────────────────────────────
# 비유: 서랍 속 메모지(.env)를 꺼내 책상 위(os.environ)에 펼쳐 두는 일.
#       책상에 이미 같은 이름의 메모가 있으면 그걸 그대로 둔다(setdefault).
#
# 왜 직접 만들었나?  python-dotenv 를 쓰면 한 줄이지만 설치가 필요하다.
#                   이 봇은 '표준 라이브러리만' 쓰기로 했으므로 몇 줄로 흉내 냈다.
#
# .env 한 줄의 모양:  KEY=VALUE     (# 로 시작하면 주석, 빈 줄은 무시)
# ═════════════════════════════════════════════════════════════════════════════
def load_env():
  """같은 폴더 .env 를 읽어 os.environ 에 채운다(이미 있으면 유지). 의존성 없음."""
  # 예) E:\0-Aleph-Python-Test\Python-Lab-ALeph-T\_7_board_test\.env
  path = os.path.join(HERE, '.env')
  # .env 가 없어도 에러를 내지 않는다 → 그때는 이미 설정된 환경변수만 쓴다
  if os.path.exists(path):
    # encoding='utf-8' : 한글 주석이 들어 있어도 깨지지 않게
    with open(path, encoding='utf-8') as f:
      for line in f:
        # 앞뒤 공백과 줄바꿈 문자(\n) 제거
        line = line.strip()
        # 빈 줄 / 주석(#) / '=' 가 없는 줄은 건너뛴다
        if not line or line.startswith('#') or '=' not in line:
          continue
        # split('=', 1) : 첫 번째 '=' 에서만 자른다
        #   "KEY=ab==" → ['KEY', 'ab=='] 처럼 값 안에 '=' 가 있어도 안전
        k, v = line.split('=', 1)
        # 이미 같은 이름이 있으면 덮어쓰지 않는다 → 실제 환경변수가 .env 보다 우선
        # (주의: 따옴표는 떼지 않는다. KEY="abc" 면 값이 "abc" 따옴표 포함)
        os.environ.setdefault(k.strip(), v.strip())


# ═════════════════════════════════════════════════════════════════════════════
# cfg() — 설정값을 dict 하나로 모은다
# ─────────────────────────────────────────────────────────────────────────────
# 비유: 순찰 나가기 전에 챙기는 '준비물 가방'.
#       어디로 갈지(board), 출입증(key), 명단(allow), 무전 주파수(graylog_host/port)...
#       뒤의 함수들은 환경변수를 직접 뒤지지 않고 이 가방(c)만 받아서 쓴다.
#
# os.environ.get('이름', '기본값') : 그 환경변수가 없으면 기본값을 돌려준다.
# ═════════════════════════════════════════════════════════════════════════════
def cfg():
  load_env()   # 먼저 .env → 환경변수로 올려 둔다
  # " lsy, instructor,," → ['lsy', 'instructor']
  #   split(',') 로 자르고 → 조각마다 공백 제거 → 빈 조각('')은 버린다.
  #   config.py 의 ADMIN_ALLOWLIST 와 똑같은 규칙이라 서버와 봇의 판정 기준이 같다.
  allow = [u.strip() for u in os.environ.get('ADMIN_ALLOWLIST', '').split(',') if u.strip()]
  return {
      # 게시판 주소. 끝의 '/' 를 떼 둬야 f"{board}/api/..." 가 '...5000//api' 가 되지 않는다.
      'board': os.environ.get('BOARD_URL', 'http://localhost:5000').rstrip('/'),
      # 관리자 API 키. ADMIN_API_KEY 가 비어 있으면 SECURITY_API_KEY 로 대체한다.
      #   config.py 도 같은 대체 규칙 → 키 하나만 설정해도 서버와 봇이 맞물린다.
      #   파이썬 or : 앞 값이 비어 있으면(거짓) 뒤 값을 돌려준다.  '' or 'abc' → 'abc'
      'key': os.environ.get('ADMIN_API_KEY', '') or os.environ.get('SECURITY_API_KEY', ''),
      # 허용목록(list)
      'allow': allow,
      # Graylog 주소
      'graylog_host': os.environ.get('GRAYLOG_HOST', 'localhost'),
      # 환경변수는 항상 문자열 → 포트 번호로 쓰려면 int 로 바꾼다. 12201 = GELF 기본 포트
      'graylog_port': int(os.environ.get('GRAYLOG_PORT', '12201')),
      # 실습자 이름 — 로그·감사기록에서 누구의 실습인지 구분
      'student': os.environ.get('STUDENT', 'lsy'),
      'src_ip': os.environ.get('BOARD_SRC_IP', '127.0.0.1'),  # 신고에 남길 대표 IP
  }


# ═════════════════════════════════════════════════════════════════════════════
# get_json() — HTTP 요청을 보내고, JSON 응답을 dict 로 돌려받는다
# ─────────────────────────────────────────────────────────────────────────────
# 비유: 관리실 창구에 출입증(X-API-Key)을 보여주고 서류를 요청하거나 제출하는 일.
#       GET  = "장부 좀 보여주세요"      (읽기)
#       POST = "이 서류 처리해 주세요"    (쓰기 — body 에 내용을 담는다)
#
# 이름은 get_json 이지만 method='POST' 로 쓰기 요청도 보낸다(회수 API 호출 때).
# 응답 코드가 400·401·404·500 같은 실패면 urllib 가 HTTPError 예외를 던진다.
#   → 부르는 쪽(main)이 try/except 로 받아서 처리한다.
# ═════════════════════════════════════════════════════════════════════════════
def get_json(url, key=None, method='GET', body=None):
  # body(dict) → JSON 문자열 → bytes. 네트워크로는 bytes 만 보낼 수 있다.
  #   (한글은 \uXXXX 형태로 바뀌어 가지만 서버가 다시 한글로 풀어 읽는다)
  # body 가 없으면(GET 요청) data=None
  data = json.dumps(body).encode() if body is not None else None
  # 요청서 작성 — 아직 보내지 않았다
  req = urllib.request.Request(url, data=data, method=method)
  # "보내는 내용물은 JSON 입니다"
  req.add_header('Content-Type', 'application/json')
  if key:
    # 출입증 제시. 서버의 admin_required 가 이 값을 ADMIN_API_KEY 와 비교한다
    req.add_header('X-API-Key', key)
  # 실제 전송. timeout=10 : 10초 안에 응답이 없으면 포기 → 봇이 영원히 멈춰 있지 않게.
  # with ... as r : 블록을 벗어나면 연결을 자동으로 닫는다.
  with urllib.request.urlopen(req, timeout=10) as r:
    # 응답 bytes → 문자열 → dict
    return json.loads(r.read().decode())


# ═════════════════════════════════════════════════════════════════════════════
# find_violations() — 위반자 찾기 (이 봇의 핵심 판정. 사실상 2줄)
# ─────────────────────────────────────────────────────────────────────────────
# 비유: 장부에서 '마스터키 소지자'만 뽑은 다음, 인사팀 명단과 한 명씩 대조.
#
#   게시판의 admin 목록 : [lsy, kim, park]
#   허용목록(allow)     : [lsy]
#   ───────────────────────────────────
#   위반 (반환값)       : [kim, park]     ← "admin 인데 명단에 없다"
#
# ?role=admin : 거르기는 서버(DB)에서 → admin 만 받아오니 전송량이 적다.
# 명단 대조는 봇 쪽(.env 의 ADMIN_ALLOWLIST)에서 한다.
#   참고: 서버에도 같은 계산을 해 주는 GET /api/admin/violations 가 있다.
# ═════════════════════════════════════════════════════════════════════════════
def find_violations(c):
  """허용목록 밖 admin 목록을 게시판에서 가져온다."""
  # 응답 예) {"count": 2,
  #          "users": [{"id": 3, "username": "kim", "role": "admin",
  #                     "role_granted_by": "lsy", "role_granted_at": "...", "role_reason": "..."},
  #                    ...]}
  d = get_json(f"{c['board']}/api/admin/users?role=admin", key=c['key'])
  # d.get('users', []) : 'users' 키가 없어도 에러 대신 빈 리스트
  # 리스트 내포 : users 중에서 username 이 허용목록에 '없는' 사람만 남긴다
  return [u for u in d.get('users', []) if u['username'] not in c['allow']]


# ═════════════════════════════════════════════════════════════════════════════
# send_gelf() — 위반 1건을 Graylog 에 보고 (무전)
# ─────────────────────────────────────────────────────────────────────────────
# 비유: 정해진 양식(GELF)의 보고서를 봉투에 넣어 관제실 우편함(UDP 12201)에 넣고 돌아선다.
#       잘 받았는지 확인 전화는 하지 않는다 → 빠르지만 '도착 보장'은 없다.
#
# 실제로 보내는 JSON 예)
#   {"version": "1.1", "host": "MY-PC",
#    "short_message": "privilege violation: 'kim' has unauthorized admin",
#    "level": 4, "_rule": "priv-unauthorized-admin", "_user": "kim",
#    "_granted_by": "lsy", "_src_ip": "127.0.0.1", "_student": "lsy", "_count": 1}
#
# Graylog 검색창에서는 밑줄을 뗀 필드 이름으로 찾는다:  rule:priv-unauthorized-admin
# ═════════════════════════════════════════════════════════════════════════════
def send_gelf(c, user):
  """위반 1건을 Graylog GELF(UDP 12201)로 신고."""
  msg = {
      # ── GELF 필수 필드 ──
      # 규격 버전(고정값) / 보낸 PC 이름("어느 경비원이 보고했나")
      'version': '1.1', 'host': socket.gethostname(),
      # 사람이 읽는 한 줄 요약 — Graylog 메시지 목록에 이 문장이 보인다
      'short_message': f"privilege violation: '{user['username']}' has unauthorized admin",
      # ── 심각도 ── syslog 기준: 0긴급 1경보 2치명 3오류 4경고 5알림 6정보 7디버그
      'level': 4,
      # ── 사용자 정의 필드 (이름 앞 '_') ── 검색·이벤트 조건·대응 단계의 입력값으로 쓰인다
      # 어떤 규칙을 어겼나 — Graylog 이벤트 규칙이 이 값으로 경보를 건다
      '_rule': 'priv-unauthorized-admin',
      # 과잉권한을 가진 계정 = 회수 대상
      '_user': user['username'],
      # 누가 admin 을 줬나(감사 추적). 기록이 없으면(None) 'unknown'
      '_granted_by': user.get('role_granted_by') or 'unknown',
      # 신고에 남길 대표 IP
      '_src_ip': c['src_ip'],
      # 실습자 이름
      '_student': c['student'],
      # 건수(숫자) — Graylog 에서 합계·횟수 조건을 걸기 좋게 숫자로 보낸다
      '_count': 1,
  }
  # dict → JSON 문자열 → bytes
  payload = json.dumps(msg).encode()
  # AF_INET = IPv4 주소 체계, SOCK_DGRAM = UDP(데이터그램). TCP 였다면 SOCK_STREAM.
  s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
  try:
    # UDP 는 연결(connect) 없이 "주소를 적어서 바로 던진다".
    # Graylog 프로그램이 꺼져 있어도 여기서는 에러가 나지 않는다.
    # (단, GRAYLOG_HOST 이름 자체를 찾을 수 없으면 socket.gaierror 예외)
    s.sendto(payload, (c['graylog_host'], c['graylog_port']))
  finally:
    # 전송 중 예외가 나도 소켓(운영체제 자원)은 반드시 반납한다
    s.close()


# ═════════════════════════════════════════════════════════════════════════════
# main() — 순찰 한 바퀴의 전체 순서
# ─────────────────────────────────────────────────────────────────────────────
#   1. 옵션 읽기          --dry-run / --revoke
#   2. 준비물 챙기기      cfg()              → API 키가 없으면 종료 코드 2
#   3. 장부 대조          find_violations()  → 조회에 실패하면 종료 코드 1
#   4. 위반이 없으면      [OK] 출력하고 끝 (종료 코드 0)
#   5. 위반 계정마다      dry-run 이면 출력만
#                         아니면 Graylog 신고 → (--revoke 면) 직접 회수까지
# ═════════════════════════════════════════════════════════════════════════════
def main():
  # argparse : 명령줄에 적은 글자들(sys.argv)을 해석해 args.dry_run / args.revoke 로 만들어 준다.
  # action='store_true' : 옵션을 적으면 True, 안 적으면 False (값을 따로 받지 않는 스위치)
  # '--dry-run' 의 '-' 는 속성 이름에서 '_' 로 바뀐다 → args.dry_run
  ap = argparse.ArgumentParser()
  ap.add_argument('--dry-run', action='store_true', help='신고 없이 위반만 출력')
  ap.add_argument('--revoke', action='store_true', help='게시판 API 로 직접 회수까지(대체 경로)')
  args = ap.parse_args()

  # 설정 가방 챙기기
  c = cfg()
  # 키가 없으면 어차피 서버가 401 로 막는다.
  # 네트워크까지 가지 말고 원인을 바로 알려준 뒤 끝낸다(빨리, 분명하게 실패).
  if not c['key']:
    print('[!] ADMIN_API_KEY(또는 SECURITY_API_KEY) 가 비어 있습니다. .env 확인.')
    sys.exit(2)   # 2 = 설정 오류

  # 게시판이 꺼져 있거나(연결 거부), 키가 틀리거나(401), 10초를 넘기면(timeout) 예외가 난다.
  # Exception 으로 넓게 받아 한 줄 메시지로 바꾸고 1 로 끝낸다.
  try:
    # 위반 계정(dict)들의 리스트
    bad = find_violations(c)
  except Exception as e:
    # 예) [!] 게시판 조회 실패: HTTP Error 401: UNAUTHORIZED
    print(f'[!] 게시판 조회 실패: {e}')
    sys.exit(1)   # 1 = 조회 실패

  # 빈 리스트는 거짓(False) → not bad 가 True 면 위반 없음
  if not bad:
    # 허용목록이 빈 리스트면 or 뒤의 안내 문구가 대신 찍힌다
    print(f"[OK] 과잉권한 위반 없음 (허용목록: {c['allow'] or '(비어있음=모든 admin이 위반)'})")
    return   # main 끝 → 종료 코드 0

  # 위반 요약 한 줄.  ', '.join(...) : ['kim', 'park'] → "kim, park"
  print(f"[!] 과잉권한 admin {len(bad)}건 탐지: " + ', '.join(u['username'] for u in bad))
  for u in bad:
    if args.dry_run:
      # 연습 모드: 누가 줬는지만 보여주고 다음 사람으로 넘어간다(신고·회수 모두 건너뜀)
      # --revoke 를 같이 줬어도 여기서 continue 되므로 회수하지 않는다
      print(f"    - {u['username']} (부여자 {u.get('role_granted_by')}) [dry-run]")
      continue
    # Graylog 신고 (흐름도의 ③)
    send_gelf(c, u)
    print(f"    - {u['username']} → Graylog 신고(rule=priv-unauthorized-admin)")
    if args.revoke:  # 대체: n8n 없이 봇이 직접 회수
      # POST /api/admin/revoke (흐름도의 ⑤를 봇이 직접)
      #   서버가 role 을 'user' 로 내리고 security_events 에 감사기록을 남긴다.
      #   source='privilege-guard-bot' : 서버 기본값 'privilege-guard'(n8n 경로)와 구분하는 꼬리표
      #   severity 는 보내지 않으므로 서버 기본값 'High' 로 기록된다.
      # 이 호출은 try 로 감싸지 않았다 → 실패하면 Traceback 과 함께 멈추고 남은 위반은 처리되지 않는다.
      r = get_json(f"{c['board']}/api/admin/revoke", key=c['key'], method='POST',
                   body={'username': u['username'], 'student': c['student'],
                         'reason': f"봇 직접 회수: 허용목록 밖 admin ({u['username']})",
                         'src_ip': c['src_ip'], 'source': 'privilege-guard-bot'})
      # 응답 예) {"msg": "권한 회수 완료", "old_role": "admin", "new_role": "user",
      #          "revoked": true, "event_id": 17, "revoked_by": "apikey"}
      # 이미 user 였다면 revoked=false 이고 event_id 가 없어 "(event None)" 으로 찍힌다
      print(f"      회수: {r.get('old_role')}→{r.get('new_role')} (event {r.get('event_id')})")


# ═════════════════════════════════════════════════════════════════════════════
# 진입점
# ─────────────────────────────────────────────────────────────────────────────
# "python 파일이름.py" 로 직접 실행할 때만 __name__ 이 '__main__' 이 되어 main() 이 돈다.
# 다른 파일(예: 테스트 코드)에서 import 하면 __name__ 이 모듈 이름이 되므로 main() 이 자동 실행되지 않는다.
#   → find_violations 같은 함수만 가져다 따로 시험해 볼 수 있다.
# ═════════════════════════════════════════════════════════════════════════════
if __name__ == '__main__':
  main()
