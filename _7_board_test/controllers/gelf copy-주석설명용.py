"""[주석·설명용 사본] controllers/gelf.py — 게시판이 보안 로그를 Graylog 로 직접 보내는 GELF 전송 헬퍼

이 파일은 원본 controllers/gelf.py 를 복사해 주석만 덧붙인 학습용 사본이다.
  · 실행 코드는 원본과 똑같다(주석과 이 설명 문자열만 추가).
  · 원본을 고쳐도 이 사본에는 반영되지 않는다.
  · 앱은 원본을 import 한다: controllers/auth_controller.py 의  from .gelf import send_gelf
    (이 사본 파일 이름에는 공백과 '-' 가 있어 import 문으로는 부를 수도 없다.)

==============================================================================
0. 한 줄 요약
==============================================================================
  "로그인 실패 같은 '앱 안에서만 보이는 사건'을 JSON 한 줄(GELF)로 만들어
   Graylog(SIEM)에 UDP 로 던지는 함수 하나. 보내다 실패해도 로그인은 멈추지 않는다."

  원본 설명 그대로:
    게시판(앱)이 보안 로그를 Graylog(SIEM)로 직접 보낸다.
    로그인 실패 같은 '앱 계층 사건'은 tcpdump 로 못 잡는다. 앱이 아는 사실(누가·어디서
    실패했나)을 GELF 한 줄로 SIEM 에 흘려보내면, 집계·탐지·대응은 Graylog+n8n 이 맡는다.
    GELF: JSON 한 줄, 커스텀 필드는 _ 접두사. UDP 12201(fire-and-forget).
    설정: GELF_HOST / GELF_PORT (config). 전송 실패는 로그인 흐름을 막지 않도록 조용히 무시.

==============================================================================
1. 쉬운 비유 — 회사 건물 1층 출입 게이트의 '무전기'
==============================================================================
  로그인 API(auth_controller)       = 건물 1층 출입 게이트
  send_gelf (이 파일)               = 게이트 옆에 달린 무전기
  Graylog                           = 보안관제실(보고를 모아 세고, 이상하면 경보)
  GELF 메시지                       = 정해진 양식의 무전 보고
  _rule = 'login-bruteforce'        = 보고 분류 코드("출입 실패 반복 의심")
  UDP                               = 응답 확인 없는 무전(말하고 끝)
  except Exception: pass            = 무전기가 고장 나도 게이트 업무는 계속한다
  n8n                               = 관제실 지시로 출동하는 보안팀
                                      (카드 정지 = POST /api/admin/lock, 출입 금지 = POST /api/admin/block)

  누군가 게이트에서 카드를 잘못 찍으면, 게이트 직원은 무전기로
  "kim 카드, 127.0.0.1 에서 실패 1회" 라고 '보고만' 한다.
  몇 번 틀렸는지 세고 "이건 공격이다" 라고 판단하는 건 관제실(Graylog)의 일이다.
  건물 밖 CCTV(tcpdump 같은 패킷 캡처)는 오가는 사람은 보지만
  '비밀번호가 틀렸다'는 판정은 못 본다 — 그 판정은 게이트 직원(앱) 안에서 내려지기 때문이다.

==============================================================================
2. 기본 개념 — 이 파일에 실제로 쓰인 것만
==============================================================================
  ■ SIEM / Graylog
      여러 곳의 로그를 한곳에 모아 검색·집계하고 조건이 맞으면 경보(이벤트)를 내는 시스템.
      이 프로젝트에서는 Graylog 가 그 역할이다.

  ■ 앱 계층 사건을 앱이 직접 보내는 이유
      네트워크 장비·패킷 캡처는 "어떤 요청이 오갔다"까지만 안다.
      "그 요청이 비밀번호 불일치로 판정됐다", "잠긴 계정에 로그인 시도했다"는
      앱 코드 안에서 결정되는 사실이다. 그래서 앱이 그 사실을 로그로 내보낸다.

  ■ GELF(Graylog Extended Log Format)
      Graylog 가 받는 JSON 로그 양식.
        필수 필드   : version, host, short_message
        level       : syslog 심각도 숫자(0 긴급 ~ 7 디버그). 이 파일은 항상 4 = Warning(경고)
        사용자 정의 : 이름 앞에 밑줄(_). Graylog 화면에서는 밑줄을 뗀 이름으로 보인다
                      (_rule → rule, _username → username). 단 _id 는 규격상 쓸 수 없다.

  ■ UDP 와 fire-and-forget
      UDP = 받았는지 확인하지 않는 전송. 우편함에 편지를 넣고 돌아서는 것과 같다.
      fire-and-forget = "쏘고 잊는다". 빠르고 로그인 응답을 기다리게 하지 않지만,
      Graylog 가 꺼져 있어도 보내는 쪽은 모른다. 12201 = GELF 기본 포트.

  ■ **fields (키워드 가변 인자)
      함수 정의의 **fields 는 "이름=값" 으로 넘어온 나머지 인자를 dict 하나로 모은다.
        send_gelf('요약', rule='login-bruteforce', username='kim', src_ip='127.0.0.1')
        → fields = {'username': 'kim', 'src_ip': '127.0.0.1'}
      그래서 부르는 쪽이 필드를 마음대로 늘려도 이 함수는 고칠 필요가 없다.

  ■ current_app
      Flask 가 "지금 요청을 처리 중인 앱"을 가리키도록 만들어 둔 대리 객체.
      app.py 의 app 객체를 직접 import 하지 않아도 설정(config)을 읽을 수 있다.
      (app.py 가 controllers 를 import 하므로, 반대로 controllers 가 app 을 import 하면 순환 import 가 된다.)
      요청 처리 중(또는 app_context 안)에서만 쓸 수 있고, 그 밖에서 쓰면 RuntimeError 가 난다.

  ■ try / finally 와 try / except
      finally      : 성공하든 예외가 나든 반드시 실행 → 소켓(운영체제 자원)을 꼭 닫는다.
      except: pass : 예외를 잡아서 아무것도 안 하고 넘어간다 → 전송 실패를 '삼킨다'.

  ■ fail-open(이 파일) vs fail-closed(API 키)
      관리자 API 키는 설정이 비면 '막는' 쪽으로 실패한다(fail-closed, config.py).
      이 파일은 반대로 전송이 실패해도 로그인은 '계속 열어 두는' 쪽을 골랐다(fail-open).
      로그 수집은 부가 기능이라 서비스 가용성이 더 중요하다는 판단이다.
      대가: 신고가 소리 없이 사라져도 아무도 모른다.

  ■ 탐지와 대응의 분리
      앱은 사건 1건마다 사실만 보고한다(_count 는 항상 1).
      집계(몇 번 실패했나)·탐지(이벤트 규칙)·대응(n8n → 관리자 API)은 모두 앱 밖에서 한다.
      models/user.py 주석: "로그인 실패가 임계 초과하면 n8n(SOAR)이 잠근다. 잠긴 계정은 로그인 거부(423)."

==============================================================================
3. 동작 원리 — 전체 흐름
==============================================================================

   POST /api/auth/login  (controllers/auth_controller.py 의 login)
     │
     ├─ ① 잠긴 계정(is_locked)이면
     │      send_gelf("login attempt on LOCKED account 'kim'",
     │                rule='login-bruteforce', username=..., src_ip=..., locked='1')
     │      → 응답 423
     │
     ├─ ② 없는 아이디 또는 비밀번호 불일치면
     │      send_gelf("failed login for 'kim' from 127.0.0.1",
     │                rule='login-bruteforce', username=... 또는 '(unknown)', src_ip=..., count=1)
     │      → 응답 401
     │
     └─ ③ 성공이면 신고하지 않는다 → 토큰 발급

   send_gelf 안에서 일어나는 일
     config 에서 GELF_HOST / GELF_PORT 읽기
       → dict 조립  version, host='board', short_message, level=4, _rule
       → fields 의 이름마다 앞에 '_' 를 붙여 추가
       → dict → JSON 문자열 → bytes
       → UDP 소켓 만들기 → sendto(주소로 바로 던지기) → 소켓 닫기
       → 도중에 난 예외는 전부 삼킨다. 반환값은 없음(None)

   이 파일 밖에서 이어지는 일
     [Graylog] 메시지 저장·집계 → 이벤트 규칙(Graylog 쪽 설정) 발동
       → [n8n] → POST /api/admin/lock {username} 또는 /api/admin/block {ip}  (헤더 X-API-Key)
     n8n 워크플로·Graylog 규칙 파일은 이 저장소에 없다(각자 도구에서 설정).

==============================================================================
4. 옵션 설명
==============================================================================
  4-1. send_gelf 인자

    인자            필수   설명
    short_message   예     사람이 읽는 한 줄 요약 → GELF short_message
    rule            예     _rule 값. Graylog 이벤트 필터의 키. 현재 호출값은 'login-bruteforce' 뿐
    **fields        아니오 이름=값 여러 개 → _이름 필드. 값은 JSON 으로 바꿀 수 있어야 한다
                           (문자열·숫자·True/False·None)
    반환값          -      없음(None). 성공했는지 실패했는지 알려주지 않는다

  4-2. 사용하는 설정(config) 값

    설정 키     config.py 에서 정하는 값                          이 파일의 기본값
    GELF_HOST   환경변수 GELF_HOST, 없으면 'localhost'            'localhost'
    GELF_PORT   int(환경변수 GELF_PORT, 없으면 '12201')           12201

    · "이 파일의 기본값"은 config 에 키 자체가 없을 때 쓰인다.
      예) tests/test_rbac.py 의 TestConfig 에는 GELF_HOST·GELF_PORT 가 없다 → localhost:12201.
    · .env.example 에는 GELF 항목이 없다. 적지 않으면 localhost:12201 로 보낸다.

  4-3. 실제로 나가는 GELF 필드

    필드            값                     어디서 오나
    version         '1.1'                  고정(GELF 규격 버전)
    host            'board'                고정(보낸 쪽 이름. 회수봇은 PC 이름을 쓴다)
    short_message   인자 short_message     호출하는 쪽
    level           4 (Warning)            고정
    _rule           인자 rule              'login-bruteforce'
    _username       fields['username']     auth_controller — 없는 아이디 실패는 '(unknown)' 일 수 있다
    _src_ip         fields['src_ip']       auth_controller — X-Forwarded-For 헤더 값, 없으면 remote_addr
    _count          1 (숫자)               ② 실패 신고 때만
    _locked         '1' (문자열)           ① 잠긴 계정 신고 때만

    Graylog 검색 예)  rule:login-bruteforce      username:kim

==============================================================================
5. 호출·메시지 예시
==============================================================================
  호출 (auth_controller 의 ② 경로와 같은 모양)
    send_gelf("failed login for 'kim' from 127.0.0.1",
              rule='login-bruteforce', username='kim', src_ip='127.0.0.1', count=1)

  UDP 12201 로 나가는 JSON 한 줄 (보기 좋게 줄을 나눴다 — 실제로는 한 줄)
    {"version": "1.1", "host": "board",
     "short_message": "failed login for 'kim' from 127.0.0.1",
     "level": 4, "_rule": "login-bruteforce",
     "_username": "kim", "_src_ip": "127.0.0.1", "_count": 1}

  잠긴 계정 신고 (① 경로)
    {"version": "1.1", "host": "board",
     "short_message": "login attempt on LOCKED account 'kim'",
     "level": 4, "_rule": "login-bruteforce",
     "_username": "kim", "_src_ip": "127.0.0.1", "_locked": "1"}

  필드 순서는 dict 에 넣은 순서 그대로다(json.dumps 는 정렬하지 않는다).
  Graylog 에 GELF UDP 입력(포트 12201)이 만들어져 있어야 받는다.

==============================================================================
6. 자주 걸리는 함정
==============================================================================
  ① "실패해도 예외를 올리지 않는다"는 소켓 부분(try 안)에만 해당한다.
     맨 앞 두 줄(current_app.config 읽기)은 try 밖이다. 요청 처리 밖(예: 파이썬 셸에서 직접 호출)에서
     부르면 RuntimeError 가 그대로 올라온다. 로그인 요청 안에서는 항상 앱 컨텍스트가 있어 문제없다.
  ② Graylog 가 꺼져 있어도, 포트가 틀려도, 호스트 이름을 못 찾아도 로그인은 정상 동작한다.
     대신 신고가 사라지고 화면·콘솔 어디에도 흔적이 없다(except: pass).
     도착 여부는 Graylog 검색창에서 rule:login-bruteforce 로 직접 확인한다.
  ③ JSON 으로 못 바꾸는 값(datetime 객체 등)을 fields 로 넘기면 json.dumps 가 TypeError 를 내고,
     그 예외도 삼켜져 경보 자체가 나가지 않는다. 문자열·숫자로 바꿔서 넘긴다.
  ④ 필드 이름을 id 로 주지 않는다. '_id' 가 되는데 GELF 규격상 _id 는 쓸 수 없다.
  ⑤ 값은 가공 없이 그대로 나간다. auth_controller 는 X-Forwarded-For 헤더 '전체'를 src_ip 로 넘긴다
     (그 파일 주석은 "remote_addr 를 쓴다"고 하지만 코드는 헤더가 있으면 헤더를 먼저 쓴다).
     "1.2.3.4, 10.0.0.1" 처럼 여러 값이 오면 그 문자열 그대로 신고되고, 이 값을 그대로
     /api/admin/block 에 넣으면 app.py 미들웨어(첫 값 1.2.3.4 로 비교)와 달라 차단이 먹지 않는다.
     또 이 헤더는 요청하는 쪽이 마음대로 위조할 수 있다.
  ⑥ _count 는 언제나 1이다. "5번 실패" 같은 누적은 앱이 세지 않고 Graylog 가 메시지 개수로 센다.
     users.failed_logins 는 화면 표시용 카운터이고 신고에는 실리지 않는다.
  ⑦ host 가 'board' 로 고정이고 auth_controller 는 student 필드를 싣지 않는다.
     여러 학생이 같은 Graylog 로 보내면 어느 게시판에서 온 신고인지 메시지만으로는 구분이 안 된다.
     (회수봇은 _student 필드를 따로 싣는다.)
"""

# ─────────────────────────────────────────────────────────────────────────────
# import — json·socket 은 파이썬 표준 라이브러리, flask 는 앱이 이미 쓰는 패키지.
#   GELF 전송에 graypy 같은 전용 라이브러리를 쓰지 않고 표준 모듈로 직접 만든다.
# ─────────────────────────────────────────────────────────────────────────────
# 파이썬 dict → JSON 문자열 변환
import json
# UDP 소켓으로 Graylog 에 바이트를 보낸다
import socket

# 지금 요청을 처리 중인 Flask 앱(설정 GELF_HOST / GELF_PORT 를 읽기 위해)
from flask import current_app


# ═════════════════════════════════════════════════════════════════════════════
# send_gelf() — 보안 사건 1건을 GELF 한 줄로 만들어 Graylog 에 UDP 로 던진다
# ─────────────────────────────────────────────────────────────────────────────
# 비유: 게이트 옆 무전기. 정해진 양식으로 "무슨 일이 있었다"만 말하고 끊는다.
#       관제실이 들었는지 확인하지 않고, 무전기가 고장 나도 게이트 업무는 계속한다.
#
# 입력: short_message(요약 문장), rule(분류 코드), **fields(추가 필드 이름=값)
# 출력: 없음(None) — 성공/실패를 돌려주지 않는다
#
# 누가 호출하나: controllers/auth_controller.py 의 login() 두 곳
#   ① 잠긴 계정에 로그인 시도   → rule='login-bruteforce', username, src_ip, locked='1'
#   ② 로그인 실패(아이디/비번)  → rule='login-bruteforce', username, src_ip, count=1
#
# 참고: privilege_revoke_bot.py 에도 같은 이름의 send_gelf 가 있지만 별개 함수다.
#       봇 쪽은 설정 dict 와 사용자 dict 를 받고, host 에 PC 이름을 넣으며, 예외를 삼키지 않는다.
# ═════════════════════════════════════════════════════════════════════════════
def send_gelf(short_message, rule, **fields):
  """GELF 경보를 Graylog 로 보낸다(실패해도 예외를 올리지 않는다).

  short_message: 사람이 읽는 요약,  rule: `_rule` 값(이벤트 필터 키),
  **fields: 그 외 커스텀 필드(자동으로 `_` 접두사가 붙는다). 예) username='lsy', src_ip='1.2.3.4'
  """
  # ── 1. 보낼 곳 정하기 ──
  # config.py 의 GELF_HOST(.env 의 GELF_HOST, 없으면 'localhost').
  # .get(키, 기본값) : config 에 키 자체가 없을 때(테스트용 TestConfig 등)도 에러 없이 기본값.
  # 주의: 이 두 줄은 아래 try 밖이다 → 앱 컨텍스트 밖에서 부르면 여기서 RuntimeError.
  host = current_app.config.get('GELF_HOST', 'localhost')
  # 포트는 숫자여야 sendto 에 쓸 수 있다. config.py 가 이미 int 로 바꿔 두지만 한 번 더 int().
  port = int(current_app.config.get('GELF_PORT', 12201))
  # ── 2. GELF 기본 필드 조립 ──
  # version       : GELF 규격 버전(고정 '1.1')
  # host          : 보낸 쪽 이름. 'board'(게시판)로 고정 — Graylog 의 source 로 보인다
  # short_message : Graylog 메시지 목록에 보이는 한 줄 요약
  # level         : syslog 심각도 0긴급 1경보 2치명 3오류 4경고 5알림 6정보 7디버그 → 4 경고
  # _rule         : 이벤트 규칙이 거르는 분류 코드. Graylog 검색은 밑줄을 뗀 rule:login-bruteforce
  msg = {'version': '1.1', 'host': 'board', 'short_message': short_message,
         'level': 4, '_rule': rule}
  # ── 3. 추가 필드에 '_' 접두사 붙이기 ──
  # username='kim' → msg['_username'] = 'kim',  count=1 → msg['_count'] = 1
  # GELF 규칙상 사용자 정의 필드는 반드시 '_' 로 시작해야 한다(안 붙이면 Graylog 가 무시할 수 있다).
  for k, v in fields.items():
    msg['_' + k] = v
  # ── 4. UDP 로 전송 — 무슨 일이 있어도 로그인 흐름을 막지 않는다 ──
  try:
    # AF_INET = IPv4 주소 체계, SOCK_DGRAM = UDP(데이터그램). TCP 였다면 SOCK_STREAM.
    # 호출할 때마다 소켓을 새로 만들고 바로 닫는다(실패 1건 = 패킷 1개).
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
      # dict → JSON 문자열 → bytes, 그리고 (주소, 포트)로 바로 던진다(연결 과정 없음).
      # json.dumps 기본값은 한글을 \uXXXX 형태로 바꿔 ASCII 로 보낸다 — Graylog 가 다시 한글로 푼다.
      # Graylog 가 꺼져 있어도 보통 여기서 에러가 나지 않는다(UDP 는 확인 응답이 없다).
      # 호스트 이름을 못 찾거나(socket.gaierror), JSON 으로 못 바꾸는 값이 있으면(TypeError) 예외.
      s.sendto(json.dumps(msg).encode(), (host, port))
    finally:
      # 전송이 성공하든 예외가 나든 소켓(운영체제 자원)은 반드시 반납한다
      s.close()
  # 위 try 안에서 난 모든 예외를 잡아 아무것도 하지 않는다(fail-open).
  # 결과: 신고는 사라지지만 로그인 API 는 원래 응답(401/423)을 정상적으로 돌려준다.
  except Exception:
    pass   # SIEM 이 꺼져 있어도 로그인 자체는 계속 동작해야 한다
