"""[주석·설명용 사본] models/security_event.py — 보안 이벤트(판정 결과·감사기록) 모델

이 파일은 원본 models/security_event.py 를 복사해 주석만 덧붙인 학습용 사본이다.
  · 실행 코드는 원본과 똑같다(주석과 이 설명 문자열만 추가).
  · 원본을 고쳐도 이 사본에는 반영되지 않는다.
  · 앱은 원본 models/security_event.py 를 import 한다(models/__init__.py 경유).
    이 사본은 이름에 공백·하이픈이 있어 import 문으로 불러올 수 없다 — 읽기 전용 교재다.
  · 원본에는 모듈 설명이 없어 이 설명 문자열을 새로 붙였다.

==============================================================================
0. 한 줄 요약
==============================================================================
  "n8n 이 내린 허용/거부 판정과, 관리 API 가 한 조치(권한 회수·계정 잠금·IP 차단)를
   한 줄씩 쌓는 보안 일지 표. 보안 대시보드와 인시던트 요약이 이 표를 읽는다"

==============================================================================
1. 쉬운 비유 — 경비실의 '사건 일지'
==============================================================================
  security_events 표     = 경비실 사건 일지
  행 1개(SecurityEvent)  = 일지 한 줄
     student      = 누가 적었나(실습자 이름표)
     src_ip       = 어디서 온 사람인가
     fail_count   = 몇 번 틀렸나
     decision     = 들여보냈나(allow) / 막았나(deny)
     severity     = 얼마나 심각한가
     source       = 어느 순찰 경로에서 나온 기록인가
  n8n                    = 판정을 내리는 보안 요원 — 결과를 적어 달라고 POST
  X-API-Key              = 일지에 쓸 수 있는 요원증(SECURITY_API_KEY)
  보안 대시보드          = 일지를 모아 보는 게시판(수업 확인용이라 열람은 키 없이 가능)
  관리 API               = 조치(회수·잠금·차단)를 할 때마다 같은 일지에 '조치 기록'도 남긴다

  원본 설명: student 를 남겨 두면 제출 증적에 본인 식별자가 찍혀 채점·표절 확인이 쉽다.

==============================================================================
2. 기본 개념
==============================================================================
  ■ ORM · 모델 클래스 · 대리키 id
      class SecurityEvent(db.Model) ⇄ 표 security_events. 객체 1개 = 행 1개.
      id 는 정수 기본키 → MySQL AUTO_INCREMENT. 목록은 id 내림차순(최신 먼저)으로 보여 준다.

  ■ nullable=False — '필수 칸'
      student·src_ip·fail_count·decision·severity 는 NOT NULL. 값 없이 저장하면 DB 가 거절한다.
      (fail_count·severity 는 default 가 있어 ORM 으로 넣을 때는 비워도 채워진다)

  ■ index=True — '찾아보기'
      student(학생별 필터)·src_ip(IP별 집계·인시던트 취합)로 자주 찾아서 인덱스를 걸었다.

  ■ default (파이썬 쪽 기본값)
      값을 안 주면 INSERT 때 SQLAlchemy 가 채운다. CREATE TABLE 에는 DEFAULT 로 적히지 않는다.
      (docs/001 문서에도 "모델의 default 는 DB DDL 에 안 들어간다" 고 정리되어 있다)

  ■ 시각을 두 가지로 남기는 이유
      generated_at = 보낸 쪽(n8n)이 만든 시각 → 문자열 그대로 String(32)
      created_at   = 게시판 DB 에 저장된 시각 → DateTime, 서버가 datetime.now 로 채움
      generated_at 은 형식 검사 없이 문자열로 보관만 하고, created_at 은 DateTime 이라
      인시던트 취합의 시간 범위 조회(created_at >= since)에 쓰인다.

  ■ 감사기록(Audit trail) · 증적
      "누가·언제·무엇을·왜" 를 지우지 않고 쌓아 두는 기록. 나중에 사고를 되짚고 책임을 확인한다.
      이 프로젝트는 권한 회수·계정 잠금·IP 차단 기록도 이 표에 함께 남겨 대시보드에서 보이게 했다.

  ■ API 키 인증과 fail-closed
      POST /api/security/events 는 헤더 X-API-Key 가 SECURITY_API_KEY 와 같을 때만 저장한다.
      설정값이 비어 있으면 무조건 401 — 실수로 열어 두지 않는 쪽으로 실패한다(fail-closed).

  ■ flush 와 commit
      security_controller 는 add → flush → (필요하면 공지글 추가) → commit 순서로 쓴다.
      flush = INSERT 를 DB 로 보내 id 를 받아 오지만 아직 확정은 아님. commit = 확정.
      그래서 이벤트와 자동 공지글이 한 트랜잭션으로 함께 저장되거나 함께 취소된다.

==============================================================================
3. 동작 원리 — 누가 쓰고 누가 읽나
==============================================================================
  [쓰기 ①] 판정 결과 저장 — security_controller.create_security_event
   n8n ──POST /api/security/events (헤더 X-API-Key)──▶ 게시판
        │ student·src_ip·decision(allow|deny) 없으면 400
        │ SecurityEvent(student[:50], src_ip, fail_count=int(...), decision,
        │               severity=요청값 또는 'Low', source=요청값 또는 'login_guard', ...)
        │ add → flush(id 확보)
        │ decision == 'deny' 이고 AUTO_POST_ON_DENY 켜짐 → 게시판 '보안' 공지글도 추가
        │ commit
        ▼ 201 {"id": 42, "student": "lsy", "decision": "deny", "post_id": null}

  [쓰기 ②] 조치 감사기록 — admin_controller (X-API-Key 또는 admin 로그인)
        POST /api/admin/revoke → decision='deny', severity 기본 'High', users=대상 아이디, source 기본 'privilege-guard'
        POST /api/admin/lock   → decision='deny', severity 기본 'High', users=대상 아이디, source 기본 'login-guard'
        POST /api/admin/block  → decision='deny', severity 기본 'High', users='',        source 기본 'ip-guard'
        (실제로 상태가 바뀐 경우에만 기록 — 이미 user·이미 잠김·이미 차단이면 기록하지 않는다)

  [읽기] 모두 키 없이 호출 가능(수업 확인용)
        GET /api/security/events?student=&decision=&limit=  → id 최신순 최대 100건 [to_dict()]  → dashboard.html 표
        GET /api/security/events/summary?student=           → decision 별 건수 + 거부 IP 상위 5(fail_count 합계)
        GET /api/security/students                          → 기록이 있는 student 목록(드롭다운)
        POST /api/admin/incident (관리자)                   → 같은 src_ip 의 최근 hours 시간 이벤트를 인시던트로 취합

==============================================================================
4. 옵션 설명 — 컬럼별
==============================================================================
  컬럼          파이썬 선언 → MySQL DDL                     옵션                        뜻 · 이 값을 준 이유
  ------------  ------------------------------------------  --------------------------  -------------------------------------
  id            db.Integer → INTEGER AUTO_INCREMENT, PK     primary_key=True            기록 번호. 최신순 정렬·to_dict 의 id.
  student       db.String(50)                               nullable=False, index=True  실습자 식별자(필수). 학생별 필터가 잦아 인덱스
                → VARCHAR(50) NOT NULL + ix_..._student                                 (ix_security_events_student). /events 는 [:50] 로 자른다.
  src_ip        db.String(45)                               nullable=False, index=True  출발지 IP(필수). IP별 집계·인시던트 취합에 쓰여 인덱스.
                → VARCHAR(45) NOT NULL + ix_..._src_ip                                  45 = IPv6 최대 표기. 관리 API 는 없으면 '0.0.0.0'.
  fail_count    db.Integer → INTEGER NOT NULL               nullable=False, default=0   실패 횟수. 거부 상위 IP 는 이 값의 합계로 순위.
                                                                                        컨트롤러가 int(값 or 0) 으로 넣는다.
  decision      db.String(10) → VARCHAR(10) NOT NULL        nullable=False              판정: allow | deny. 검사는 /events 에만 있다.
                                                                                        관리 API 기록은 항상 'deny'.
  severity      db.String(10) → VARCHAR(10) NOT NULL        nullable=False,             심각도(Low·Medium·High 등). 대시보드는 High 빨강,
                                                            default='Low'               Medium 주황, 그 밖은 회색으로 칠한다.
  reason        db.String(200) → VARCHAR(200)               (없음) → NULL 허용          사람이 읽는 사유. 관리 API 는 [:200] 로 자른다.
  users         db.String(255) → VARCHAR(255)               (없음)                      관련 계정(시도된 아이디, 회수·잠금 대상 등). 문자열 1칸.
  last_seen     db.String(32) → VARCHAR(32)                 (없음)                      보낸 쪽이 준 '마지막 시도 시각' 문자열.
  window_min    db.Integer → INTEGER                        (없음)                      보낸 쪽이 집계한 시간 구간(분).
  source        db.String(50) → VARCHAR(50)                 default='login_guard'       기록 출처 꼬리표. 컨트롤러도 요청에 없으면
                                                                                        'login_guard' 를 넣는다(관리 API 는 각자 다른 기본값).
  generated_at  db.String(32) → VARCHAR(32)                 (없음)                      보낸 쪽이 만든 시각(문자열 그대로).
  created_at    db.DateTime → DATETIME                      default=datetime.now        DB 에 저장된 시각(게시판 서버 현지 시각).
                                                                                        인시던트 hours 범위 계산의 기준.

  옵션 용어 풀이
    primary_key=True (Integer)  : 기본키 + AUTO_INCREMENT
    nullable=False              : NOT NULL (안 적으면 기본키 제외 NULL 허용)
    index=True                  : ix_<표>_<컬럼> 일반 인덱스(unique 아님 — 같은 학생·같은 IP 행이 여럿이어도 된다)
    default=값 / 함수           : INSERT 때 비어 있으면 파이썬이 채움. DDL 에는 안 나타남
    String(n)                   : 최대 n 글자. 넘치는지는 파이썬이 아니라 DB 가 검사한다
    (unique · server_default · onupdate · ForeignKey · relationship 은 이 모델에 없다)

==============================================================================
5. 예시
==============================================================================
  n8n 이 보내는 요청 (값은 예시 — 실제 값 형식은 n8n 워크플로우가 정한다)
    POST /api/security/events     헤더  X-API-Key: <보안 이벤트 키>
    {"student": "lsy", "src_ip": "203.0.113.7", "decision": "deny", "fail_count": 7,
     "severity": "High", "reason": "5분간 로그인 7회 실패", "users": "admin,kim",
     "last_seen": "2026-09-14T10:14:58", "window_min": 5, "generated_at": "2026-09-14T10:15:00"}

  security_events 표의 행 (출처별 예)
    id  student  src_ip        fail_count  decision  severity  users  source               created_at
    42  lsy      203.0.113.7   7           deny      High      ...    login_guard          2026-09-14 10:15:01
    43  lsy      127.0.0.1     0           deny      High      kim    privilege-guard-bot  2026-09-14 11:00:03
    44  apikey   203.0.113.7   0           deny      High      (빈)   ip-guard             2026-09-14 11:05:10
    · 43 = 회수봇 --revoke 가 직접 회수(봇이 student·src_ip·source 를 보냄)
    · 44 = n8n 이 student 없이 /api/admin/block 호출 → student 칸에 호출자 'apikey'

  to_dict() 결과 = GET /api/security/events 응답 "events" 배열의 원소
    {"id": 42, "student": "lsy", "src_ip": "203.0.113.7", "fail_count": 7,
     "decision": "deny", "severity": "High", "reason": "5분간 로그인 7회 실패",
     "users": "admin,kim", "last_seen": "2026-09-14T10:14:58", "window_min": 5,
     "source": "login_guard", "generated_at": "2026-09-14T10:15:00",
     "created_at": "2026-09-14T10:15:01"}

  dashboard.html 이 표에 쓰는 칸: id · student · src_ip · decision · severity · fail_count · reason · created_at
    (created_at 은 'T' 를 공백으로 바꾸고 앞 19글자만 보여 준다)

  사용 코드
    SecurityEvent.query.filter_by(student='lsy').order_by(SecurityEvent.id.desc()).limit(20).all()
    db.session.query(SecurityEvent.decision, func.count(SecurityEvent.id)).group_by(SecurityEvent.decision).all()
      → 예) [('deny', 5), ('allow', 2)]   (summary API 가 dict 로 바꿔 by_decision 으로 보낸다)

==============================================================================
6. 자주 걸리는 함정
==============================================================================
  ① 읽기 API 3종(/events·/events/summary·/students)은 키 없이 누구나 호출된다(수업 확인용).
     IP·아이디·사유가 그대로 공개되므로 실서비스라면 인증을 붙여야 한다.
  ② decision 이 allow|deny 인지는 POST /api/security/events 만 검사한다. DB 에는 그런 제약이 없다.
     관리 API 기록(회수·잠금·차단)은 모두 'deny' 라서 대시보드 '거부' 건수에 함께 잡힌다.
  ③ source 이름이 섞여 있다: 기본값 'login_guard'(밑줄) / 잠금 'login-guard'(하이픈) /
     'privilege-guard' / 'ip-guard' / 회수봇 'privilege-guard-bot'. 출처로 거를 때 철자를 정확히 맞춘다.
  ④ String(n) 길이는 DB 가 검사한다. /events 는 student 만 50자로 자르고 src_ip·severity·users·last_seen·
     source·generated_at 등은 자르지 않는다 → 긴 값이 오면 MySQL 엄격 모드(8.0 기본값)에서 저장 에러(500),
     테스트용 SQLite 는 길이를 검사하지 않아 통과한다.
  ⑤ last_seen·generated_at 은 DateTime 이 아니라 문자열이다. 형식 검사도, 시각 계산도 없다.
     '2026-09-14T10:15:30.123456+09:00' 이 딱 32자 — 이보다 긴 형식은 ④에 걸린다.
  ⑥ fail_count·severity 의 default 는 파이썬 쪽이라 DDL 에 DEFAULT 가 없다.
     SQL 로 직접 INSERT 하면서 이 칸을 빼면 NOT NULL 인데 기본값이 없어 거절된다(엄격 모드).
  ⑦ created_at(게시판 서버 시각)과 generated_at(보낸 쪽 시각)은 다를 수 있다.
     인시던트 취합(hours 범위)과 대시보드 '저장 시각'은 created_at 기준이다.
  ⑧ 관리 API 를 src_ip 없이 부르면 src_ip 가 '0.0.0.0' 으로 저장된다(회수·잠금).
     이 값이 거부 기록으로 쌓여 대시보드 '거부 상위 IP' 에 0.0.0.0 이 섞여 보일 수 있다.
"""
# ─────────────────────────────────────────────────────────────────────────────
# import
# ─────────────────────────────────────────────────────────────────────────────
# datetime.now : created_at(DB 저장 시각)의 기본값을 만들 함수
from datetime import datetime

# db : extensions.py 의 SQLAlchemy() 객체(모든 모델이 공유)
from extensions import db


# ═════════════════════════════════════════════════════════════════════════════
# SecurityEvent — 보안 일지 한 줄 = security_events 표의 행 한 개
# ─────────────────────────────────────────────────────────────────────────────
# 비유: 경비실 사건 일지의 한 줄(누가·어디서·몇 번·판정·심각도·출처·언제).
# 입력: n8n 의 POST /api/security/events 본문, 또는 관리 API(회수·잠금·차단)가 만든 감사기록
# 출력: 표의 행 / to_dict() → GET /api/security/events 응답 → 보안 대시보드
# 누가 쓰나: security_controller(저장·조회·요약·학생 목록),
#            admin_controller(revoke·lock·block 감사기록, create_incident 취합)
# ═════════════════════════════════════════════════════════════════════════════
class SecurityEvent(db.Model):
  """n8n 이 판정한 허용/거부 결과를 저장하는 표.

  student 를 남겨 두면 제출 증적에 본인 식별자가 찍혀 채점·표절 확인이 쉽다.
  """
  # DB 안의 표 이름. SQL 로 확인할 때:  SELECT * FROM security_events ORDER BY id DESC;
  __tablename__ = 'security_events'

  # ── 식별 ──
  # 기록 번호(대리키). 정수 기본키 → MySQL AUTO_INCREMENT
  id = db.Column(db.Integer, primary_key=True)
  # 누가 제출한 기록인가(필수). ?student= 필터·학생 목록에 쓰여 인덱스
  student = db.Column(db.String(50), nullable=False, index=True)   # 본인 식별자(필수)
  # 어디서 온 요청인가(필수). IP별 집계·인시던트 취합에 쓰여 인덱스
  src_ip = db.Column(db.String(45), nullable=False, index=True)    # IPv6 까지 45자

  # ── 판정 ──
  # 실패 횟수(필수). 안 주면 INSERT 때 파이썬이 0. 거부 상위 IP 순위는 이 값의 합계
  fail_count = db.Column(db.Integer, nullable=False, default=0)
  # 허용/거부(필수). 기본값이 없다 — /events 는 allow|deny 가 아니면 400, 관리 API 는 'deny' 를 넣는다
  decision = db.Column(db.String(10), nullable=False)              # allow | deny
  # 심각도(필수). 안 주면 파이썬이 'Low'. 관리 API 는 요청에 없으면 'High' 를 직접 넣는다
  severity = db.Column(db.String(10), nullable=False, default='Low')

  # ── 맥락(모두 NULL 허용) ──
  # 사람이 읽는 사유
  reason = db.Column(db.String(200))
  # 관련 계정(시도된 아이디 목록, 회수·잠금 대상 아이디 등)을 문자열 한 칸에
  users = db.Column(db.String(255))
  # 보낸 쪽이 알려 준 '마지막 시도 시각' — 형식을 모르므로 문자열로 받는다
  last_seen = db.Column(db.String(32))
  # 보낸 쪽이 집계한 시간 구간(분)
  window_min = db.Column(db.Integer)
  # 기록 출처 꼬리표. 기본값 'login_guard'(밑줄) — 관리 API 는 'login-guard'·'privilege-guard'·'ip-guard' 를 쓴다
  source = db.Column(db.String(50), default='login_guard')

  # ── 시각 2종 ──
  # 보낸 쪽 시각(문자열 그대로) vs DB 저장 시각(서버가 datetime.now 로 채우는 DateTime)
  generated_at = db.Column(db.String(32))                          # 보낸 쪽이 만든 시각
  created_at = db.Column(db.DateTime, default=datetime.now)        # DB 저장 시각

  # ═══════════════════════════════════════════════════════════════════════════
  # to_dict() — 일지 한 줄을 JSON 으로 보낼 수 있는 dict 로
  # ───────────────────────────────────────────────────────────────────────────
  # 비유: 일지 한 줄을 대시보드 게시판용 카드에 옮겨 적기.
  # 입력: 없음(self)   출력: 컬럼 13개를 담은 dict (created_at 만 ISO 8601 문자열로 변환)
  # 누가 쓰나: security_controller.list_security_events → GET /api/security/events 의 "events" 배열
  # ═══════════════════════════════════════════════════════════════════════════
  def to_dict(self):
    return {
        # 식별·판정 — 컬럼 값 그대로
        'id': self.id, 'student': self.student, 'src_ip': self.src_ip,
        'fail_count': self.fail_count, 'decision': self.decision,
        'severity': self.severity, 'reason': self.reason, 'users': self.users,
        # last_seen·generated_at 은 이미 문자열이라 변환 없이 그대로
        'last_seen': self.last_seen, 'window_min': self.window_min,
        'source': self.source, 'generated_at': self.generated_at,
        # created_at 은 datetime → '2026-09-14T10:15:01' 형태로. None 이면 None(JSON null)
        #   None 인 때: 아직 INSERT 전(기본값은 저장 순간 채워진다), SQL 로 직접 넣어 NULL 인 행
        'created_at': self.created_at.isoformat() if self.created_at else None,
    }
