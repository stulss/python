"""[주석·설명용 사본] controllers/admin_controller.py — 관리자(인가/RBAC) REST: 권한 부여·회수, 계정 잠금, IP 차단, 인시던트

이 파일은 원본 controllers/admin_controller.py 를 복사해 주석만 덧붙인 학습용 사본이다.
  · 실행 코드는 원본과 똑같다(주석과 이 설명 문자열만 추가).
  · 원본을 고쳐도 이 사본에는 반영되지 않는다.
  · 앱은 원본을 import 한다: controllers/__init__.py 의  from .admin_controller import admin_bp
    (이 사본 파일 이름에는 공백과 '-' 가 있어 import 문으로는 부를 수도 없다.)

==============================================================================
0. 한 줄 요약
==============================================================================
  "관리자만 드나드는 REST 창구 모음 — 회원 등급을 올리고(grant) 내리고(revoke),
   계정을 잠그고(lock), 공격 IP 를 막고(block), 사건 티켓(incident)을 만든다.
   통과하려면 API 키(기계) 또는 admin 로그인(사람) 둘 중 하나가 필요하다."

  원본 설명 그대로:
    관리자(인가/RBAC) REST — 회원 권한 부여·회수.
    접근 방식 두 가지
      ① 기계 호출(n8n·회수봇)  : 헤더  X-API-Key: <ADMIN_API_KEY>
      ② 사람(관리자 페이지)     : JWT(로그인 토큰) + 그 계정의 role == 'admin'
    시나리오
      - 관리자 페이지에서 특정 회원에게 admin 을 '부여'(인가) → 불필요한 과잉권한 발생
      - 파이썬 회수봇이 허용목록(ADMIN_ALLOWLIST) 밖 admin 을 탐지 → Graylog 신고
      - Graylog 이벤트 → n8n → 이 API 의 /revoke 를 호출해 실제 '회수'(최소권한 복원)
      - 회수 시 security_events 에 감사기록(source='privilege-guard') → 대시보드 노출

==============================================================================
1. 쉬운 비유 — 회사 건물의 '관리실 창구'
==============================================================================
  게시판(Flask 앱)              = 회사 건물
  /api/admin/* (이 파일)        = 관리실 창구 — 마스터키·출입카드·출입금지 명단·사건 파일을 다룬다
  admin_required                = 창구 앞 경비 — 출입증이나 관리자 사원증을 확인
  X-API-Key                     = 기계(회수봇·n8n)용 출입증
  JWT + role == 'admin'         = 사람(관리자)용 사원증 — 로그인 토큰 + 장부상 직급이 admin
  grant / revoke                = 마스터키(등급) 지급 / 회수
  lock / unlock                 = 직원 출입카드 정지 / 재개
  block / unblock               = 방문자(IP) 출입금지 명단 등록 / 해제
  security_events               = 보안 일지 (/dashboard 화면 = 일지를 벽에 붙인 게시판)
  incident                      = 사건 파일 — 같은 출발지의 일지를 한 파일로 묶는다
  request.actor                 = 처리한 사람 도장 ('apikey' 또는 관리자 아이디)

  경비원(회수봇)이 순찰하다 명단에 없는 마스터키 소지자(kim)를 찾아 관제실(Graylog)에 무전을 치면,
  보안팀(n8n)이 관리실 창구에 출입증(X-API-Key)을 내밀고 "kim 의 키를 회수해 주세요"(POST /revoke)라고 한다.
  창구는 키를 회수하고 보안 일지(security_events)에 한 줄 적는다.
  관리자가 직접 창구에 와서(관리자 페이지 /admin) 사원증(JWT)을 보이고 처리할 수도 있다.

==============================================================================
2. 기본 개념 — 이 파일에 실제로 쓰인 것만
==============================================================================
  ■ Blueprint 와 url_prefix
      Blueprint = 관련 라우트를 묶는 상자. admin_bp 는 url_prefix='/api/admin' 이라
      @admin_bp.route('/users') 의 실제 주소는 /api/admin/users 가 된다.
      app.py 의 create_app 이 controllers/__init__.py 의 all_blueprints 를 돌며 register_blueprint 로 등록한다.

  ■ 데코레이터와 functools.wraps
      @admin_required 는 뷰 함수를 감싸 "검사 → 통과하면 원래 함수 실행"으로 바꾼다.
      @wraps(fn) 은 감싼 함수(wrapper)에 원래 함수의 이름·docstring 을 옮겨 붙인다.
      없으면 뷰 12개가 모두 'wrapper' 라는 같은 이름이 되고, Flask 는 함수 이름으로 endpoint 를 정하므로
      두 번째 등록부터 "이미 있는 endpoint 를 덮어쓴다"는 AssertionError 가 나서 앱이 뜨지 않는다.
      쌓는 순서도 중요하다 — 아래 데코레이터부터 적용된다.
        @admin_bp.route(...)   ← 나중에 적용: '검사가 붙은 함수'를 주소에 등록
        @admin_required        ← 먼저 적용: 원래 함수를 검사로 감쌈
      둘을 뒤집으면 주소에는 검사 없는 원래 함수가 등록되어 누구나 호출할 수 있게 된다.

  ■ 인증(Authentication) vs 인가(Authorization)
      인증 = "너 누구야?"   /   인가 = "너 이거 해도 돼?"
      controllers/rbac.py 의 role_required 는 둘을 구분해 401(로그인 안 함)·403(등급 부족)을 준다.
      이 파일의 admin_required 는 구분하지 않고 실패하면 언제나 401 이다(6절 ①).

  ■ API 키 vs JWT
      API 키 : 미리 나눠 가진 비밀 문자열 1개를 헤더 X-API-Key 에 싣는다. 사람이 아닌 프로그램용.
               누가 보냈는지는 구분하지 못한다 → 기록에는 모두 'apikey' 로 남는다.
      JWT    : POST /api/auth/login 성공 때 받는 서명된 토큰. 헤더 Authorization: Bearer <토큰>.
               토큰에는 사용자 id 만 들어 있고(create_access_token(identity=str(user.id))),
               role 은 요청마다 DB 에서 다시 읽는다(rbac.current_user) → 회수하면 다음 요청부터 바로 막힌다.
               유효기간은 2시간(config.py 의 JWT_ACCESS_TOKEN_EXPIRES).

  ■ fail-closed
      ADMIN_API_KEY 가 빈 문자열이면 키 경로는 무조건 실패한다. "설정을 깜빡하면 열리는 게 아니라 닫힌다."
      config.py: ADMIN_API_KEY 가 비면 SECURITY_API_KEY 로 대체, 둘 다 비면 '' → 키로는 아무도 못 들어온다.

  ■ request.actor — 요청 한 건 동안만 쓰는 메모
      Flask 의 request 는 요청마다 새로 생긴다. 데코레이터가 request.actor 에 '누가'를 적어 두면
      같은 요청 안의 뷰 함수가 getattr(request, 'actor', 'unknown') 으로 꺼내 감사기록에 쓴다.

  ■ HTTP 메서드와 상태코드 (이 파일에서 쓰는 것)
      GET = 조회(DB 를 바꾸지 않음)   /   POST = 변경
      200 OK · 201 Created(인시던트를 새로 만들 때만) · 400 필수값 누락·잘못된 값
      401 인가 실패 · 404 대상 없음 · 잡지 않은 예외는 Flask 가 500 으로 돌려준다

  ■ 멱등(idempotent) 처리
      "같은 요청을 두 번 보내도 결과가 같다." revoke·lock·block 은 이미 목표 상태면 DB 를 바꾸지 않고
      200 + revoked/changed = false 를 돌려주며 감사기록도 남기지 않는다.
      n8n 이 재시도하거나, 회수봇 --revoke 와 n8n 이 같은 계정을 차례로 회수해도 기록은 한 번만 남는다.
      단 두 요청이 정말 같은 순간에 겹치면 둘 다 바뀌기 전 값을 읽어 기록이 2건 남을 수 있고,
      block 은 두 번째 INSERT 가 기본키(ip) 중복으로 500 이 될 수 있다(행 잠금 같은 동시성 처리는 없다).

  ■ ORM 조회와 commit (Flask-SQLAlchemy)
      User.query.filter_by(username=...).first()   조건에 맞는 첫 행, 없으면 None
      db.session.get(모델, 기본키)                   기본키로 한 행, 없으면 None
      객체.속성 = 값          → db.session.commit() 때 UPDATE
      db.session.add(새 객체) → commit 때 INSERT. commit 뒤에야 자동 증가 번호(ev.id)를 알 수 있다
      db.session.delete(객체) → commit 때 DELETE

  ■ 감사기록(Audit trail) — 두 군데
      users 표           : role_granted_by / role_granted_at / role_reason — '마지막 변경'만 남는다(덮어씀)
      security_events 표 : 한 줄씩 쌓인다(이력). revoke·lock·block 이 실제로 바뀔 때만 추가된다
      /dashboard 화면은 GET /api/security/events 로 이 표를 읽어
      학생·IP·거부 배지·심각도·실패수·사유·시각을 보여준다(source 열은 화면에 없다).

  ■ SOAR 와 active response
      탐지(Graylog) → 판단·자동화(n8n) → 실제 조치(이 파일의 revoke·lock·block).
      block 의 효과는 app.py 의 before_request 미들웨어 _block_ip_guard 가 낸다:
      요청 IP 가 blocked_ips 에 있으면 403. 단 /api/admin 경로는 검사하지 않는다
      (운영자·n8n 이 스스로 막혀 차단 해제를 못 하게 되는 일을 막는 안전장치).

  ■ 인시던트(Incident) 티켓
      models/incident.py: 탐지·대응 뒤 "무슨 일이 언제, 무엇을 했나"를 한 건으로 묶는 추적 단위.
      실무 티켓(Jira/ServiceNow)의 축소판. 같은 src_ip 의 '열린(open)' 티켓은 하나만 둔다.

==============================================================================
3. 동작 원리
==============================================================================
  3-1. 요청 한 건의 흐름 (예: POST /api/admin/revoke)

   요청
     │
     ▼
   app.py  _block_ip_guard (before_request)
     │  경로가 /api/admin 으로 시작 → IP 차단 검사를 건너뛴다
     ▼
   admin_required 의 wrapper
     ├─ ① X-API-Key 가 ADMIN_API_KEY 와 같다       → request.actor = 'apikey'  → 뷰 함수로
     ├─ ② JWT 가 유효하고 그 계정 role == 'admin'  → request.actor = 그 아이디 → 뷰 함수로
     └─ 둘 다 아니다 → 401 {"msg": "관리자 인가가 필요합니다(X-API-Key 또는 admin 로그인)."}
     ▼
   뷰 함수 (예: revoke_role)
     ├─ body 읽기       request.get_json(silent=True) or {}
     ├─ 필수값 검사     없으면 400
     ├─ 대상 조회       없으면 404
     ├─ 이미 목표 상태  → 200 + revoked(changed) = false  (DB 변경 없음)
     └─ 값 변경 (+ SecurityEvent 추가) → db.session.commit() → 200 JSON

  3-2. 과잉권한 시나리오 — privilege_revoke_bot.py 와 맞물리는 부분

   [관리자 페이지 /admin] ─ POST /grant {"username": "kim", "role": "admin"} (JWT) ─▶ kim.role = admin
   [회수봇, 매시간]       ─ GET /users?role=admin (X-API-Key) ─▶ admin 목록
        │  허용목록(ADMIN_ALLOWLIST)과 대조 → kim 은 명단에 없음 = 위반
        ▼
   [회수봇] ─ GELF UDP 12201 (rule=priv-unauthorized-admin) ─▶ [Graylog] ─ 이벤트 ─▶ [n8n]
   [n8n]    ─ POST /revoke {"username": "kim", ...} (X-API-Key) ─▶ kim.role = user + security_events 1줄
   · 봇을 --revoke 로 돌리면 n8n 대신 봇이 직접 POST /revoke (source='privilege-guard-bot')
   · 관리자 페이지의 '회수'·'즉시 회수' 버튼도 같은 POST /revoke (JWT, reason='관리자 페이지 수동 회수')

  3-3. 로그인 무차별 대입 시나리오 — lock / block 쪽

   [로그인 실패] auth_controller → controllers/gelf.py send_gelf(rule=login-bruteforce) ─▶ [Graylog]
     ─▶ [n8n] ─▶ POST /lock {"username": ...} 또는 POST /block {"ip": ...}
   · lock·block 의 docstring 에 "n8n 이 호출"이라고 적혀 있다. n8n 워크플로 파일은 이 저장소에 없다.
   · /unlock, /unblock, /blocked, /incident, /incidents, /incident/close 는
     저장소 안의 화면·봇·테스트 어디서도 부르지 않는다 → curl·n8n 등 밖에서 직접 호출한다.

==============================================================================
4. 옵션 설명
==============================================================================
  4-1. 인가 — 모든 엔드포인트 공통(@admin_required)

    방식  보내는 헤더                     통과 조건                                   request.actor
    기계  X-API-Key: <ADMIN_API_KEY>      설정 키가 비어 있지 않고 헤더 값과 똑같다   'apikey'
    사람  Authorization: Bearer <JWT>     토큰 유효 + DB 의 그 계정 role == 'admin'   그 아이디
    실패  (둘 다 아님)                    → 401                                       -
    검사 순서는 키가 먼저다. 키가 맞으면 JWT 는 보지 않는다.

  4-2. 엔드포인트 요약 (URL 앞에 모두 /api/admin 이 붙는다)

    메서드 URL              함수             하는 일             확인된 호출처
    GET    /users           list_users       회원 목록 + 역할    admin.html, 회수봇, 테스트
    GET    /violations      list_violations  허용목록 밖 admin   admin.html, 테스트
    POST   /grant           grant_role       역할 부여           admin.html, 테스트
    POST   /revoke          revoke_role      역할 회수(→ user)   admin.html, 회수봇 --revoke, n8n, 테스트
    POST   /lock            lock_account     계정 잠금           n8n(docstring)
    POST   /unlock          unlock_account   잠금 해제           저장소 안에는 없음
    POST   /block           block_ip         IP 실차단           n8n(docstring)
    POST   /unblock         unblock_ip       IP 차단 해제        저장소 안에는 없음
    GET    /blocked         list_blocked     차단 IP 목록        저장소 안에는 없음
    POST   /incident        create_incident  인시던트 생성/갱신  저장소 안에는 없음
    GET    /incidents       list_incidents   인시던트 목록       저장소 안에는 없음
    POST   /incident/close  close_incident   인시던트 종료       저장소 안에는 없음

  4-3. 엔드포인트별 입력과 응답
    (body 는 JSON. "기본"은 값을 안 보냈거나 빈 값일 때 대신 쓰는 값)

    ▶ GET /users
      쿼리  role = user | gold | admin   (선택. 생략하거나 목록 밖 값이면 필터 없이 전체)
      200   {"count": N, "users": [회원, ...]}   id 오름차순
            회원 = id, username, role, role_granted_by, role_granted_at, role_reason,
                   is_locked, locked_at, lock_reason, failed_logins   (password 는 들어 있지 않다)

    ▶ GET /violations
      쿼리  allowlist = "lsy,instructor"   (선택. 생략·빈 값이면 config 의 ADMIN_ALLOWLIST)
      200   {"allowlist": [...], "count": N, "violations": [회원, ...]}
      위반  role == 'admin' 이면서 username 이 allowlist 에 없는 계정. gold 는 위반이 아니다.

    ▶ POST /grant
      body  username  필수
            role      필수, user | gold | admin 중 하나
            reason    선택, 기본 '' (200자에서 자름)
      200   {"msg": "역할 부여 완료", "username", "old_role", "new_role", "granted_by"}
      400   {"msg": "username, role(user|gold|admin) 은 필수입니다."}
      404   {"msg": "없는 사용자: <username>"}
      DB    users 의 role, role_granted_by(=actor), role_granted_at(=지금), role_reason. security_events 는 안 남긴다

    ▶ POST /revoke
      body  username      필수
            reason        선택. users.role_reason 기본      '<이전역할>→user 회수 by <actor>'
                                security_events.reason 기본 '과잉권한 회수: <username> <이전역할>→user'
            student       선택, 기본 actor (50자)
            src_ip        선택, 기본 '0.0.0.0'
            severity      선택, 기본 'High'
            source        선택, 기본 'privilege-guard'   ← docstring 의 body 목록엔 없지만 코드가 읽는다
            generated_at  선택, 기본 없음(null)          ← 위와 같음
      200   회수함    {"msg": "권한 회수 완료", "username", "old_role", "new_role": "user",
                       "revoked": true, "event_id", "revoked_by"}
      200   이미 user {"msg": "이미 user 권한(회수 불필요)", "username", "old_role": "user",
                       "new_role": "user", "revoked": false}
      400   {"msg": "username 은 필수입니다."}        404  {"msg": "없는 사용자: <username>"}
      규칙  gold 든 admin 이든 한 번에 user 까지 내린다. 허용목록은 보지 않는다(누구를 회수할지는 부르는 쪽 판단).
            security_events 에는 fail_count=0, decision='deny', users=username 으로 남는다.

    ▶ POST /lock
      body  username 필수 / reason / student(기본 actor) / src_ip(기본 '0.0.0.0')
            fail_count(기본 0, 정수로 변환) / severity(기본 'High') / source(기본 'login-guard') / generated_at
      200   잠금  {"msg": "계정 잠금 완료", "username", "locked": true, "changed": true, "event_id", "locked_by"}
      200   이미  {"msg": "이미 잠긴 계정", "username", "locked": true, "changed": false}
      400 / 404   /revoke 와 같은 문구
      DB    is_locked=True, locked_at=지금, lock_reason(기본 '브루트포스 자동 잠금 by <actor>')
            + security_events 1줄(reason 기본 '계정 잠금: <username> (브루트포스)')
      효과  auth_controller 의 login 이 is_locked 를 보고 423 으로 거부한다

    ▶ POST /unlock
      body  username 필수
      200   {"msg": "잠금 해제 완료", "username", "locked": false, "unlocked_by"}   (원래 안 잠겨 있어도 200)
      400 / 404
      DB    is_locked=False, failed_logins=0, lock_reason=None. locked_at 은 그대로. security_events 는 안 남긴다

    ▶ POST /block
      body  ip 또는 src_ip (둘 중 하나 필수, ip 우선) / reason(기본 '자동 차단 by <actor>')
            student(기본 actor) / fail_count(기본 0) / severity(기본 'High') / source(기본 'ip-guard') / generated_at
      200   차단  {"msg": "IP 차단 완료", "ip", "blocked": true, "changed": true, "event_id", "blocked_by"}
      200   이미  {"msg": "이미 차단된 IP", "ip", "blocked": true, "changed": false}
      400   {"msg": "ip(또는 src_ip) 는 필수입니다."}
      DB    blocked_ips 1줄(ip, reason, blocked_by=actor, blocked_at=지금)
            + security_events 1줄(users='', reason 기본 'IP 실차단: <ip>')

    ▶ POST /unblock
      body  ip 또는 src_ip (필수)
      200   {"msg": "차단 해제 완료", "ip", "blocked": false, "unblocked_by"}   (원래 차단 안 된 IP 여도 200)
      400   {"msg": "ip 는 필수입니다."}

    ▶ GET /blocked
      200   {"count": N, "blocked": [{"ip", "reason", "blocked_by", "blocked_at"}, ...]}   최근 차단 순

    ▶ POST /incident
      body  src_ip 또는 ip (필수, src_ip 우선)
            title     선택, 기본 '보안 인시던트: <src_ip> (<건수>건)' (200자)
            severity  선택, 기본 = 모은 이벤트 중 최고 심각도
            student   선택, 기본 actor (50자)
            hours     선택, 기본 24 — 최근 몇 시간의 security_events 를 모을지
      201   새로 만듦  {"msg": "인시던트 생성", "created": true, "incident": {...}}
      200   갱신함     {"msg": "인시던트 갱신", "created": false, "incident": {...}}
      400   {"msg": "src_ip 는 필수입니다."}
      incident = id, title, src_ip, severity, status, summary, event_count, actions, student,
                 created_at, updated_at, closed_at

    ▶ GET /incidents
      쿼리  status = open | closed   (선택. 생략·목록 밖 값이면 전체)
      200   {"count": N, "incidents": [...]}   최근 갱신 순

    ▶ POST /incident/close
      body  id (인시던트 번호. 없으면 0 으로 찾으므로 404)
      200   {"msg": "인시던트 종료", "incident": {...}}
      404   {"msg": "없는 인시던트"}

  4-4. 모듈 상수와 도우미 함수

    이름                            인자 → 반환
    ROLE_CHOICES                    'user|gold|admin' (400 오류 문구용 문자열)
    _SEV_RANK                       {'Low': 1, 'Medium': 2, 'High': 3, 'Critical': 4} (대소문자 구분)
    _has_valid_key()                없음 → True / False
    _current_admin_user()           없음 → User 또는 None
    admin_required(fn)              감쌀 뷰 함수 → 검사가 붙은 wrapper 함수
    _allowlist(param=None)          "a,b" 문자열 또는 None → 아이디 리스트
    _build_summary(src_ip, events)  출발지 IP, SecurityEvent 리스트(최신순)
                                    → (요약 문자열, 최고 심각도, 조치 문자열, 건수)

  4-5. 사용하는 설정(config)과 환경변수

    config 키        .env 환경변수                            설명
    ADMIN_API_KEY    ADMIN_API_KEY (비면 SECURITY_API_KEY)    기계 호출 키. 둘 다 비면 키 경로 차단
    ADMIN_ALLOWLIST  ADMIN_ALLOWLIST (예: lsy,instructor)     /violations 기본 허용목록. 비면 모든 admin 이 위반
    JWT_SECRET_KEY   JWT_SECRET_KEY                           사람 경로의 토큰 서명 검증(rbac.current_user)

==============================================================================
5. 요청·응답 예시 (Git Bash 기준 한 줄 명령. 키·토큰은 자리표시자)
==============================================================================
  ※ 실제 응답은 Flask 가 키를 알파벳순으로 정렬하고 한글을 유니코드 이스케이프로 바꿔 내보낸다.
    아래는 읽기 쉽게 순서를 바꾸고 한글로 적었다(브라우저·파이썬이 받아 풀면 같은 값이다).

  ① admin 만 조회 — 회수봇 find_violations 와 같은 호출
    curl -H "X-API-Key: <ADMIN_API_KEY>" "http://localhost:5000/api/admin/users?role=admin"
    → 200 {"count": 2, "users": [{"id": 1, "username": "lsy", "role": "admin", ...},
                                 {"id": 3, "username": "kim", "role": "admin", "role_granted_by": "lsy", ...}]}

  ② 부여 — 사람(관리자 lsy 의 JWT)
    curl -X POST -H "Authorization: Bearer <JWT>" -H "Content-Type: application/json" -d '{"username": "kim", "role": "admin", "reason": "실습"}' http://localhost:5000/api/admin/grant
    → 200 {"msg": "역할 부여 완료", "username": "kim", "old_role": "user", "new_role": "admin", "granted_by": "lsy"}

  ③ 회수 — n8n 이 보내는 모양
    curl -X POST -H "X-API-Key: <ADMIN_API_KEY>" -H "Content-Type: application/json" -d '{"username": "kim", "reason": "허용목록 밖 admin", "student": "lsy", "src_ip": "127.0.0.1"}' http://localhost:5000/api/admin/revoke
    → 200 {"msg": "권한 회수 완료", "username": "kim", "old_role": "admin", "new_role": "user",
           "revoked": true, "event_id": 17, "revoked_by": "apikey"}
    같은 요청을 한 번 더 보내면
    → 200 {"msg": "이미 user 권한(회수 불필요)", "username": "kim", "old_role": "user", "new_role": "user", "revoked": false}

  ④ 인가 실패 — 키도 토큰도 없음 (일반 회원 토큰이어도 똑같다)
    curl "http://localhost:5000/api/admin/users"
    → 401 {"msg": "관리자 인가가 필요합니다(X-API-Key 또는 admin 로그인)."}

  ⑤ IP 차단 → 같은 IP 로 인시던트 만들기
    curl -X POST -H "X-API-Key: <ADMIN_API_KEY>" -H "Content-Type: application/json" -d '{"ip": "203.0.113.7", "reason": "로그인 실패 반복"}' http://localhost:5000/api/admin/block
    curl -X POST -H "X-API-Key: <ADMIN_API_KEY>" -H "Content-Type: application/json" -d '{"src_ip": "203.0.113.7"}' http://localhost:5000/api/admin/incident
    → 201 {"msg": "인시던트 생성", "created": true,
           "incident": {"id": 1, "title": "보안 인시던트: 203.0.113.7 (1건)", "severity": "High",
                        "status": "open", "event_count": 1, "actions": "deny",
                        "summary": "[인시던트 요약] 출발지 203.0.113.7 ...", ...}}

==============================================================================
6. 자주 걸리는 함정
==============================================================================
  ① 403 은 나오지 않는다. 키 틀림·토큰 없음·토큰 만료·일반(또는 gold) 회원 모두 똑같은 401 과 같은 문구다.
     admin_required 의 docstring("아니면 401/403")과 다르다. tests/test_rbac.py 와 admin.html 은 401 을 기준으로 짜여 있다.
  ② 잠긴(is_locked) admin 도 이미 받아 둔 JWT 로는 관리자 API 를 계속 쓸 수 있다.
     잠금 검사는 POST /api/auth/login 에만 있고, 토큰은 최대 2시간 유효하다.
     반대로 role 은 요청마다 DB 에서 읽으므로 revoke 는 다음 요청부터 바로 효과가 있다.
  ③ GET /users?role= 에 목록 밖 값(Admin 처럼 대문자, 오타)을 주면 필터가 조용히 빠져 '전체 회원'이 온다.
     회수봇 find_violations 도 받은 목록의 role 을 다시 확인하지 않으므로, 철자가 바뀌면 일반 회원까지 위반으로 본다.
  ④ /revoke 는 허용목록을 보지 않는다. 키만 있으면 허용목록 안의 admin(강사·본인)도 user 로 내려간다.
     admin 이 JWT 로 자기 자신을 회수하면 다음 요청부터 관리자 API 가 401 이 된다. 복구는 API 키로 /grant.
  ⑤ 기계 호출은 모두 actor='apikey' 로 기록된다. role_granted_by 만 보고는 봇인지 n8n 인지 알 수 없다.
     구분하려면 body 에 source·student 를 보낸다(회수봇은 source='privilege-guard-bot').
  ⑥ 과잉권한을 '만드는' /grant 는 security_events 에 남지 않는다(/unlock·/unblock 도 마찬가지).
     users 표의 role_granted_* 는 다음 변경 때 덮어써지므로, admin 부여 이력은 회수가 일어나야 일지에 보인다.
  ⑦ 잘못된 형식은 400 이 아니라 500 이 된다: body 가 JSON 배열([1, 2] 같은), username·role 이 숫자,
     fail_count·hours·id 가 숫자로 바꿀 수 없는 문자열 등.
     "severity": null 처럼 null 을 명시하면 data.get('severity', 'High') 가 None 을 돌려 NOT NULL 컬럼 저장에 실패한다.
     severity(10자)·source(50자)·ip(45자)·generated_at(32자)는 잘라내지 않아, 길면 MySQL(엄격 모드)에서 오류가 난다
     — 테스트용 SQLite 는 문자열 길이를 검사하지 않아 그냥 통과한다.
  ⑧ /unlock·/unblock 은 원래 상태와 상관없이 200 '해제 완료'다. 오타 난 IP 로 해제해도 성공처럼 보인다.
     /block 은 IP 형식을 검사하지 않는다.
  ⑨ 차단은 문자열이 글자까지 같아야 먹는다. app.py 미들웨어는 X-Forwarded-For 의 '첫 값'으로 비교하지만,
     auth_controller 는 그 헤더 '전체'를 Graylog 로 신고한다. "1.2.3.4, 10.0.0.1" 을 그대로 /block 하면 막히지 않는다.
     또 차단된 IP 도 /api/admin/* 는 계속 호출할 수 있다(의도된 예외).
  ⑩ /incident 의 심각도 비교는 대소문자를 가린다. 'high' 는 순위표에 없어 Low(1) 취급이라 최고 심각도가 못 된다.
     관련 이벤트가 0건이어도 티켓이 만들어진다(최초/최종 None ~ None, 심각도 Low).
     닫힌(closed) 티켓은 찾지 않으므로 같은 IP 로 다시 부르면 새 티켓이 생긴다.
     /incident/close 는 이미 닫힌 티켓에도 200 을 주고 closed_at 을 새 시각으로 덮어쓴다.
  ⑪ API 키를 == 로 비교한다(security_controller 의 require_api_key 도 같다). 실무에서는 비교에 걸리는 시간 차이로
     키를 추측하는 공격을 막으려고 hmac.compare_digest 를 쓴다 — 실습 코드의 한계로 알아 둔다.
  ⑫ source 기본값의 철자가 파일마다 다르다. 이 파일의 lock 은 'login-guard'(하이픈)인데
     models/security_event.py 와 security_controller 의 기본값은 'login_guard'(밑줄)다.
     source 로 거르거나 인시던트 요약의 경로별 건수를 볼 때 두 이름이 따로 집계된다(login-guard×2, login_guard×3).
"""

# ─────────────────────────────────────────────────────────────────────────────
# import
# ─────────────────────────────────────────────────────────────────────────────
# datetime.now() : 부여·잠금·종료 시각 기록 / timedelta : "최근 N시간" 계산(create_incident)
from datetime import datetime, timedelta
# wraps : 데코레이터가 감싼 함수의 이름·docstring 을 보존한다(2절 참고)
from functools import wraps

# Blueprint   : 라우트 묶음
# current_app : 지금 요청을 처리 중인 앱 → config(ADMIN_API_KEY 등) 읽기
# jsonify     : dict → JSON 응답
# request     : 지금 들어온 요청(헤더·쿼리·body)
from flask import Blueprint, current_app, jsonify, request

# db : SQLAlchemy 객체(extensions.py). db.session 으로 조회·저장한다
from extensions import db
# 이 파일이 다루는 표 4개: 차단 IP(blocked_ips) / 인시던트(incidents) / 보안 일지(security_events) / 회원(users)
from models import BlockedIP, Incident, SecurityEvent, User

# 점(.)으로 시작 = 같은 패키지(controllers) 안의 rbac.py
#   VALID_ROLES  : ('user', 'gold', 'admin') — rbac 이 models/user.py 에서 가져와 다시 내보낸다
#   current_user : JWT 가 유효하면 User, 아니면 None (토큰이 깨져도 예외를 내지 않는다)
from .rbac import VALID_ROLES, current_user   # 등급 정의는 rbac 한 곳에서

# 'admin' = 블루프린트 이름 → endpoint 이름이 'admin.list_users' 처럼 된다
# url_prefix='/api/admin' → 아래 route('/users') 의 실제 주소는 /api/admin/users
admin_bp = Blueprint('admin', __name__, url_prefix='/api/admin')

# ('user', 'gold', 'admin') — models/user.py 의 ROLE_LEVEL 에서 온다.
# '|'.join(...) → 'user|gold|admin'. /grant 의 400 오류 문구에 넣는다.
# 등급을 새로 추가하면(models/user.py) 이 문구도 저절로 따라 바뀐다.
ROLE_CHOICES = '|'.join(VALID_ROLES)


# ═════════════════════════════════════════════════════════════════════════════
# _has_valid_key() — 기계 출입증(X-API-Key) 검사
# ─────────────────────────────────────────────────────────────────────────────
# 비유: 창구 경비가 출입증 번호를 장부의 번호와 한 글자씩 대조한다.
#       장부에 번호가 아예 없으면(설정이 비어 있으면) 어떤 출입증도 통과시키지 않는다(fail-closed).
#
# 입력: 없음 (지금 요청의 헤더와 앱 설정을 직접 읽는다)
# 출력: True = 키 일치 / False = 불일치·헤더 없음·설정 비어 있음
# 누가 호출하나: admin_required 의 wrapper (검사 ①)
# ═════════════════════════════════════════════════════════════════════════════
def _has_valid_key():
  """X-API-Key 가 ADMIN_API_KEY 와 일치하면 True(비어 있으면 항상 False = fail-closed)."""
  # config.py: ADMIN_API_KEY 가 비면 SECURITY_API_KEY, 둘 다 비면 ''
  expected = current_app.config.get('ADMIN_API_KEY', '')
  # bool(expected) 가 False(빈 키)면 and 뒤는 보지도 않고 False.
  #   → 설정도 비고 헤더도 없을 때 '' == '' 로 뚫리는 사고를 막는다.
  # 헤더가 없으면 '' 로 비교한다. 헤더 '이름'은 대소문자를 안 가리지만 '값'은 글자까지 같아야 True.
  # (== 비교 — 실무라면 hmac.compare_digest 로 시간차 공격을 막는다. 6절 ⑪)
  return bool(expected) and request.headers.get('X-API-Key', '') == expected


# ═════════════════════════════════════════════════════════════════════════════
# _current_admin_user() — 사람 사원증(JWT) + 직급(admin) 검사
# ─────────────────────────────────────────────────────────────────────────────
# 비유: 사원증(토큰)이 진짜인지 보고, 인사 장부(DB)에서 그 사람 직급이 admin 인지 확인한다.
#       직급은 사원증에 적힌 게 아니라 매번 장부에서 새로 읽는다 → 회수하면 즉시 반영된다.
#
# 입력: 없음 (Authorization: Bearer <JWT> 헤더를 rbac.current_user 가 읽는다)
# 출력: admin 인 User 객체 / 아니면 None (토큰 없음·깨짐·만료·admin 아님 모두 None)
# 누가 호출하나: admin_required 의 wrapper (검사 ②)
# 주의: 계정 잠금(is_locked) 여부는 보지 않는다 (6절 ②)
# ═════════════════════════════════════════════════════════════════════════════
def _current_admin_user():
  """JWT 가 있고 그 계정이 admin 이면 User, 아니면 None."""
  # 토큰 검증 → 토큰 속 id 로 db.session.get(User, id). 어디서든 실패하면 None
  user = current_user()
  # user.is_admin : models/user.py 의 속성 — role == 'admin' 일 때만 True (gold 는 False)
  # 'A if 조건 else B' : 조건이 참이면 A, 거짓이면 B
  return user if (user and user.is_admin) else None


# ═════════════════════════════════════════════════════════════════════════════
# admin_required — 관리자 API 12개 전부에 붙는 '창구 앞 경비' 데코레이터
# ─────────────────────────────────────────────────────────────────────────────
# 비유: 창구 앞 경비. 먼저 기계 출입증을 보고, 없으면 관리자 사원증을 본다.
#       통과시킬 때는 방문 기록지(request.actor)에 "누가 왔는지" 적어서 창구로 들여보낸다.
#
# 입력: fn — 감쌀 뷰 함수 (예: revoke_role)
# 출력: wrapper — 검사가 붙은 새 함수 (Flask 는 이 함수를 주소에 등록한다)
# 누가 호출하나: 파이썬이 이 모듈을 읽을 때 @admin_required 줄마다 한 번씩 호출한다.
#               실제 검사(wrapper)는 HTTP 요청이 들어올 때마다 실행된다.
#
# 결과 요약
#   키 일치            → request.actor = 'apikey'  → fn 실행
#   admin JWT          → request.actor = 아이디    → fn 실행
#   그 밖의 모든 경우  → 401 (403 은 쓰지 않는다 — docstring 의 "401/403" 과 다르다. 6절 ①)
# ═════════════════════════════════════════════════════════════════════════════
def admin_required(fn):
  """유효한 관리자 키(기계) 또는 admin JWT(사람)면 통과. 아니면 401/403."""
  # @wraps(fn) : wrapper 의 이름을 fn 의 이름으로 바꿔 둔다 → Flask endpoint 이름이 겹치지 않는다
  # *args, **kwargs : 뷰 함수가 받는 인자가 무엇이든 그대로 넘기기 위한 형태
  #   (이 파일의 뷰들은 URL 변수가 없어 실제로는 늘 비어 있다)
  @wraps(fn)
  def wrapper(*args, **kwargs):
    # ① 기계 경로 — 키가 맞으면 JWT 는 보지 않는다
    if _has_valid_key():
      # 감사기록용 '누가'. 회수봇·n8n·curl 모두 같은 'apikey' 로 찍힌다
      request.actor = 'apikey'
      # 원래 뷰 함수를 실행하고 그 응답을 그대로 돌려준다
      return fn(*args, **kwargs)
    # ② 사람 경로 — 로그인한 admin 인가?
    admin = _current_admin_user()
    if admin:
      # 감사기록에 관리자 아이디가 남는다 (예: role_granted_by = 'lsy')
      request.actor = admin.username
      return fn(*args, **kwargs)
    # ③ 둘 다 실패 — 로그인 안 함 / 토큰 만료 / 일반·gold 회원 / 키 틀림 → 전부 같은 401
    #    admin.html 은 이 401 을 보고 "이 계정은 admin 이 아닙니다(관리자 권한 필요)." 를 띄운다
    return jsonify({'msg': '관리자 인가가 필요합니다(X-API-Key 또는 admin 로그인).'}), 401
  # 데코레이터는 '검사가 붙은 함수'를 돌려준다 → 위에 쌓인 @admin_bp.route 가 이것을 등록한다
  return wrapper


# ═════════════════════════════════════════════════════════════════════════════
# _allowlist() — 정책 허용목록(admin 을 가져도 되는 아이디들) 정하기
# ─────────────────────────────────────────────────────────────────────────────
# 비유: 인사팀 명단. 창구에 임시 명단을 들고 오면 그것을 쓰고,
#       없으면 사무실 벽에 걸린 공식 명단(.env 의 ADMIN_ALLOWLIST)을 쓴다.
#
# 입력: param — "lsy, instructor,," 같은 쉼표 문자열 또는 None
# 출력: ['lsy', 'instructor'] 같은 리스트 (빈 조각·앞뒤 공백 제거)
# 누가 호출하나: list_violations (GET /violations 의 ?allowlist=)
#   docstring 은 "쿼리/바디" 라고 하지만, 지금 코드에서 부르는 곳은 쿼리 하나뿐이다.
# ═════════════════════════════════════════════════════════════════════════════
def _allowlist(param=None):
  """정책 허용목록. 쿼리/바디로 넘기면 우선, 없으면 config(.env)."""
  # None 이나 '' (빈 문자열)는 거짓 → 아래 config 쪽으로 간다.
  # 그래서 "?allowlist=" 로 '빈 허용목록'을 일부러 넘길 수는 없다.
  if param:
    # config.py 의 ADMIN_ALLOWLIST, 회수봇 cfg() 와 똑같은 자르기 규칙 → 판정 기준이 서로 같다
    return [u.strip() for u in param.split(',') if u.strip()]
  # config.py 가 .env 의 ADMIN_ALLOWLIST 를 이미 리스트로 만들어 둔다. 비어 있으면 [] → 모든 admin 이 위반
  return current_app.config.get('ADMIN_ALLOWLIST', [])


# ═════════════════════════════════════════════════════════════════════════════
# list_users() — GET /api/admin/users : 회원 목록 + 역할
# ─────────────────────────────────────────────────────────────────────────────
# 비유: 관리실 장부 열람. "마스터키 가진 사람만 보여주세요"(?role=admin)처럼 걸러 볼 수도 있다.
#
# 입력: 쿼리 role (선택) — user | gold | admin
# 출력: 200 {"count": N, "users": [User.to_dict(), ...]}  (id 오름차순, password 는 빠져 있다)
# 누가 호출하나:
#   · 회수봇 privilege_revoke_bot.py 의 find_violations → GET /users?role=admin (X-API-Key)
#   · 관리자 페이지 admin.html → 로그인 직후(enterAdmin)·새로고침·부여/회수 뒤 (JWT)
#   · tests/test_rbac.py 의 test_admin_users_list_shows_gold (?role=gold)
# ═════════════════════════════════════════════════════════════════════════════
# 데코레이터 두 줄: 아래(@admin_required)가 먼저 감싸고, 위(route)가 그 결과를 주소에 등록한다
@admin_bp.route('/users', methods=['GET'])
@admin_required
def list_users():
  """회원 목록 + 역할. ?role=admin 으로 필터."""
  # request.args = URL 의 ? 뒤 쿼리 문자열. 없으면 None
  role = request.args.get('role')
  # 아직 실행되지 않은 '조회 준비물'. 조건을 덧붙인 뒤 .all() 에서 SQL 이 실제로 나간다
  q = User.query
  # 정해진 등급 이름일 때만 WHERE role = ... 을 붙인다.
  # 목록 밖 값(None, 'Admin', 오타)이면 조용히 필터 없이 전체가 된다 → 6절 ③
  if role in VALID_ROLES:
    q = q.filter_by(role=role)
  # id 오름차순(가입 순)으로 전부 가져온다
  rows = q.order_by(User.id.asc()).all()
  # 모델 객체는 JSON 으로 바로 못 바꾸므로 to_dict() 로 dict 로 바꿔 담는다
  return jsonify({'count': len(rows), 'users': [u.to_dict() for u in rows]})


# ═════════════════════════════════════════════════════════════════════════════
# list_violations() — GET /api/admin/violations : 정책 위반(허용목록 밖 admin) 목록
# ─────────────────────────────────────────────────────────────────────────────
# 비유: 장부의 마스터키 소지자를 인사팀 명단과 대조한 '위반자 명단'을 창구가 대신 뽑아 준다.
#       회수봇 find_violations 가 봇 쪽에서 하는 계산을 여기서는 서버가 한다.
#
# 입력: 쿼리 allowlist (선택) — "lsy,instructor". 없으면 .env 의 ADMIN_ALLOWLIST
# 출력: 200 {"allowlist": [...], "count": N, "violations": [User.to_dict(), ...]}
# 누가 호출하나:
#   · 관리자 페이지 admin.html '정책 위반 — 허용목록 밖 admin' 의 조회 버튼 (입력칸 값을 ?allowlist= 로)
#   · tests/test_rbac.py 의 test_gold_users_are_not_policy_violations (gold 는 위반 0건)
#   · 회수봇은 이 API 대신 /users?role=admin 을 받아 직접 대조한다
# ═════════════════════════════════════════════════════════════════════════════
@admin_bp.route('/violations', methods=['GET'])
@admin_required
def list_violations():
  """정책 위반(허용목록 밖 admin) 목록. 회수봇이 참고용으로 쓸 수 있다.
  ?allowlist=lsy,instructor 로 기준을 넘기면 그걸 우선 적용."""
  # 쿼리로 준 명단이 우선, 없으면 config(.env) 명단
  allow = _allowlist(request.args.get('allowlist'))
  # 위반 후보는 admin 만. gold 는 과잉권한 정책의 대상이 아니다 (순서 지정 없음)
  admins = User.query.filter_by(role='admin').all()
  # 명단에 없는 admin = 위반. 허용목록이 빈 리스트면 모든 admin 이 여기에 들어간다
  bad = [u for u in admins if u.username not in allow]
  # 어떤 기준(allowlist)으로 판정했는지도 함께 돌려준다 → 화면에서 기준을 확인할 수 있다
  return jsonify({
      'allowlist': allow,
      'count': len(bad),
      'violations': [u.to_dict() for u in bad],
  })


# ═════════════════════════════════════════════════════════════════════════════
# grant_role() — POST /api/admin/grant : 회원에게 역할 부여(인가)
# ─────────────────────────────────────────────────────────────────────────────
# 비유: 마스터키(또는 골드 카드) 지급. 지급 장부에 "누가·언제·왜 줬는지" 도장을 찍는다.
#       이 실습 시나리오에서는 여기서 admin 을 잘못/과하게 줘서 '불필요한 권한'을 일부러 만든다.
#
# 입력(body): username(필수), role(필수: user|gold|admin), reason(선택)
# 출력: 200 부여 결과 / 400 필수값·등급 오류 / 404 없는 사용자
# 누가 호출하나:
#   · 관리자 페이지 admin.html '권한 부여' 버튼 (JWT) → 성공하면 "kim: user → admin" 표시
#   · tests/test_rbac.py 의 set_role 도우미 (X-API-Key) — 테스트 준비용으로 등급을 바꿀 때
# 참고: 같은 등급을 다시 줘도(admin → admin) 부여자·시각·사유가 새로 덮어써진다.
#       내리는 방향(admin → user)도 이 API 로 되지만 security_events 기록은 남지 않는다.
# ═════════════════════════════════════════════════════════════════════════════
@admin_bp.route('/grant', methods=['POST'])
@admin_required
def grant_role():
  """회원에게 역할 부여(인가). body: {username, role, reason}
  시나리오상 여기서 admin 을 잘못/과하게 부여해 '불필요한 권한'을 만든다."""
  # silent=True : body 가 JSON 이 아니거나 비어 있어도 예외 대신 None → or {} 로 빈 dict
  #   → 이상한 요청도 500 이 아니라 아래의 400 으로 끝난다
  data = request.get_json(silent=True) or {}
  # (값 or '') : 키가 없거나 null 이면 '' 로 바꾼 뒤 strip() — None.strip() 에러를 피한다
  username = (data.get('username') or '').strip()
  role = (data.get('role') or '').strip()
  # 아이디가 비었거나, 등급이 정해진 3개 밖(예: 'superuser')이면 400
  #   → tests/test_rbac.py 의 test_grant_rejects_unknown_role 이 확인한다
  if not username or role not in VALID_ROLES:
    return jsonify({'msg': f'username, role({ROLE_CHOICES}) 은 필수입니다.'}), 400

  # 아이디로 회원 1명 찾기. 없으면 None
  user = User.query.filter_by(username=username).first()
  if not user:
    return jsonify({'msg': f'없는 사용자: {username}'}), 404

  # 응답에 '이전 → 이후'를 보여주려고 바꾸기 전 값을 보관
  old = user.role
  # 여기부터는 파이썬 객체의 속성만 바뀐다 — 아직 DB 에는 반영 안 됨
  user.role = role
  # 감사: 누가 줬나. admin_required 가 적어 둔 'apikey' 또는 관리자 아이디
  #   getattr(객체, 이름, 기본값) : 속성이 없을 때(데코레이터를 안 거친 경우 대비) 'unknown'
  user.role_granted_by = getattr(request, 'actor', 'unknown')
  # 감사: 언제 줬나 (서버 PC 의 현지 시각)
  user.role_granted_at = datetime.now()
  # 감사: 왜 줬나. users.role_reason 컬럼이 200자라 [:200] 으로 잘라 저장 실패를 막는다
  user.role_reason = (data.get('reason') or '')[:200]
  # 모아 둔 변경을 한 번에 DB 에 UPDATE
  db.session.commit()
  # 200 과 함께 결과 요약. admin.html 은 old_role → new_role 을 화면에 찍는다
  return jsonify({'msg': '역할 부여 완료', 'username': username,
                  'old_role': old, 'new_role': role,
                  'granted_by': user.role_granted_by}), 200


# ═════════════════════════════════════════════════════════════════════════════
# revoke_role() — POST /api/admin/revoke : 과잉권한 회수(최소권한 복원)
# ─────────────────────────────────────────────────────────────────────────────
# 비유: 마스터키 회수. 키를 돌려받고(role → user), 보안 일지(security_events)에 한 줄 적는다.
#       이미 키가 없는 사람이면 "회수할 게 없다"고만 답하고 일지에는 적지 않는다.
#
# 입력(body): username(필수), reason, student, severity, src_ip, source, generated_at (모두 선택)
# 출력: 200 revoked=true(회수함) / 200 revoked=false(이미 user) / 400 / 404
# 누가 호출하나:
#   · n8n — Graylog 이벤트(rule=priv-unauthorized-admin)를 받아 X-API-Key 로 호출 (원래 경로)
#   · 회수봇 privilege_revoke_bot.py --revoke — 봇이 직접 호출. source='privilege-guard-bot',
#     student·src_ip·reason 을 싣고 severity 는 안 보내므로 기본 'High' 로 기록된다
#   · 관리자 페이지 admin.html '회수'·'즉시 회수' 버튼 (JWT, reason='관리자 페이지 수동 회수')
#   · tests/test_rbac.py 의 test_revoke_gold_back_to_user / test_revoked_gold_loses_access
# 참고: 봇과 n8n 이 같은 계정을 회수하면 먼저 온 쪽만 revoked=true, 나중 쪽은 revoked=false.
# ═════════════════════════════════════════════════════════════════════════════
@admin_bp.route('/revoke', methods=['POST'])
@admin_required
def revoke_role():
  """과잉권한 회수(최소권한 복원) → role 을 'user' 로. n8n 이 호출.
  body: {username, reason, student, severity, src_ip}
  회수가 실제로 일어나면 security_events 에 감사기록(source='privilege-guard')을 남긴다."""
  # body 읽기 — JSON 이 아니어도 빈 dict (grant_role 과 같은 방식)
  data = request.get_json(silent=True) or {}
  username = (data.get('username') or '').strip()
  # 회수는 등급을 받지 않는다 — 목표는 언제나 'user' 이므로 username 만 필수
  if not username:
    return jsonify({'msg': 'username 은 필수입니다.'}), 400

  user = User.query.filter_by(username=username).first()
  if not user:
    return jsonify({'msg': f'없는 사용자: {username}'}), 404

  # 바꾸기 전 등급 (gold 또는 admin 이면 회수 대상)
  old = user.role
  # 누가 회수하나 — 'apikey'(n8n·봇) 또는 관리자 아이디
  actor = getattr(request, 'actor', 'unknown')
  # 멱등 처리: 이미 user 면 아무것도 바꾸지 않고 200 + revoked=False
  if old == 'user':
    # 이미 최소권한 — 변경 없음(감사기록도 남기지 않아 소음 방지)
    return jsonify({'msg': '이미 user 권한(회수 불필요)', 'username': username,
                    'old_role': old, 'new_role': 'user', 'revoked': False}), 200

  # ── 회수 ── gold 든 admin 이든 한 번에 바닥 등급 'user' 로. 허용목록은 여기서 보지 않는다
  user.role = 'user'
  # users 표의 감사 칸: '마지막으로 등급을 바꾼 사람'이 회수자로 덮어써진다
  user.role_granted_by = actor
  user.role_granted_at = datetime.now()
  # 사유가 없으면 'admin→user 회수 by apikey' 같은 문장을 자동으로 만든다 (200자 제한)
  user.role_reason = (data.get('reason') or f'{old}→user 회수 by {actor}')[:200]

  # 감사기록: 대시보드에서 보이도록 security_events 재사용
  # SecurityEvent 는 원래 n8n 이 판정한 허용/거부 결과를 담는 표다(models/security_event.py).
  # 회수 기록용 표를 새로 만들지 않고 칸을 맞춰 끼워 넣는다 → /dashboard 에 '거부' 한 줄로 보인다.
  ev = SecurityEvent(
      # 누구의 실습 기록인가. 안 보내면 actor('apikey' 등). 컬럼이 50자라 자른다
      student=(data.get('student') or actor)[:50],
      # 출발지 IP. 회수는 IP 와 무관할 수 있어 없으면 '0.0.0.0' (NOT NULL 컬럼 채우기)
      src_ip=data.get('src_ip') or '0.0.0.0',
      # 로그인 실패 수는 해당 없음 → 0 / 판정은 '거부(deny)' — 권한을 빼앗는 조치라서
      fail_count=0, decision='deny',
      # 심각도. 키가 없을 때만 'High' (키를 null 로 보내면 None → 저장 실패, 6절 ⑦)
      severity=data.get('severity', 'High'),
      # 사람이 읽는 사유. 없으면 '과잉권한 회수: kim admin→user' 같은 문장 (200자)
      reason=(data.get('reason') or f'과잉권한 회수: {username} {old}→user')[:200],
      # users = 관련 계정 / source = 어느 경로의 기록인가. 기본 'privilege-guard'(n8n 경로)
      #   회수봇은 'privilege-guard-bot' 을 보내 구분한다
      users=username, source=data.get('source', 'privilege-guard'),
      # 보낸 쪽이 만든 시각(문자열). 없으면 None — DB 저장 시각은 created_at 이 따로 채운다
      generated_at=data.get('generated_at'),
  )
  # INSERT 준비
  db.session.add(ev)
  # users UPDATE + security_events INSERT 를 한 트랜잭션으로 확정 (둘 다 되거나 둘 다 안 되거나)
  db.session.commit()
  # commit 뒤라 ev.id(자동 증가 번호)를 알 수 있다 → event_id 로 돌려준다
  # 회수봇은 이 응답을 "회수: admin→user (event 17)" 처럼 출력한다
  return jsonify({'msg': '권한 회수 완료', 'username': username,
                  'old_role': old, 'new_role': 'user', 'revoked': True,
                  'event_id': ev.id, 'revoked_by': actor}), 200


# ═════════════════════════════════════════════════════════════════════════════
# lock_account() — POST /api/admin/lock : 계정 잠금(브루트포스 대응)
# ─────────────────────────────────────────────────────────────────────────────
# 비유: 비밀번호를 계속 틀리는 출입카드를 정지시키고, 정지 사실을 보안 일지에 한 줄 적는다.
#       이미 정지된 카드면 "이미 잠김"이라고만 답한다.
#
# 입력(body): username(필수), reason, student, src_ip, fail_count, severity, source, generated_at
# 출력: 200 changed=true(잠금) / 200 changed=false(이미 잠김) / 400 / 404
# 누가 호출하나: docstring 상 n8n — 로그인 실패 GELF(rule=login-bruteforce)를 Graylog 가 집계한 뒤.
#               저장소 안(화면·봇·테스트)에는 호출하는 코드가 없다.
# 효과: auth_controller 의 login 이 is_locked 를 보고 비밀번호가 맞아도 423 으로 거부한다.
#       단 이미 발급된 JWT 는 막지 않는다 (6절 ②)
# 참고: 기본 source 는 'login-guard'(하이픈). security_events 모델·security_controller 의 기본값은
#       'login_guard'(밑줄)라서, source 로 거를 때 두 철자가 섞여 보인다.
# ═════════════════════════════════════════════════════════════════════════════
@admin_bp.route('/lock', methods=['POST'])
@admin_required
def lock_account():
  """계정 잠금(브루트포스 대응) → is_locked=True. n8n 이 호출.
  body: {username, reason, student, src_ip, fail_count, severity}
  잠금이 실제로 일어나면 security_events 에 감사기록(source='login-guard')을 남긴다."""
  # 앞부분(읽기 → 400 → 404)은 revoke_role 과 같은 틀이다
  data = request.get_json(silent=True) or {}
  username = (data.get('username') or '').strip()
  if not username:
    return jsonify({'msg': 'username 은 필수입니다.'}), 400
  user = User.query.filter_by(username=username).first()
  if not user:
    return jsonify({'msg': f'없는 사용자: {username}'}), 404

  actor = getattr(request, 'actor', 'unknown')
  # 멱등 처리: 이미 잠겼으면 바꾸지 않고 200 + changed=False (감사기록도 없음)
  if user.is_locked:
    return jsonify({'msg': '이미 잠긴 계정', 'username': username,
                    'locked': True, 'changed': False}), 200

  # 잠금 표시 + 언제 + 왜 (사유 기본값 예: '브루트포스 자동 잠금 by apikey', 200자)
  user.is_locked = True
  user.locked_at = datetime.now()
  user.lock_reason = (data.get('reason') or f'브루트포스 자동 잠금 by {actor}')[:200]
  # 보안 일지 1줄 — revoke_role 과 같은 모양. 다른 점은 fail_count 를 받는 것과 기본 source
  ev = SecurityEvent(
      student=(data.get('student') or actor)[:50],
      src_ip=data.get('src_ip') or '0.0.0.0',
      # n8n 이 집계한 실패 횟수를 넘기면 기록한다. int() 라서 "5" 같은 문자열도 된다
      #   (숫자로 못 바꾸는 값이면 ValueError → 500, 6절 ⑦)
      fail_count=int(data.get('fail_count') or 0), decision='deny',
      severity=data.get('severity', 'High'),
      reason=(data.get('reason') or f'계정 잠금: {username} (브루트포스)')[:200],
      users=username, source=data.get('source', 'login-guard'),
      generated_at=data.get('generated_at'),
  )
  db.session.add(ev)
  # users UPDATE + security_events INSERT 를 한 번에 확정
  db.session.commit()
  return jsonify({'msg': '계정 잠금 완료', 'username': username, 'locked': True,
                  'changed': True, 'event_id': ev.id, 'locked_by': actor}), 200


# ═════════════════════════════════════════════════════════════════════════════
# unlock_account() — POST /api/admin/unlock : 계정 잠금 해제
# ─────────────────────────────────────────────────────────────────────────────
# 비유: 정지했던 출입카드를 다시 쓸 수 있게 풀고, 틀린 횟수 표시도 0 으로 되돌린다.
#
# 입력(body): username(필수)
# 출력: 200 (원래 잠겨 있지 않았어도 200) / 400 / 404
# 누가 호출하나: 저장소 안에는 호출하는 코드가 없다 — 운영자가 curl 이나 n8n 에서 직접 호출
# 참고: lock 과 달리 security_events 감사기록을 남기지 않고, locked_at 도 지우지 않는다.
# ═════════════════════════════════════════════════════════════════════════════
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

  # 이미 풀려 있는지 확인하지 않고 그냥 덮어쓴다 (lock·revoke 와 달리 '이미 ~' 분기가 없다)
  user.is_locked = False
  # 화면 표시용 로그인 실패 카운터 초기화 (models/user.py: "표시용(성공 시 0)")
  user.failed_logins = 0
  # 잠금 사유 지우기. locked_at 은 건드리지 않으므로 '마지막으로 잠겼던 시각'이 남는다
  user.lock_reason = None
  db.session.commit()
  # 누가 풀었는지는 응답에만 담긴다 (DB 에는 기록되지 않는다)
  return jsonify({'msg': '잠금 해제 완료', 'username': username, 'locked': False,
                  'unlocked_by': getattr(request, 'actor', 'unknown')}), 200


# ═════════════════════════════════════════════════════════════════════════════
# block_ip() — POST /api/admin/block : 공격 IP 실차단(active response)
# ─────────────────────────────────────────────────────────────────────────────
# 비유: 수상한 방문자(IP)를 출입금지 명단(blocked_ips)에 올린다. 그다음부터는 1층 경비
#       (app.py 미들웨어)가 그 방문자를 입구에서 돌려보낸다(403). 이미 명단에 있으면 "이미 차단"이라고만 답한다.
#
# 입력(body): ip 또는 src_ip(필수), reason, student, severity, fail_count, source, generated_at
# 출력: 200 changed=true(차단) / 200 changed=false(이미 차단) / 400
# 누가 호출하나: docstring 상 n8n. 저장소 안(화면·봇·테스트)에는 호출하는 코드가 없다.
# 효과: app.py 의 _block_ip_guard 가 매 요청 blocked_ips 를 조회 → 있으면 403
#       {"msg": "차단된 IP 입니다(관리자에게 문의).", "ip": ..., "blocked": true}. /api/admin/* 는 예외.
# ═════════════════════════════════════════════════════════════════════════════
@admin_bp.route('/block', methods=['POST'])
@admin_required
def block_ip():
  """공격 IP 실차단(active response) → blocked_ips 에 추가. n8n 이 호출.
  body: {ip, reason, student, severity}. 이후 그 IP 요청은 미들웨어가 403(관리자 API 제외)."""
  data = request.get_json(silent=True) or {}
  # 'ip' 를 먼저 보고 없으면 'src_ip' — 보안 이벤트에서 쓰는 필드 이름(src_ip)을 그대로 넘겨도 되게.
  # 형식(IPv4/IPv6) 검사는 하지 않는다 → 'abc' 도 저장된다 (6절 ⑧)
  ip = (data.get('ip') or data.get('src_ip') or '').strip()
  if not ip:
    return jsonify({'msg': 'ip(또는 src_ip) 는 필수입니다.'}), 400
  actor = getattr(request, 'actor', 'unknown')

  # BlockedIP 의 기본키가 ip 문자열 → 기본키 조회로 '이미 차단됐나'를 확인한다
  if not db.session.get(BlockedIP, ip):
    # 출입금지 명단에 추가. blocked_at 은 모델 기본값(datetime.now)이 채운다
    db.session.add(BlockedIP(ip=ip, reason=(data.get('reason') or f'자동 차단 by {actor}')[:200],
                             blocked_by=actor))
    # 보안 일지 1줄 — src_ip 는 차단한 IP, 관련 계정(users)은 없음(''), 기본 source 는 'ip-guard'
    ev = SecurityEvent(
        student=(data.get('student') or actor)[:50], src_ip=ip,
        fail_count=int(data.get('fail_count') or 0), decision='deny',
        severity=data.get('severity', 'High'),
        reason=(data.get('reason') or f'IP 실차단: {ip}')[:200],
        users='', source=data.get('source', 'ip-guard'),
        generated_at=data.get('generated_at'))
    db.session.add(ev)
    # blocked_ips INSERT + security_events INSERT 를 한 번에 확정
    db.session.commit()
    return jsonify({'msg': 'IP 차단 완료', 'ip': ip, 'blocked': True,
                    'changed': True, 'event_id': ev.id, 'blocked_by': actor}), 200
  # 멱등 처리: 이미 명단에 있으면 아무것도 바꾸지 않는다 (감사기록도 없음)
  return jsonify({'msg': '이미 차단된 IP', 'ip': ip, 'blocked': True, 'changed': False}), 200


# ═════════════════════════════════════════════════════════════════════════════
# unblock_ip() — POST /api/admin/unblock : IP 차단 해제
# ─────────────────────────────────────────────────────────────────────────────
# 비유: 출입금지 명단에서 이름을 지운다. 명단에 없던 이름이어도 "지웠다"고 답한다.
#
# 입력(body): ip 또는 src_ip(필수)
# 출력: 200 (원래 차단 안 된 IP 여도 200) / 400
# 누가 호출하나: 저장소 안에는 호출하는 코드가 없다 — 운영자가 curl 이나 n8n 에서 직접 호출
# 참고: 차단된 IP 에서도 이 API 는 부를 수 있다(app.py 가 /api/admin 을 예외로 둔다).
#       security_events 감사기록은 남기지 않는다.
# ═════════════════════════════════════════════════════════════════════════════
@admin_bp.route('/unblock', methods=['POST'])
@admin_required
def unblock_ip():
  """IP 차단 해제. body: {ip}"""
  data = request.get_json(silent=True) or {}
  # block_ip 와 같은 규칙: ip 우선, 없으면 src_ip
  ip = (data.get('ip') or data.get('src_ip') or '').strip()
  if not ip:
    # 문구에는 src_ip 가 빠져 있지만 src_ip 로 보내도 받아 준다
    return jsonify({'msg': 'ip 는 필수입니다.'}), 400
  # 기본키(ip)로 한 행 찾기
  row = db.session.get(BlockedIP, ip)
  # 있을 때만 DELETE. 없으면 아무 일도 하지 않는다
  if row:
    db.session.delete(row)
    db.session.commit()
  # 삭제했든 안 했든 같은 '해제 완료' 응답 → 오타 난 IP 로 불러도 성공처럼 보인다 (6절 ⑧)
  return jsonify({'msg': '차단 해제 완료', 'ip': ip, 'blocked': False,
                  'unblocked_by': getattr(request, 'actor', 'unknown')}), 200


# ═════════════════════════════════════════════════════════════════════════════
# list_blocked() — GET /api/admin/blocked : 차단된 IP 목록
# ─────────────────────────────────────────────────────────────────────────────
# 비유: 출입금지 명단 열람. 가장 최근에 올린 이름이 맨 위.
#
# 입력: 없음
# 출력: 200 {"count": N, "blocked": [{"ip", "reason", "blocked_by", "blocked_at"}, ...]}
# 누가 호출하나: 저장소 안에는 호출하는 코드가 없다 — curl·n8n 에서 확인용으로 호출
# ═════════════════════════════════════════════════════════════════════════════
@admin_bp.route('/blocked', methods=['GET'])
@admin_required
def list_blocked():
  """차단된 IP 목록."""
  # blocked_at 내림차순 = 최근 차단이 먼저
  rows = BlockedIP.query.order_by(BlockedIP.blocked_at.desc()).all()
  # BlockedIP.to_dict() : blocked_at 은 "2026-09-14T10:20:30" 같은 ISO 형식 문자열
  return jsonify({'count': len(rows), 'blocked': [r.to_dict() for r in rows]})


# ═════════════════════════════════════════════════════════════════════════════
# _SEV_RANK — 심각도 이름 → 순위 숫자 (클수록 심각)
# ─────────────────────────────────────────────────────────────────────────────
# 비유: 사건 등급표. "High 가 Medium 보다 위"를 코드가 비교할 수 있게 숫자로 바꿔 둔다.
# 누가 쓰나: _build_summary 가 '최고 심각도'를 고를 때
# 주의: dict 키는 대소문자를 가린다 — 'high'·'HIGH' 는 표에 없어 기본 1(Low) 취급 (6절 ⑩)
# ═════════════════════════════════════════════════════════════════════════════
_SEV_RANK = {'Low': 1, 'Medium': 2, 'High': 3, 'Critical': 4}


# ═════════════════════════════════════════════════════════════════════════════
# _build_summary() — 보안 일지 여러 줄을 사람이 읽는 '사건 요약서'로 정리
# ─────────────────────────────────────────────────────────────────────────────
# 비유: 한 방문자(IP)에 대한 보안 일지 조각들을 모아 사건 파일 첫 장에 붙일 요약서를 쓴다.
#       "몇 건, 어떤 경로에서, 언제부터 언제까지, 어떤 조치, 가장 심각했던 등급, 그리고 시간순 목록"
#
# 입력: src_ip — 출발지 IP (요약 제목용)
#       events — SecurityEvent 리스트. create_incident 가 created_at 내림차순(최신이 [0])으로 넘긴다
# 출력: (summary, worst, actions, count) 4개짜리 튜플
#       summary 여러 줄 문자열 / worst 최고 심각도 이름 / actions "deny" 같은 조치 문자열(없으면 '없음')
#       count   이벤트 개수
# 누가 호출하나: create_incident 한 곳
#
# 만들어지는 요약 예) — 같은 IP 로 login-guard 2건, ip-guard 1건이 쌓였을 때
#   [인시던트 요약] 출발지 203.0.113.7
#   - 관련 이벤트: 3건 (ip-guard×1, login-guard×2)
#   - 최초/최종: 2026-09-14 10:00:01 ~ 2026-09-14 10:05:12
#   - 취해진 조치: deny
#   - 최고 심각도: High
#   [타임라인]
#   - 2026-09-14 10:05:12 [High/ip-guard] IP 실차단: 203.0.113.7 (users=-)
#   - 2026-09-14 10:03:40 [High/login-guard] 계정 잠금: kim (브루트포스) (users=kim)
#   - ...
# ═════════════════════════════════════════════════════════════════════════════
def _build_summary(src_ip, events):
  """security_events 를 사람이 읽는 인시던트 요약(타임라인·집계·조치)으로 취합."""
  # by_source : {'login-guard': 2, 'ip-guard': 1} 처럼 경로(source)별 건수
  # actions   : 조치 종류 모음. set 이라 같은 값('deny')이 여러 번 나와도 한 번만 남는다
  by_source, actions = {}, set()
  # 최고 심각도 후보. 가장 낮은 'Low' 에서 시작해 더 높은 게 나오면 바꾼다
  worst = 'Low'
  # 타임라인을 한 줄씩 담을 리스트
  lines = []
  # 이벤트를 최신 → 과거 순서로 한 건씩
  for e in events:
    # dict.get(키, 0) + 1 : 처음 보는 source 면 0 에서 시작해 1 증가
    by_source[e.source] = by_source.get(e.source, 0) + 1
    # decision 이 비어 있지 않으면 조치로 모은다 (이 파일이 넣는 값은 모두 'deny')
    if e.decision:
      actions.add(e.decision)
    # 순위 비교: 표에 없는 이름은 1. '보다 클 때만' 바꾸므로 같은 순위면 먼저 본 값(최신)이 남는다
    if _SEV_RANK.get(e.severity, 1) > _SEV_RANK.get(worst, 1):
      worst = e.severity
    # 시각 문자열: DB 저장 시각(created_at)이 있으면 '2026-09-14 10:05:12' 형식,
    #   없으면 보낸 쪽 시각(generated_at), 그것도 없으면 '?'
    when = e.created_at.strftime('%Y-%m-%d %H:%M:%S') if e.created_at else (e.generated_at or '?')
    # 타임라인 한 줄. 사유·계정이 비어 있으면 '' / '-' 로 채운다
    lines.append(f"- {when} [{e.severity}/{e.source}] {e.reason or ''} (users={e.users or '-'})")
  # events 는 최신순이므로 맨 끝([-1])이 가장 오래된 것 = 최초, 맨 앞([0])이 최종.
  # events 가 비어 있으면 'events and ...' 가 거짓이 되어 None → 요약에 "None ~ None" 으로 찍힌다.
  # datetime 을 그대로 문자열로 넣으므로 DB 에 따라(SQLite 등) 소수점 아래 초까지 붙을 수 있다.
  first = events[-1].created_at if events and events[-1].created_at else None
  last = events[0].created_at if events and events[0].created_at else None
  # 경로별 건수를 이름순으로 "ip-guard×1, login-guard×2" 처럼 이어 붙인다
  src_summary = ', '.join(f'{k}×{v}' for k, v in sorted(by_source.items()))
  # 괄호 안에 문자열을 나란히 쓰면 파이썬이 하나로 이어 붙인다(암묵적 연결).
  # 각 줄 끝의 \n 이 줄바꿈 문자라 여러 줄 요약이 된다.
  # '- 취해진 조치' : ', '.join(sorted(actions)) 가 빈 문자열이면 or 뒤의 '없음'
  # 마지막 줄의 + 로 타임라인을 붙인다. lines[:20] = 최신 20줄까지만 (event_count 에는 전체 건수)
  summary = (
      f"[인시던트 요약] 출발지 {src_ip}\n"
      f"- 관련 이벤트: {len(events)}건 ({src_summary})\n"
      f"- 최초/최종: {first} ~ {last}\n"
      f"- 취해진 조치: {', '.join(sorted(actions)) or '없음'}\n"
      f"- 최고 심각도: {worst}\n"
      f"[타임라인]\n" + "\n".join(lines[:20])
  )
  # 튜플로 4개를 한 번에 돌려준다 → 받는 쪽: summary, worst, actions, cnt = ...
  return summary, worst, ', '.join(sorted(actions)) or '없음', len(events)


# ═════════════════════════════════════════════════════════════════════════════
# create_incident() — POST /api/admin/incident : 인시던트 티켓 생성/갱신
# ─────────────────────────────────────────────────────────────────────────────
# 비유: 한 방문자(IP)에 대한 사건 파일을 연다. 이미 열린 파일이 있으면 새로 만들지 않고
#       최근 일지로 요약서를 다시 써서 끼운다(중복 파일 방지).
#
# 입력(body): src_ip 또는 ip(필수), title, severity, student, hours(기본 24)
# 출력: 201 {"msg": "인시던트 생성", "created": true, "incident": {...}}
#       200 {"msg": "인시던트 갱신", "created": false, "incident": {...}} / 400
# 누가 호출하나: docstring 에 호출자가 적혀 있지 않고, 저장소 안(화면·봇·테스트)에서도 부르지 않는다.
#               block·lock 같은 대응 뒤에 curl·n8n 에서 직접 호출하는 용도다.
# 흐름: 최근 hours 시간의 같은 IP 이벤트 조회 → _build_summary → 열린 티켓 찾기(없으면 생성)
#       → 칸 채우기 → commit
# ═════════════════════════════════════════════════════════════════════════════
@admin_bp.route('/incident', methods=['POST'])
@admin_required
def create_incident():
  """인시던트 티켓 생성/갱신. body: {src_ip, title?, severity?, student?, hours?}

  같은 src_ip 의 '열린' 티켓이 있으면 갱신(중복 방지), 없으면 새로 만든다.
  요약은 최근 hours(기본 24) 시간의 security_events 를 자동 취합한다(사람이 읽는 리포트)."""
  data = request.get_json(silent=True) or {}
  # block_ip 와 반대로 src_ip 가 우선, 없으면 ip
  src_ip = (data.get('src_ip') or data.get('ip') or '').strip()
  if not src_ip:
    return jsonify({'msg': 'src_ip 는 필수입니다.'}), 400
  actor = getattr(request, 'actor', 'unknown')
  # 몇 시간 치를 모을지. 없거나 0 이면 24. 숫자로 못 바꾸는 값이면 ValueError → 500 (6절 ⑦)
  hours = int(data.get('hours') or 24)
  # 기준 시각 = 지금 - hours 시간. created_at 도 datetime.now(서버 현지 시각)로 저장되므로 기준이 같다
  since = datetime.now() - timedelta(hours=hours)
  # 같은 IP + 기준 시각 이후 이벤트를 최신순으로 전부.
  #   바깥 괄호로 감싸면 메서드 사슬(.filter().order_by().all())을 여러 줄로 나눠 쓸 수 있다.
  #   filter(A, B) = A AND B. filter_by 와 달리 == · >= 같은 비교식을 쓴다
  events = (SecurityEvent.query
            .filter(SecurityEvent.src_ip == src_ip, SecurityEvent.created_at >= since)
            .order_by(SecurityEvent.created_at.desc()).all())
  # 튜플 풀기: 요약문, 최고 심각도, 조치 문자열, 건수
  summary, worst, actions, cnt = _build_summary(src_ip, events)
  # 요청에 심각도를 주면 그 값, 아니면 계산된 최고 심각도 (이벤트 0건이면 'Low')
  severity = data.get('severity') or worst
  # 제목 기본값 예) '보안 인시던트: 203.0.113.7 (3건)'. incidents.title 이 200자라 자른다
  title = (data.get('title') or f'보안 인시던트: {src_ip} ({cnt}건)')[:200]

  # 같은 IP 의 '열린' 티켓을 찾는다. closed 는 찾지 않으므로 닫힌 뒤에는 새 티켓이 생긴다
  inc = Incident.query.filter_by(src_ip=src_ip, status='open').first()
  # 새로 만들었는지 표시 — 응답 코드(201/200)와 msg 를 고르는 데 쓴다
  created = False
  if not inc:
    # 한 줄에 문장 3개(세미콜론 구분): 객체 만들기 → 세션에 추가 → created 표시
    inc = Incident(src_ip=src_ip, status='open'); db.session.add(inc); created = True
  # 새 티켓이든 기존 티켓이든 아래 칸을 최신 값으로 덮어쓴다(갱신)
  inc.title = title
  inc.severity = severity
  inc.summary = summary
  inc.event_count = cnt
  # incidents.actions 컬럼이 255자라 자른다
  inc.actions = actions[:255]
  inc.student = (data.get('student') or actor)[:50]
  # 새 티켓이면 INSERT, 기존 티켓이면 UPDATE.
  # 값이 하나라도 바뀌어 UPDATE 가 나가면 updated_at 이 지금 시각으로 바뀐다(모델의 onupdate)
  db.session.commit()
  # 조건 표현식 두 개: msg 문구와 상태코드를 created 값에 따라 고른다
  return jsonify({'msg': '인시던트 생성' if created else '인시던트 갱신',
                  'created': created, 'incident': inc.to_dict()}), (201 if created else 200)


# ═════════════════════════════════════════════════════════════════════════════
# list_incidents() — GET /api/admin/incidents : 인시던트 목록
# ─────────────────────────────────────────────────────────────────────────────
# 비유: 사건 파일 서랍 열람. "열린 것만"(?status=open) 또는 "닫힌 것만" 골라 볼 수 있다.
#
# 입력: 쿼리 status (선택) — open | closed. 그 밖의 값·생략이면 전체
# 출력: 200 {"count": N, "incidents": [Incident.to_dict(), ...]}  최근 갱신 순
# 누가 호출하나: 저장소 안에는 호출하는 코드가 없다 — curl·n8n 에서 확인용으로 호출
# ═════════════════════════════════════════════════════════════════════════════
@admin_bp.route('/incidents', methods=['GET'])
@admin_required
def list_incidents():
  """인시던트 목록. ?status=open|closed 로 필터."""
  status = request.args.get('status')
  q = Incident.query
  # list_users 의 role 필터와 같은 방식 — 정해진 값일 때만 조건을 붙인다
  if status in ('open', 'closed'):
    q = q.filter_by(status=status)
  # updated_at 내림차순 = 최근에 갱신된 티켓이 먼저
  rows = q.order_by(Incident.updated_at.desc()).all()
  return jsonify({'count': len(rows), 'incidents': [r.to_dict() for r in rows]})


# ═════════════════════════════════════════════════════════════════════════════
# close_incident() — POST /api/admin/incident/close : 인시던트 종료
# ─────────────────────────────────────────────────────────────────────────────
# 비유: 사건 파일에 '종결' 도장을 찍고 종결 날짜를 적는다. 파일을 버리지는 않는다(삭제 아님).
#
# 입력(body): id — 인시던트 번호 (create_incident 응답의 incident.id)
# 출력: 200 {"msg": "인시던트 종료", "incident": {...}} / 404 {"msg": "없는 인시던트"}
# 누가 호출하나: 저장소 안에는 호출하는 코드가 없다 — curl·n8n 에서 직접 호출
# 참고: 이미 닫힌 티켓이어도 다시 200 이고 closed_at 이 새 시각으로 덮어써진다.
#       닫은 뒤 같은 IP 로 POST /incident 를 부르면 새 티켓이 만들어진다.
# ═════════════════════════════════════════════════════════════════════════════
@admin_bp.route('/incident/close', methods=['POST'])
@admin_required
def close_incident():
  """인시던트 종료(status=closed). body: {id}"""
  data = request.get_json(silent=True) or {}
  # id 가 없으면 0 으로 찾는다 → 번호는 1부터라 0번 티켓은 없으므로 404 (따로 400 검사를 하지 않는다)
  # "3" 같은 문자열도 int() 로 바뀐다. 숫자로 못 바꾸는 값이면 ValueError → 500
  inc = db.session.get(Incident, int(data.get('id') or 0))
  if not inc:
    return jsonify({'msg': '없는 인시던트'}), 404
  # 상태만 바꾼다 — 요약·이벤트 수 등은 그대로 보존(나중에 감사·재발 방지에 쓰는 기록)
  inc.status = 'closed'
  inc.closed_at = datetime.now()
  db.session.commit()
  return jsonify({'msg': '인시던트 종료', 'incident': inc.to_dict()}), 200
