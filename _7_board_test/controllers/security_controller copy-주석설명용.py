"""[주석·설명용 사본] controllers/security_controller.py — 보안 이벤트 REST: n8n 이 판정 결과를 보내 저장하는 곳

이 파일은 원본 controllers/security_controller.py 를 복사해 주석만 덧붙인 학습용 사본이다.
  · 실행 코드는 원본과 똑같다(주석과 이 설명 문자열만 추가).
  · 원본을 고쳐도 이 사본에는 반영되지 않는다.
  · 앱은 원본을 import 한다(controllers/__init__.py 의 from .security_controller import security_bp).
    이 사본은 블루프린트로 등록되지 않는다. 파일 이름에 공백이 있어 import 문으로 부를 수도 없다.

원본 설명:  인증은 헤더 X-API-Key — 사람이 아니라 봇(n8n)이 부르므로 로그인 대신 공유 비밀 1개를 쓴다.

==============================================================================
0. 한 줄 요약
==============================================================================
  "n8n(자동화 봇)이 'IP 의 로그인 시도를 허용(allow)/거부(deny)했다'는 판정을 API 키와 함께 보내면
   security_events 표에 저장하고(거부 + 설정 ON 이면 게시판 '보안' 공지글도 자동 등록),
   보안 대시보드는 키 없이 목록·요약·학생 목록을 읽어 가는 API"

==============================================================================
1. 쉬운 비유 — 경비실 출입 기록부
==============================================================================
  n8n                          = 판정을 내리고 보고하는 경비원
  POST /api/security/events    = 경비실 기록부에 한 줄 적기
  X-API-Key                    = 기록부 자물쇠 비밀번호(경비원만 안다)
  require_api_key              = 그 자물쇠
  fail-closed                  = 비밀번호가 아직 정해지지 않았으면 자물쇠가 아예 안 열린다
  security_events 표           = 기록부
  decision = allow / deny      = "통과시킴 / 돌려보냄"
  AUTO_POST_ON_DENY            = "돌려보낸 건은 1층 게시판에도 공지" 스위치
  soarbot                      = 공지문 아래 적히는 '시스템' 명의
  GET 3종                      = 누구나 들여다볼 수 있는 기록 열람창(보안 대시보드)

  경비원(n8n)은 로그인 실패가 몰린 IP 를 보고 통과/돌려보냄을 판정한 뒤 기록부에 적으러 온다.
  기록부 자물쇠는 비밀번호가 맞아야 열리고, 비밀번호가 설정 안 됐으면 절대 안 열린다.
  '돌려보냄' 이고 공지 스위치가 켜져 있으면 soarbot 명의로 게시판에 공지도 붙인다.
  기록 열람은 수업 확인용이라 비밀번호 없이 누구나 할 수 있다.

==============================================================================
2. 기본 개념
==============================================================================
  ■ 보안 이벤트와 allow / deny
      "어떤 학생(student)의 실습 환경에서, 어떤 IP(src_ip)가, 몇 번 실패했고(fail_count),
       그래서 허용했나 거부했나(decision)" 를 한 줄로 남긴 기록.
      student 를 남기는 이유(models/security_event.py): 제출 증적에 본인 식별자가 찍혀 채점·표절 확인이 쉽다.

  ■ n8n 연동
      n8n 은 노코드 자동화 도구. 워크플로우의 HTTP 요청 단계가 이 API 를 부른다.
      도커 안의 n8n 에서는 http://host.docker.internal:5000 으로 이 앱에 닿는다(app.py 주석).
      이 폴더에는 n8n 워크플로우 파일이 없으므로, 실제로 어떤 필드를 채워 보내는지는 n8n 쪽 설정에 달렸다.
      이 API 가 받는 필드는 아래 4절 표가 전부다.

  ■ API 키 인증(X-API-Key)과 fail-closed
      사람은 로그인(JWT)으로, 봇은 미리 나눠 가진 비밀 문자열을 헤더에 실어 자신을 증명한다.
      fail-closed = 설정이 빠진 '실패 상황'에서 문을 닫는 쪽으로 동작.
        SECURITY_API_KEY 가 비어 있음      → 어떤 키를 보내도 401 (실수로 열어 두지 않는다)
        (반대인 fail-open 이었다면 키 설정을 잊는 순간 누구나 기록을 쓸 수 있다)

  ■ 데코레이터 직접 만들기 + functools.wraps
      require_api_key 는 "원래 함수(fn)를 받아, 검사 후 fn 을 부르는 wrapper 를 돌려주는" 함수다.
      @wraps(fn) 은 wrapper 에 원래 함수의 이름(__name__)·docstring 을 복사한다.
      Flask 는 함수 이름으로 엔드포인트 이름을 정하므로, wraps 가 없으면 이 데코레이터를 쓴 뷰가
      모두 'wrapper' 라는 같은 이름이 되어 두 번째 등록부터 충돌 에러가 난다.

  ■ HTTP 상태코드 (이 파일)
      201 Created(저장됨) / 200 OK(조회) / 400(필수값 누락·decision 값 오류) / 401(키 없음·틀림)
      + app.py 의 before_request 가 차단된 IP 에 403 을 먼저 돌려줄 수 있다.

  ■ 트랜잭션 — flush 와 commit
      db.session.add(obj)  : 변경 예약
      db.session.flush()   : 예약한 SQL 을 DB 에 보내되 '확정은 안 함' → 자동 증가 id 를 미리 받는다
      db.session.commit()  : 지금까지를 한꺼번에 확정
      이벤트 1건 + (필요하면) soarbot 계정 + 공지글을 commit 한 번으로 묶는다(한 트랜잭션).
      commit 전에 오류가 나면 아무것도 확정되지 않는다 — "이벤트만 저장되고 공지는 빠짐" 같은 반쪽 상태가 없다.

  ■ 집계 쿼리
      func.count(컬럼) = COUNT,  func.sum(컬럼) = SUM,  group_by = 묶어서 세기,
      distinct() = 중복 제거,   order_by(... .desc()) = 큰 순서.

  ■ 비밀번호 해시와 os.urandom
      generate_password_hash : 비밀번호를 되돌릴 수 없는 해시로 저장(평문 금지).
      os.urandom(16).hex()   : 운영체제가 만든 예측 불가능한 32글자 난수 문자열.
      soarbot 의 비밀번호를 '아무도 모르는 난수'로 만들어 사람이 그 계정으로 로그인하지 못하게 한다.

==============================================================================
3. 동작 원리
==============================================================================
  ■ 쓰기 — n8n 이 판정 결과를 보낼 때

   [n8n 워크플로우]
        │  POST /api/security/events   헤더 X-API-Key, 본문 JSON
        ▼
   app.py before_request (_block_ip_guard)
        │  요청 IP 가 blocked_ips 에 있으면 → 403 (여기서 끝)
        ▼
   @require_api_key
        │  SECURITY_API_KEY 가 비었거나 헤더 키가 다르면 → 401 (여기서 끝)
        ▼
   create_security_event()
        │ ① JSON 읽기 → student·src_ip·decision 검사 (빠졌거나 decision 이 allow/deny 아님 → 400)
        │ ② SecurityEvent 객체 생성 → add → flush (id 확보)
        │ ③ decision == 'deny' 이고 AUTO_POST_ON_DENY 가 켜져 있으면
        │       _create_security_post(ev)
        │         · soarbot 계정 찾기 → 없으면 난수 비밀번호로 새로 만들기(flush)
        │         · 카테고리 '보안' 공지글 Post 추가(flush) → 글 id 반환
        │ ④ commit (이벤트 + 계정 + 공지글을 한 번에 확정)
        ▼
   201 {"id": 이벤트 번호, "student": ..., "decision": ..., "post_id": 공지글 번호 또는 null}

  ■ 읽기 — 보안 대시보드(/dashboard, templates/dashboard.html)가 열릴 때

   dashboard.html JS
     · loadStudents() → GET /api/security/students                    → '학생' 드롭다운
     · loadSummary()  → GET /api/security/events/summary[?student=]    → 전체/거부/허용 카드, 거부 상위 IP 막대
     · loadEvents()   → GET /api/security/events?[student=&][decision=&]limit=50 → 최근 이벤트 표
   (새로고침 버튼·학생 선택·전체/거부/허용 버튼이 이 함수들을 다시 부른다)

  ■ 같은 표에 기록을 넣는 다른 곳 (controllers/admin_controller.py)
     권한 회수 /api/admin/revoke, 계정 잠금 /api/admin/lock, IP 차단 /api/admin/block 이 실제로 조치하면
     security_events 에 decision='deny' 기록을 남긴다(source 기본값: privilege-guard / login-guard / ip-guard).
     그래서 대시보드에는 이 파일로 들어온 기록과 관리자 조치 기록이 함께 보인다.

==============================================================================
4. 옵션 설명
==============================================================================
  ■ 엔드포인트  (모두 url_prefix /api/security. 차단된 IP 는 넷 다 403)
    | 메서드 | URL                           | 인증                          | 쿼리 파라미터                    | 응답 코드       |
    |--------|-------------------------------|-------------------------------|----------------------------------|-----------------|
    | POST   | /api/security/events          | X-API-Key == SECURITY_API_KEY | 없음(body 는 아래 표)             | 201 / 400 / 401 |
    | GET    | /api/security/events          | 없음                          | student, decision, limit          | 200             |
    | GET    | /api/security/events/summary  | 없음                          | student                           | 200             |
    | GET    | /api/security/students        | 없음                          | 없음                              | 200             |

  ■ POST body 필드 (JSON)
    | 필드          | 필수 | 기본값         | 서버가 하는 일                         | DB 컬럼(models/security_event.py) |
    |---------------|------|----------------|----------------------------------------|-----------------------------------|
    | student       | O    | -              | 앞뒤 공백 제거 후 50자까지 자름          | String(50) NOT NULL, index         |
    | src_ip        | O    | -              | 그대로(형식 검사 없음)                   | String(45) NOT NULL, index         |
    | decision      | O    | -              | 'allow' 또는 'deny' 만 허용(대소문자 구분) | String(10) NOT NULL                |
    | fail_count    | -    | 0              | int() 로 변환(없음·null·0·'' → 0)       | Integer NOT NULL                   |
    | severity      | -    | 'Low'          | 그대로(값 목록 검사 없음)                | String(10) NOT NULL                |
    | reason        | -    | null           | 그대로. 판정 사유                        | String(200)                        |
    | users         | -    | null           | 그대로. 시도된 계정들                    | String(255)                        |
    | last_seen     | -    | null           | 그대로(문자열). 마지막 시도 시각          | String(32)                         |
    | window_min    | -    | null           | 그대로. 집계 구간(분)                    | Integer                            |
    | source        | -    | 'login_guard'  | 그대로. 이벤트 출처                      | String(50)                         |
    | generated_at  | -    | null           | 그대로(문자열). 보낸 쪽이 만든 시각        | String(32)                         |
      created_at 은 body 로 받지 않는다 — DB 에 저장되는 순간 서버 시각(datetime.now)이 들어간다.
      대시보드 색: severity 가 High 면 빨강, Medium 이면 주황, 그 밖의 값은 회색.

  ■ POST 응답
    201 : {"id": 이벤트 번호, "student": 저장된 student(자른 값), "decision": ..., "post_id": 공지글 번호 또는 null}
    400 : {"msg": "student, src_ip, decision(allow|deny) 은 필수입니다."}
    401 : {"msg": "API 키가 없거나 잘못되었습니다."}

  ■ GET /api/security/events 쿼리
    | 이름      | 기본값 | 뜻                                     | 비고                                  |
    |-----------|--------|----------------------------------------|---------------------------------------|
    | student   | 없음   | 그 학생 것만(정확히 일치)                | 없으면 전체                            |
    | decision  | 없음   | allow 또는 deny 만                      | 다른 값은 무시(= 전체)                  |
    | limit     | 20     | 최신 id 순으로 몇 건                     | 최대 100 으로 자름. 숫자 아니면 20     |
    응답: {"count": 건수, "events": [SecurityEvent.to_dict(), ...]}
      to_dict() = id, student, src_ip, fail_count, decision, severity, reason, users,
                  last_seen, window_min, source, generated_at, created_at(ISO 문자열 또는 null)

  ■ GET /api/security/events/summary 쿼리
    | 이름     | 기본값 | 뜻                   |
    |----------|--------|----------------------|
    | student  | 없음   | 그 학생 기록만 집계    |
    응답: {"student": 값 또는 null,
           "by_decision": {"allow": 건수, "deny": 건수}   ← 기록이 있는 판정만 키가 생긴다
           "top_deny_ips": [{"src_ip": ..., "fails": 그 IP 의 deny 기록 fail_count 합계}, ... 최대 5개]}

  ■ GET /api/security/students
    응답: {"students": [기록이 있는 student 이름들(중복 제거, 이름순)]}

  ■ 함수·데코레이터 인자
    | 이름                         | 인자                         | 돌려주는 것                                   |
    |------------------------------|------------------------------|-----------------------------------------------|
    | require_api_key(fn)          | fn = 보호할 뷰 함수            | wrapper(*args, **kwargs) — 검사 후 fn 호출      |
    | _create_security_post(ev)    | ev = add 된 SecurityEvent     | 새 공지글(Post)의 id (flush 까지만, commit 안 함) |
    | Blueprint('security', ...)   | 이름·import 이름·url_prefix   | 엔드포인트 이름 security.create_security_event 등 |

  ■ 사용하는 설정값 (config.py ← .env)
    | 설정               | .env 값 → 설정값                         | 효과                                        |
    |--------------------|------------------------------------------|---------------------------------------------|
    | SECURITY_API_KEY   | 문자열 (없으면 '')                        | POST 의 비교 대상. '' 이면 POST 항상 401      |
    | AUTO_POST_ON_DENY  | 정확히 '1' 이면 True, 그 밖(기본 '0')은 False | True 면 deny 때 '보안' 공지글 자동 등록       |
      참고: ADMIN_API_KEY 는 이 파일에서 쓰지 않는다(관리자 API 전용).

==============================================================================
5. 요청·응답 예시   (키는 자리표시자. Windows PowerShell 은 curl.exe, 따옴표 규칙이 다르다)
==============================================================================
  ① n8n 이 보내는 것과 같은 저장 요청
    curl -X POST http://localhost:5000/api/security/events -H "X-API-Key: <SECURITY_API_KEY>" -H "Content-Type: application/json" -d '{"student": "lsy", "src_ip": "192.168.0.50", "decision": "deny", "fail_count": 7, "severity": "High", "reason": "5분 동안 로그인 7회 실패", "users": "admin,root", "last_seen": "2026-09-14T10:21:05", "window_min": 5, "source": "login_guard", "generated_at": "2026-09-14T10:21:30"}'
    → 201 {"id": 42, "student": "lsy", "decision": "deny", "post_id": null}
      AUTO_POST_ON_DENY=1 이면 post_id 에 공지글 번호가 오고, 게시판에 이런 글이 생긴다:
        제목     [보안][lsy] 192.168.0.50 접근 거부 (High)
        카테고리 보안     작성자 soarbot
        내용     5분 동안 로그인 7회 실패
                 시도 계정: admin,root
                 마지막 시도: 2026-09-14T10:21:05
                 수집: 2026-09-14T10:21:30

    키가 없거나 틀림 → 401 {"msg": "API 키가 없거나 잘못되었습니다."}
    decision 이 "block" 같은 값 → 400 {"msg": "student, src_ip, decision(allow|deny) 은 필수입니다."}

  ② 목록 — lsy 의 거부 기록 최신 2건
    curl "http://localhost:5000/api/security/events?student=lsy&decision=deny&limit=2"
    → {"count": 2, "events": [{"id": 42, "student": "lsy", "src_ip": "192.168.0.50", "fail_count": 7,
                               "decision": "deny", "severity": "High", ..., "created_at": "2026-09-14T10:21:31"}, {...}]}

  ③ 요약
    curl "http://localhost:5000/api/security/events/summary?student=lsy"
    → {"student": "lsy", "by_decision": {"allow": 3, "deny": 5},
       "top_deny_ips": [{"src_ip": "192.168.0.50", "fails": 21}, {"src_ip": "10.0.0.7", "fails": 6}]}

  ④ 학생 목록
    curl http://localhost:5000/api/security/students
    → {"students": ["kim", "lsy"]}

==============================================================================
6. 자주 걸리는 함정
==============================================================================
  ① 'soarbot' 이름을 누가 먼저 가입해 버리면 그 사람이 보안 공지글의 작성자가 된다.
     /api/auth/register 에는 예약 이름 검사가 없고, _create_security_post 는 username='soarbot' 인
     기존 계정을 그대로 쓴다. post_controller 는 author_id 만 비교하므로 그 사람이 공지글을
     수정·삭제할 수 있다. 반대로 자동으로 만든 soarbot 은 비밀번호를 아무도 몰라 공지글을 지울 사람이 없다.
  ② 조회 3종(GET)은 인증이 없다. 누구나 모든 학생의 IP·시도 계정(users)·사유를 볼 수 있다.
     수업 확인용 의도지만(원본 docstring), 실서비스라면 공격자에게 정보를 주는 셈이다.
  ③ 키 혼동: 이 파일은 SECURITY_API_KEY 만 비교한다. ADMIN_API_KEY 를 보내면 401.
     "ADMIN_API_KEY 가 비면 SECURITY_API_KEY 로 대체" 는 관리자 API 쪽 규칙이고, 그 반대는 없다.
  ④ AUTO_POST_ON_DENY 는 정확히 1 일 때만 켜진다(true, on, yes 는 꺼짐). .env 를 바꿨으면
     config.py 가 import 시점에 한 번 읽으므로 앱을 다시 켜야 반영된다.
     공용 게시판이라 켜면 학생 수만큼 공지글이 쌓인다(.env.example 이 기본 0 인 이유).
  ⑤ 입력 검사가 얕아서 400 이 아니라 500 이 나는 경우가 있다.
     본문이 JSON 객체가 아니라 배열·문자열이면 data.get 에서, student 가 숫자면 .strip() 에서,
     fail_count 가 "abc" 면 int() 에서 예외가 난다. severity 를 null 로 명시하면 NOT NULL 컬럼에 None 이 들어가
     DB 오류가 날 수 있다. src_ip·시각·severity 형식이나 길이는 검사하지 않는다(길이 초과는 DB 설정에 따라 오류·잘림).
  ⑥ 차단된 IP 에서 오는 요청은 이 블루프린트에 닿기 전에 app.py 가 403 으로 돌려보낸다(/api/admin/* 만 예외).
     n8n 이 요청을 보내는 주소가 blocked_ips 에 들어가면 이벤트 저장까지 막힌다.
  ⑦ 키 비교가 일반 문자열 비교(!=)다. 실서비스는 hmac.compare_digest 로 비교 시간 차이를 줄이고,
     키가 평문으로 보이지 않도록 HTTPS 로 보낸다.
  ⑧ 대시보드 숫자 읽는 법: '거부 상위 IP' 는 이벤트 건수가 아니라 fail_count 합계 순이다.
     admin_controller 의 권한 회수 기록은 decision='deny', fail_count=0 이라 거부 '건수'에는 잡히지만
     상위 IP 합계는 늘리지 않는다(src_ip 를 안 보내면 '0.0.0.0'). 대시보드 '전체' 카드는 deny + allow 합이다.
     source 이름도 섞인다: 이 API 기본값 'login_guard'(밑줄) vs 계정 잠금 기록 'login-guard'(하이픈).
  ⑨ limit 은 100 으로 위만 자르고 음수는 막지 않는다(음수는 SQL 의 LIMIT 으로 그대로 가서
     DB 종류에 따라 오류 또는 제한 없음). limit=0 이면 빈 목록.
  ⑩ 공지글 본문에 None 이 찍힐 수 있다. reason·users·last_seen·generated_at 을 안 보내면
     f-string 이 문자 그대로 'None' 을 적는다.
  ⑪ soarbot 이 아직 없을 때 deny 요청 두 개가 동시에 오면 둘 다 계정을 만들려다
     username UNIQUE 제약에 걸려 한쪽이 500 이 날 수 있다(그 요청의 이벤트도 함께 저장되지 않는다).
"""
# ─────────────────────────────────────────────────────────────────────────────
# import
#   os                      : os.urandom — soarbot 의 난수 비밀번호 재료
#   wraps                   : 데코레이터가 원래 함수 이름을 유지하게 해 준다
#   Blueprint               : 라우트 묶음(부서)
#   current_app             : 지금 앱의 설정(SECURITY_API_KEY, AUTO_POST_ON_DENY) 읽기
#   jsonify / request       : JSON 응답 만들기 / 들어온 요청(헤더·본문·쿼리) 읽기
#   generate_password_hash  : 비밀번호 → 해시(soarbot 계정 생성용)
#   db                      : extensions.py 의 SQLAlchemy 객체
#   Post, SecurityEvent, User : 게시글 / 보안 이벤트 / 회원 모델
# ─────────────────────────────────────────────────────────────────────────────
import os
from functools import wraps

from flask import Blueprint, current_app, jsonify, request
from werkzeug.security import generate_password_hash

from extensions import db
from models import Post, SecurityEvent, User

# 블루프린트 생성: 이름 'security', 이 파일의 모든 주소 앞에 /api/security 가 붙는다.
security_bp = Blueprint('security', __name__, url_prefix='/api/security')


# ═════════════════════════════════════════════════════════════════════════════
# require_api_key(fn) — "X-API-Key 가 맞아야 통과" 데코레이터 (fail-closed)
# ─────────────────────────────────────────────────────────────────────────────
# 비유: 기록부 자물쇠. 비밀번호가 설정 안 됐으면(빈 값) 무조건 잠겨 있다.
#
# 입력: fn = 보호할 뷰 함수
# 출력: wrapper 함수 — 요청마다
#         키가 맞음            → fn(...) 결과를 그대로 돌려줌
#         설정 키가 빔 / 헤더 키 없음 / 다름 → 401 {"msg": "API 키가 없거나 잘못되었습니다."}
# 누가 쓰나: 이 파일의 POST /api/security/events 한 곳
#           (관리자 API 는 admin_controller.py 의 admin_required 가 따로 있다 — 키도 다르다)
#
# 사용 모양:
#   @security_bp.route('/events', methods=['POST'])   ← 위: 라우트 등록
#   @require_api_key                                  ← 아래: 먼저 감싼다(괄호 없이 쓴다)
#   def create_security_event(): ...
# ═════════════════════════════════════════════════════════════════════════════
def require_api_key(fn):
  """X-API-Key 가 설정값과 같을 때만 통과. 키가 비었거나 다르면 401(fail-closed)."""
  # wraps(fn) : wrapper 의 이름을 'create_security_event' 로 유지 → Flask 엔드포인트 이름이 겹치지 않는다
  @wraps(fn)
  def wrapper(*args, **kwargs):
    # 서버에 설정된 정답 키. 없으면 '' (config.py 기본값도 '')
    expected = current_app.config.get('SECURITY_API_KEY', '')
    # 두 조건 중 하나라도 참이면 거절:
    #   not expected                      → 정답 키가 비었다 = 설정 누락 → 무조건 닫는다(fail-closed)
    #   헤더 X-API-Key 가 정답과 다르다     → 헤더가 없으면 '' 로 보고 비교 → 역시 다름
    # (not expected 검사가 없다면, 정답 '' 과 '헤더 없음' '' 이 같아져 누구나 통과하게 된다)
    if not expected or request.headers.get('X-API-Key', '') != expected:
      return jsonify({'msg': 'API 키가 없거나 잘못되었습니다.'}), 401
    # 통과 — 원래 뷰 함수를 받은 인자 그대로 실행
    return fn(*args, **kwargs)
  # 데코레이터는 '감싼 함수'를 돌려준다 → 이후 이 이름으로 부르면 wrapper 가 실행된다
  return wrapper


# ═════════════════════════════════════════════════════════════════════════════
# _create_security_post(ev) — 거부 이벤트를 게시판 '보안' 공지글로 자동 등록 (심화)
# ─────────────────────────────────────────────────────────────────────────────
# 비유: 돌려보낸 방문자가 있으면 1층 게시판에 '시스템(soarbot)' 명의로 공지를 붙인다.
#
# 입력: ev = 방금 session 에 add 된 SecurityEvent (student, src_ip, severity, reason, users,
#            last_seen, generated_at 을 읽는다)
# 출력: 새 공지글의 id (정수). commit 은 하지 않는다 → 부른 쪽(create_security_event)이 한 번에 commit
# 누가 호출하나: create_security_event() — decision == 'deny' 이고 AUTO_POST_ON_DENY 가 True 일 때만
# 이름 앞 밑줄(_) : "이 파일 안에서만 쓰는 도우미" 라는 파이썬 관례(라우트 아님)
# ═════════════════════════════════════════════════════════════════════════════
def _create_security_post(ev):
  """심화: 거부 이벤트를 게시판 '보안' 공지글로 자동 등록(작성자 = 시스템 계정)."""
  # 게시글에는 author_id(작성자)가 반드시 필요하다(posts.author_id NOT NULL) → 시스템 계정을 쓴다.
  # 이름으로 찾기만 하므로, 누군가 먼저 'soarbot' 으로 가입했다면 그 계정이 쓰인다(함정 ①)
  bot = User.query.filter_by(username='soarbot').first()
  # 처음 한 번은 계정이 없으니 만든다
  if not bot:
    # 비밀번호 = 32글자 난수의 해시. 원문을 어디에도 남기지 않으므로 아무도 이 계정으로 로그인할 수 없다.
    # role 은 모델 기본값 'user'
    bot = User(username='soarbot',
               password=generate_password_hash(os.urandom(16).hex()))
    db.session.add(bot)
    # INSERT 를 미리 보내 bot.id 를 받는다(아래 author_id 에 필요). 아직 확정(commit)은 아니다
    db.session.flush()

  # 공지글 만들기
  post = Post(
      # 예) [보안][lsy] 192.168.0.50 접근 거부 (High)
      title=f'[보안][{ev.student}] {ev.src_ip} 접근 거부 ({ev.severity})',
      # 줄바꿈(\n)으로 네 줄: 사유 / 시도 계정 / 마지막 시도 / 수집 시각
      # 값이 None 이면 f-string 이 'None' 이라고 적는다(함정 ⑩)
      # 괄호 안에서 문자열 두 개를 나란히 쓰면 파이썬이 하나로 이어 붙인다
      content=(f'{ev.reason}\n시도 계정: {ev.users}\n'
               f'마지막 시도: {ev.last_seen}\n수집: {ev.generated_at}'),
      # 카테고리 '보안', 작성자 = soarbot
      category='보안', author_id=bot.id)
  db.session.add(post)
  # post.id 를 받기 위해 flush (commit 은 부른 쪽이 한다)
  db.session.flush()
  return post.id


# ═════════════════════════════════════════════════════════════════════════════
# create_security_event() — n8n 판정 결과 1건 저장 (이 표에 INSERT 하는 입구)
# ─────────────────────────────────────────────────────────────────────────────
# 비유: 경비원(n8n)이 자물쇠 비밀번호를 대고 기록부에 한 줄 적는다.
#       '돌려보냄' 이고 공지 스위치가 켜져 있으면 게시판 공지까지 같이 붙인다.
#
# 입력: 헤더 X-API-Key: <SECURITY_API_KEY>
#       body JSON — 필수 student, src_ip, decision(allow|deny) / 선택 fail_count, severity, reason,
#                   users, last_seen, window_min, source, generated_at   (4절 표 참고)
# 출력: 201 {"id", "student", "decision", "post_id"}
#       400 필수값 누락 / 401 키 문제(require_api_key) / 403 차단 IP(app.py)
# 누가 호출하나: n8n 워크플로우의 HTTP 요청 단계
# 주소: POST /api/security/events
# 데코레이터 순서: route 가 위, require_api_key 가 아래 → 등록되는 것은 '키 검사로 감싼 함수'
# ═════════════════════════════════════════════════════════════════════════════
@security_bp.route('/events', methods=['POST'])
@require_api_key
def create_security_event():
  # 본문이 없거나 JSON 으로 못 읽으면 None → {} → 아래 필수값 검사에서 400.
  # (단, JSON 이긴 한데 객체가 아닌 배열·문자열이면 data.get 에서 500 — 함정 ⑤)
  data = request.get_json(silent=True) or {}      # JSON 아니어도 500 대신 400
  # student : None 이어도 '' 로 바꾼 뒤 앞뒤 공백 제거 → "  " 같은 공백만 있는 값도 걸러진다
  student = (data.get('student') or '').strip()
  # src_ip·decision 은 공백 제거 없이 그대로
  src_ip = data.get('src_ip')
  decision = data.get('decision')
  # 셋 중 하나라도 비었거나, decision 이 정확히 'allow'/'deny' 가 아니면(대소문자 구분) 400
  if not student or not src_ip or decision not in ('allow', 'deny'):
    return jsonify({'msg': 'student, src_ip, decision(allow|deny) 은 필수입니다.'}), 400

  # 저장할 행(row) 만들기 — 선택 필드는 없으면 None(DB 에서 NULL) 또는 괄호 속 기본값
  ev = SecurityEvent(
      # student 는 컬럼 길이 50 에 맞춰 잘라서 저장 / src_ip 는 그대로
      student=student[:50], src_ip=src_ip,
      # fail_count : 없음·null·0·'' 이면 0, "7" 같은 문자열 숫자도 int 로 바뀐다("abc" 는 ValueError → 500)
      fail_count=int(data.get('fail_count') or 0), decision=decision,
      # severity : 키가 아예 없을 때만 'Low'. 값 목록(Low/Medium/High...) 검사는 없다
      severity=data.get('severity', 'Low'), reason=data.get('reason'),
      # 시도된 계정들, 마지막 시도 시각(문자열 그대로)
      users=data.get('users'), last_seen=data.get('last_seen'),
      # 집계 구간(분)
      window_min=data.get('window_min'),
      # 이벤트 출처 — 기본 'login_guard'(밑줄). 관리자 조치 기록은 'login-guard' 등 하이픈을 쓴다(함정 ⑧)
      source=data.get('source', 'login_guard'),
      # 보낸 쪽이 만든 시각(문자열 그대로). DB 저장 시각 created_at 은 모델이 자동으로 채운다
      generated_at=data.get('generated_at'),
  )
  # INSERT 예약
  db.session.add(ev)
  # INSERT 를 미리 보내 자동 증가 id 를 받는다(아직 확정 아님).
  # 참고: 현재 코드는 commit 전에 ev.id 를 따로 쓰지는 않는다(공지글 내용에도 id 는 없다)
  db.session.flush()                              # ev.id 확보

  # 공지글 번호 — 만들지 않으면 None → 응답 JSON 에서 null
  post_id = None
  # 거부 판정이고, 설정 AUTO_POST_ON_DENY 가 True(.env 에서 정확히 '1')일 때만 공지글 생성
  if decision == 'deny' and current_app.config.get('AUTO_POST_ON_DENY'):
    post_id = _create_security_post(ev)

  # 이벤트 + (soarbot 계정) + 공지글을 여기서 한 번에 확정
  db.session.commit()                             # 이벤트+공지글을 한 트랜잭션으로
  # 201 Created. student 는 잘린(최대 50자) 저장값이 돌아간다
  return jsonify({'id': ev.id, 'student': ev.student,
                  'decision': ev.decision, 'post_id': post_id}), 201


# ═════════════════════════════════════════════════════════════════════════════
# list_security_events() — 이벤트 목록 조회 (키 없음)
# ─────────────────────────────────────────────────────────────────────────────
# 비유: 기록부 열람창. 누구나 최근 기록을 볼 수 있고, 학생·판정으로 골라 볼 수 있다.
#
# 입력: 쿼리 ?student=  ?decision=allow|deny  ?limit=(기본 20, 최대 100)
# 출력: 200 {"count": 건수, "events": [SecurityEvent.to_dict(), ...]}  — 최신 id 순
# 누가 호출하나: templates/dashboard.html 의 loadEvents() (limit=50 으로 호출)
# 주소: GET /api/security/events   (같은 주소의 POST 와는 메서드로 구분된다)
# ═════════════════════════════════════════════════════════════════════════════
@security_bp.route('/events', methods=['GET'])
def list_security_events():
  """조회는 키 없이(수업 확인용). ?student= 로 본인 것만 고른다."""
  # 없으면 None
  student = request.args.get('student')
  decision = request.args.get('decision')
  # 숫자가 아니면 기본 20 (Werkzeug 의 type 변환 실패 → default)
  limit = request.args.get('limit', default=20, type=int)

  # 조건 조립 — 아직 DB 에 가지 않는다
  query = SecurityEvent.query
  # filter_by(컬럼=값) : 같은 값만 (WHERE student = ?)
  if student:
    query = query.filter_by(student=student)
  # allow/deny 가 아닌 값은 조용히 무시 → 전체
  if decision in ('allow', 'deny'):
    query = query.filter_by(decision=decision)

  # 최신 id 순, min(limit, 100) : 한 번에 100건을 넘기지 않는다(음수는 막지 않음 — 함정 ⑨)
  rows = query.order_by(SecurityEvent.id.desc()).limit(min(limit, 100)).all()
  # 모델 객체 → dict 로 바꿔 JSON 응답
  return jsonify({'count': len(rows), 'events': [r.to_dict() for r in rows]})


# ═════════════════════════════════════════════════════════════════════════════
# security_events_summary() — 허용/거부 건수 + 거부 상위 IP 5개 (키 없음)
# ─────────────────────────────────────────────────────────────────────────────
# 비유: 기록부 맨 앞장의 요약표 — "통과 몇 건, 돌려보냄 몇 건, 가장 많이 실패한 IP 다섯 곳".
#
# 입력: 쿼리 ?student= (선택)
# 출력: 200 {"student": 값 또는 null,
#            "by_decision": {"allow": n, "deny": m},
#            "top_deny_ips": [{"src_ip": ..., "fails": 합계}, ...]}
# 누가 호출하나: templates/dashboard.html 의 loadSummary()
#   → 전체(deny+allow) / 거부 / 허용 카드, '최다 거부 IP', '거부 상위 IP' 막대그래프
# 주소: GET /api/security/events/summary
# ═════════════════════════════════════════════════════════════════════════════
@security_bp.route('/events/summary', methods=['GET'])
def security_events_summary():
  """허용/거부 건수 + 거부 상위 IP 5개."""
  # 집계 함수 모음(func.count, func.sum). 파일 맨 위가 아니라 이 함수 안에서만 import 한다
  from sqlalchemy import func

  student = request.args.get('student')
  # q1 ≈ SELECT decision, COUNT(id) FROM security_events [WHERE student=?] GROUP BY decision
  #      (GROUP BY 는 아래 by_decision 줄에서 붙인다)
  q1 = db.session.query(SecurityEvent.decision, func.count(SecurityEvent.id))
  # q2 ≈ SELECT src_ip, SUM(fail_count) FROM security_events WHERE decision='deny' [AND student=?]
  #      GROUP BY src_ip ORDER BY SUM(fail_count) DESC LIMIT 5
  #      → '건수'가 아니라 '실패 횟수 합계'로 순위를 매긴다(함정 ⑧)
  q2 = (db.session.query(SecurityEvent.src_ip, func.sum(SecurityEvent.fail_count))
        .filter(SecurityEvent.decision == 'deny'))
  # 학생을 골랐으면 두 쿼리 모두에 같은 조건
  if student:
    q1 = q1.filter(SecurityEvent.student == student)
    q2 = q2.filter(SecurityEvent.student == student)

  # [('allow', 3), ('deny', 5)] 같은 (판정, 건수) 튜플 목록 → {'allow': 3, 'deny': 5}
  #   기록이 없는 판정은 키 자체가 없다 → 화면 JS 는 d.by_decision?.deny || 0 으로 받는다
  by_decision = dict(q1.group_by(SecurityEvent.decision).all())
  # [('192.168.0.50', 21), ...] 최대 5개
  top = (q2.group_by(SecurityEvent.src_ip)
         .order_by(func.sum(SecurityEvent.fail_count).desc()).limit(5).all())

  return jsonify({
      # 요청에 준 student 를 그대로 되돌려 준다(없으면 null)
      'student': student,
      'by_decision': by_decision,
      # SUM 결과는 DB 드라이버에 따라 Decimal 로 올 수 있어 int() 로 JSON 숫자로 맞춘다
      'top_deny_ips': [{'src_ip': ip, 'fails': int(n)} for ip, n in top],
  })


# ═════════════════════════════════════════════════════════════════════════════
# list_students() — 기록이 있는 학생 이름 목록 (키 없음)
# ─────────────────────────────────────────────────────────────────────────────
# 비유: 기록부에 한 번이라도 이름이 오른 사람 명단(중복 없이, 이름순).
#
# 입력: 없음
# 출력: 200 {"students": ["kim", "lsy", ...]}
# 누가 호출하나: templates/dashboard.html 의 loadStudents() → '학생' 드롭다운 채우기
# 주소: GET /api/security/students
# 참고: admin_controller 의 조치 기록은 body 에 student 가 없으면 조치한 주체(API 키 호출이면 'apikey',
#       사람이면 관리자 username)를 student 로 저장한다 → 그 이름도 이 목록에 섞여 나온다.
# ═════════════════════════════════════════════════════════════════════════════
@security_bp.route('/students', methods=['GET'])
def list_students():
  """대시보드 드롭다운용 — 기록이 있는 학생 목록."""
  # SELECT DISTINCT student FROM security_events ORDER BY student
  rows = (db.session.query(SecurityEvent.student)
          .distinct().order_by(SecurityEvent.student).all())
  # 각 행은 ('lsy',) 처럼 칸 하나짜리 튜플 → r[0] 으로 이름만 꺼낸다
  return jsonify({'students': [r[0] for r in rows]})
