"""[주석·설명용 사본] models/blocked_ip.py — 차단 IP 목록(실차단) 모델

이 파일은 원본 models/blocked_ip.py 를 복사해 주석만 덧붙인 학습용 사본이다.
  · 실행 코드는 원본과 똑같다(주석과 이 설명 문자열만 추가).
  · 원본을 고쳐도 이 사본에는 반영되지 않는다.
  · 앱은 원본 models/blocked_ip.py 를 import 한다(models/__init__.py 경유).
    이 사본은 이름에 공백·하이픈이 있어 import 문으로 불러올 수 없다 — 읽기 전용 교재다.

==============================================================================
0. 한 줄 요약
==============================================================================
  "n8n(SOAR)이 '이 IP 막아!' 하고 적어 넣는 차단 명단 표.
   app.py 미들웨어가 요청마다 이 표를 조회해, 적힌 IP 면 403 으로 돌려보낸다"

==============================================================================
1. 쉬운 비유 — 건물 정문의 '출입 금지 명단'
==============================================================================
  blocked_ips 표          = 정문 경비실 벽에 붙은 출입 금지 명단
  행 1개(BlockedIP)       = 명단 한 줄: 누구(ip) / 왜(reason) / 누가 올렸나(blocked_by) / 언제(blocked_at)
  n8n(SOAR)               = 보안팀 — 공격자를 확인하면 명단에 한 줄 추가(POST /api/admin/block)
  app.py _block_ip_guard  = 정문 경비원 — 방문자마다 명단을 보고, 있으면 돌려보냄(403)
  /api/admin/* 경로       = 관리실 전용 뒷문 — 명단 확인 없이 통과(명단 고칠 사람이 갇히지 않게)

  경비원은 방문자 얼굴(IP 문자열)을 명단과 '글자 그대로' 대조한다.
  같은 동네(같은 대역)의 다른 IP 는 못 알아본다 — 명단에 적힌 그 문자열만 막는다.
  명단에서 지우는 건 POST /api/admin/unblock 이다. 기한이 지나 저절로 풀리는 기능은 없다.

==============================================================================
2. 기본 개념
==============================================================================
  ■ ORM 과 모델 클래스
      ORM(Object-Relational Mapping) = 파이썬 클래스와 DB 표를 짝지어,
      SQL 을 직접 쓰지 않고 객체로 행을 읽고 쓰게 해 주는 도구. 여기서는 SQLAlchemy.
        클래스 BlockedIP          ⇄  표 blocked_ips
        클래스 속성(ip, reason…)  ⇄  컬럼
        객체 1개                  ⇄  행 1개

  ■ db.Model / __tablename__
      db 는 extensions.py 의 SQLAlchemy() 객체. db.Model 을 상속하면 '표 설계도'로 등록된다.
      __tablename__ 은 DB 안의 표 이름. 실제 CREATE TABLE 은 app.py 의 db.create_all() 이 한다.

  ■ 기본키(Primary Key) — 여기서는 '자연키'
      표에서 행 하나를 콕 집는 값. 중복 불가 · NULL 불가.
      다른 모델(User·Post 등)은 의미 없는 번호 id 를 기본키로 쓰지만(대리키),
      이 표는 IP 문자열 자체가 기본키다(자연키).
        → 같은 IP 를 두 번 넣을 수 없다(중복 차단 방지)
        → db.session.get(BlockedIP, '203.0.113.7') 한 번으로 조회 — 기본키 조회는 가장 빠른 조회다

  ■ default (파이썬 쪽 기본값)
      INSERT 할 때 값이 비어 있으면 SQLAlchemy 가 파이썬에서 채워 넣는다.
      CREATE TABLE 문에는 DEFAULT 로 적히지 않는다 → SQL 로 직접 INSERT 하면 적용되지 않는다.

  ■ 실차단(Active Response) / SOAR
      탐지(Graylog 경보)에서 멈추지 않고 '막는 동작'까지 자동으로 하는 것.
      n8n 이 POST /api/admin/block 호출 → 이 표에 행 추가 → 그 IP 의 이후 요청은 앱에 닿지 못한다.

  ■ 미들웨어(before_request)
      app.py 의 @app.before_request 함수 _block_ip_guard 는 모든 라우트보다 먼저 실행된다.
      여기서 응답을 돌려주면 원래 라우트(게시판·로그인 등)는 아예 실행되지 않는다.

  ■ 클라이언트 IP 와 X-Forwarded-For
      app.py _client_ip() 는 X-Forwarded-For 헤더가 있으면 쉼표 앞 첫 값을, 없으면 접속 주소(remote_addr)를 쓴다.
      프록시(nginx·n8n) 뒤에서도 원래 IP 를 보려는 규칙인데, 이 헤더는 클라이언트가 마음대로 적을 수 있다.
      (app.py 에도 "랩 한정 규칙 — 실서비스는 신뢰 프록시 목록으로 검증해야 스푸핑을 막는다" 고 적혀 있다)

  ■ datetime → 문자열 (isoformat)
      to_dict() 는 datetime 을 isoformat() 으로 '2026-09-14T10:15:30' 같은 ISO 8601 문자열로 바꾼다.
      (datetime 을 그대로 jsonify 하면 Flask 는 'Mon, 14 Sep 2026 10:15:30 GMT' 같은 HTTP 날짜 형식으로 바꾼다)

==============================================================================
3. 동작 원리
==============================================================================
  [차단 등록]  admin_controller.block_ip
   n8n ──POST /api/admin/block (헤더 X-API-Key, body {"ip": "203.0.113.7", "reason": "..."})──▶ 게시판
        │ ① db.session.get(BlockedIP, ip) 로 이미 있는지 확인
        │ ② 없으면  BlockedIP 행 추가  +  SecurityEvent 감사기록(source='ip-guard', decision='deny')
        │ ③ commit → 200 {"msg": "IP 차단 완료", "changed": true, "event_id": ...}
        │    이미 있으면 아무것도 바꾸지 않고 200 {"msg": "이미 차단된 IP", "changed": false}
        ▼
  [매 요청 검사]  app.py _block_ip_guard (before_request)
        │ 경로가 /api/admin 으로 시작 → 검사 없이 통과
        │ ip = _client_ip()
        │ db.session.get(BlockedIP, ip) 가 있으면
        │    → 403 {"msg": "차단된 IP 입니다(관리자에게 문의).", "ip": ..., "blocked": true}
        ▼ 없으면 원래 라우트로 진행

  [조회]  GET  /api/admin/blocked           → blocked_at 최신순 [to_dict(), ...]
  [해제]  POST /api/admin/unblock {"ip": ..} → 행 삭제 (없던 IP 여도 200 "차단 해제 완료")

==============================================================================
4. 옵션 설명 — 컬럼별
==============================================================================
  컬럼        파이썬 선언 → MySQL DDL      옵션                    뜻 · 이 값을 준 이유
  ----------  ---------------------------  ----------------------  ------------------------------------------
  ip          db.String(45)                primary_key=True        IP 문자열이 곧 기본키(자연키). 기본키라 자동 NOT NULL.
              → VARCHAR(45) NOT NULL,                              45 = IPv4 가 섞인 IPv6 표기의 최대 길이
                PRIMARY KEY (ip)                                   (ffff:ffff:ffff:ffff:ffff:ffff:255.255.255.255).
                                                                   기본키에는 DB 가 인덱스를 두므로 index=True 가 필요 없다.
  reason      db.String(200)               (없음) → NULL 허용      차단 사유. /block 이 [:200] 로 잘라 넣고,
              → VARCHAR(200)                                       안 보내면 '자동 차단 by <actor>' 로 채운다.
  blocked_by  db.String(80)                (없음) → NULL 허용      누가 차단했나(actor). X-API-Key 호출이면 'apikey',
              → VARCHAR(80)                                        admin 로그인이면 그 아이디.
                                                                   users.username 과 같은 길이(80)라 아이디가 그대로 들어간다.
  blocked_at  db.DateTime                  default=datetime.now    INSERT 순간 파이썬이 서버 PC 현재 시각(시간대 정보 없음)을 채운다.
              → DATETIME                                           DDL 에는 DEFAULT 가 없다(파이썬 쪽 기본값).

  옵션 용어 풀이
    primary_key=True  : 기본키. 중복 불가 + NULL 불가 + 자동 인덱스
    nullable          : 안 적으면 기본키가 아닌 컬럼은 NULL 허용(True)
    default=함수      : datetime.now 처럼 괄호 없이 '함수'를 넘기면 행을 넣을 때마다 호출된다.
                        datetime.now() 로 괄호를 붙이면 파일을 import 한 순간의 시각 하나가 모든 행에 들어간다.
    (unique · index · server_default · ForeignKey · relationship 은 이 모델에 없다)

==============================================================================
5. 예시
==============================================================================
  blocked_ips 표의 행 (IP 는 문서용 예시 대역 203.0.113.x / 198.51.100.x)
    ip              reason              blocked_by   blocked_at
    203.0.113.7     로그인 브루트포스   apikey       2026-09-14 10:15:30
    198.51.100.23   자동 차단 by lsy    lsy          2026-09-14 11:02:05

  to_dict() 결과 = GET /api/admin/blocked 응답 "blocked" 배열의 원소
    {"ip": "203.0.113.7", "reason": "로그인 브루트포스", "blocked_by": "apikey",
     "blocked_at": "2026-09-14T10:15:30"}

  GET /api/admin/blocked 전체 응답 (blocked_at 최신순)
    {"count": 2, "blocked": [{"ip": "198.51.100.23", ...}, {"ip": "203.0.113.7", ...}]}

  사용 코드
    db.session.get(BlockedIP, '203.0.113.7')   # 기본키 조회: 있으면 객체, 없으면 None (app.py)
    db.session.add(BlockedIP(ip='203.0.113.7', reason='로그인 브루트포스', blocked_by='apikey'))

  화면: templates 에는 이 표를 보여 주는 곳이 없다 — API(JSON)로만 확인한다.

==============================================================================
6. 자주 걸리는 함정
==============================================================================
  ① 글자 그대로 비교한다. 대역(CIDR, 예: 203.0.113.0/24) 차단은 안 되고,
     '127.0.0.1' 과 '::1', '1.2.3.4' 와 '::ffff:1.2.3.4' 는 서로 다른 값이다.
  ② X-Forwarded-For 는 위조할 수 있다. 차단된 공격자가 이 헤더에 다른 IP 를 적어 보내면
     _client_ip() 가 그 값을 믿으므로 차단을 피한다(랩 한정 규칙).
  ③ 신고 IP 와 차단 검사 IP 의 모양이 다를 수 있다.
     auth_controller 로그인은 X-Forwarded-For 헤더 '전체'를 src_ip 로 쓰고, 차단 검사는 쉼표 앞 '첫 값'만 쓴다.
     헤더에 IP 가 여러 개('1.1.1.1, 10.0.0.2')인데 그 src_ip 를 그대로 /block 에 넘기면 차단 행이 영영 일치하지 않는다.
  ④ 내 IP(127.0.0.1 등)를 막으면 내 브라우저의 게시판·로그인도 403 이 된다.
     /api/admin/* 는 검사하지 않으므로 X-API-Key 로 POST /api/admin/unblock 을 불러 풀면 된다.
  ⑤ 기한이 없다. blocked_at 은 기록일 뿐, 시간이 지나도 자동 해제되지 않는다.
  ⑥ 요청마다 DB 조회가 한 번 더 생긴다. 랩 규모는 괜찮지만 실서비스는 캐시(Redis)·방화벽(nftables) 계층으로
     올려야 한다고 app.py 설명에 적혀 있다.
  ⑦ 길이 45 는 파이썬이 아니라 DB 가 검사한다. /block 은 ip 를 자르지 않으므로 더 긴 문자열은
     MySQL 이 엄격 모드(8.0 기본값)면 에러, 테스트용 SQLite 는 길이를 검사하지 않아 그대로 들어간다.
  ⑧ MySQL DATETIME(소수 자리 지정 없음)은 초 단위까지만 저장한다.
     SQLite(테스트)에서는 blocked_at 문자열에 마이크로초('.123456')가 붙을 수 있다.
"""
# ─────────────────────────────────────────────────────────────────────────────
# import
# ─────────────────────────────────────────────────────────────────────────────
# datetime.now : blocked_at 기본값(차단 시각)을 만들 함수
from datetime import datetime

# db : extensions.py 에서 만든 SQLAlchemy() 객체. 모든 모델이 이 하나를 같이 쓴다.
#   app.py 가 아니라 extensions.py 에서 가져오므로 순환 import 가 생기지 않는다.
from extensions import db


# ═════════════════════════════════════════════════════════════════════════════
# BlockedIP — 차단된 IP 한 줄 = blocked_ips 표의 행 한 개
# ─────────────────────────────────────────────────────────────────────────────
# 비유: 정문 경비실의 '출입 금지 명단' 한 줄.
# 입력: n8n·관리자가 POST /api/admin/block 으로 보낸 ip·reason (+ 호출자 actor)
# 출력: 표의 행 / to_dict() → GET /api/admin/blocked 응답
# 누가 쓰나: app.py _block_ip_guard(매 요청 조회), admin_controller /block·/unblock·/blocked
# ═════════════════════════════════════════════════════════════════════════════
class BlockedIP(db.Model):
  """차단된 IP 목록(실차단/active response). 미들웨어가 매 요청 이 표를 보고 403.

  n8n(SOAR)이 공격 IP 를 여기에 추가하면, 그 IP 의 이후 요청은 앱에 닿지 못한다.
  """
  # DB 안의 표 이름. SQL 로 확인할 때:  SELECT * FROM blocked_ips;
  __tablename__ = 'blocked_ips'

  # ── 컬럼 ── db.Column(타입, 옵션...) 한 줄 = 표의 열 하나
  # IP 문자열이 곧 기본키(자연키) → 같은 IP 는 한 줄만, db.session.get(BlockedIP, ip) 로 바로 조회.
  # 45자 = ffff:ffff:ffff:ffff:ffff:ffff:255.255.255.255 (IPv4 가 섞인 IPv6 최대 표기)
  ip = db.Column(db.String(45), primary_key=True)   # IPv6 까지 45자
  # 차단 사유 (NULL 허용). /block 이 200자로 잘라 넣는다.
  reason = db.Column(db.String(200))
  # 차단한 주체: 'apikey'(기계 호출) 또는 admin 아이디 (NULL 허용)
  blocked_by = db.Column(db.String(80))
  # 차단 시각. datetime.now 뒤에 괄호가 없다 = 함수 자체를 넘겨 INSERT 때마다 호출하게 한다.
  # 파이썬 쪽 기본값이라 CREATE TABLE 에는 DEFAULT 가 없다.
  blocked_at = db.Column(db.DateTime, default=datetime.now)

  # ═══════════════════════════════════════════════════════════════════════════
  # to_dict() — 행 1개를 JSON 으로 보낼 수 있는 dict 로 바꾼다
  # ───────────────────────────────────────────────────────────────────────────
  # 비유: 명단 한 줄을 '보고서 양식'에 옮겨 적기.
  # 입력: 없음(self)   출력: {'ip', 'reason', 'blocked_by', 'blocked_at'}
  # 누가 쓰나: admin_controller.list_blocked → GET /api/admin/blocked 의 "blocked" 배열
  # ═══════════════════════════════════════════════════════════════════════════
  def to_dict(self):
    return {
        # 문자열 컬럼은 그대로 담는다
        'ip': self.ip, 'reason': self.reason, 'blocked_by': self.blocked_by,
        # datetime 은 ISO 8601 문자열로. None 이면 isoformat() 을 부를 수 없으니 None 그대로.
        #   None 이 되는 때: 아직 INSERT 전(기본값은 저장 순간 채워진다), SQL 로 직접 넣어 NULL 인 행
        'blocked_at': self.blocked_at.isoformat() if self.blocked_at else None,
    }
