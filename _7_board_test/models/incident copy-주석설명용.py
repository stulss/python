"""[주석·설명용 사본] models/incident.py — 보안 인시던트(사고) 티켓 모델

이 파일은 원본 models/incident.py 를 복사해 주석만 덧붙인 학습용 사본이다.
  · 실행 코드는 원본과 똑같다(주석과 이 설명 문자열만 추가).
  · 원본을 고쳐도 이 사본에는 반영되지 않는다.
  · 앱은 원본 models/incident.py 를 import 한다(models/__init__.py 경유).
    이 사본은 이름에 공백·하이픈이 있어 import 문으로 불러올 수 없다 — 읽기 전용 교재다.

==============================================================================
0. 한 줄 요약
==============================================================================
  "같은 출발지 IP 에서 벌어진 보안 이벤트(security_events)들을 한 장의 '사고 티켓'으로 묶어,
   무슨 일이 언제 있었고 어떤 조치를 했는지 추적하는 표"

==============================================================================
1. 쉬운 비유 — 병원의 '진료 차트'
==============================================================================
  security_events 행 1개           = 그때그때 나온 검사 결과지 한 장
  incidents 행 1개(Incident)       = 환자(출발지 IP) 한 명의 진료 차트
  status  open / closed            = 진료 중 / 퇴원
  summary                          = 차트 요약란(결과지를 시간순으로 옮겨 적은 것)
  POST /api/admin/incident         = "차트 정리해 주세요" — 진료 중 차트가 있으면 고쳐 쓰고, 없으면 새 차트
  POST /api/admin/incident/close   = 퇴원 처리(closed_at 기록)

  같은 환자의 '진료 중' 차트는 하나만 둔다(중복 방지). 퇴원한 뒤 다시 오면 새 차트를 연다.
  요약란은 사람이 손으로 쓰지 않는다 — 최근 N시간(기본 24)의 결과지를 모아 매번 새로 쓴다.

==============================================================================
2. 기본 개념
==============================================================================
  ■ 인시던트(사고) 티켓 — 원본 설명
      탐지·대응(잠금/차단) 후 '무슨 일이 언제, 무엇을 했나'를 한 건의 추적 단위로 남긴다.
      실무의 티켓(Jira/ServiceNow)·SIR 의 축소판 — 감사·재발방지·인계에 쓴다.
      같은 출발지(src_ip)의 '열린' 티켓은 하나만 두고(중복 방지) 이벤트가 쌓이면 갱신한다.

  ■ 이벤트 vs 인시던트
      이벤트   = 낱개 기록 (security_events 한 행: 로그인 경보, 계정 잠금, IP 차단, 권한 회수…)
      인시던트 = 여러 이벤트를 묶어 사람이 열고 닫는 관리 단위 (incidents 한 행)
      둘은 외래키로 연결되지 않는다. 'src_ip 가 같고 최근 hours 시간 안' 이라는 조건으로 그때그때 묶는다.

  ■ ORM 모델 · 대리키 id
      class Incident(db.Model) ⇄ 표 incidents. 객체 1개 = 행 1개.
      id = db.Column(db.Integer, primary_key=True) → MySQL 에서 AUTO_INCREMENT(1, 2, 3… 자동 번호).

  ■ 인덱스(index=True)
      책 뒤의 '찾아보기'. 그 컬럼으로 찾는 쿼리가 빨라진다. 대신 INSERT·UPDATE 때 인덱스도 고쳐야 한다.
      이 모델은 자주 찾는 src_ip(열린 티켓 찾기)·status(목록 필터)에 걸었다.

  ■ String vs Text
      String(n) = VARCHAR(n): 길이 제한이 있는 짧은 값.  Text = TEXT: 긴 글(MySQL TEXT 최대 65,535 바이트).

  ■ default 와 onupdate (둘 다 파이썬 쪽)
      default  = INSERT 할 때 값이 비어 있으면 파이썬이 채운다.
      onupdate = ORM 이 이 행에 UPDATE 문을 보낼 때 파이썬이 채운다.
      둘 다 CREATE TABLE 에는 나타나지 않는다 → SQL 로 직접 넣거나 고치면 적용되지 않는다.

  ■ 수명주기(status)
      open ──/incident/close──▶ closed.  닫힌 티켓을 다시 여는 API 는 없다.

==============================================================================
3. 동작 원리 — admin_controller.create_incident
==============================================================================
   n8n·관리자 ──POST /api/admin/incident {"src_ip": "203.0.113.7", "hours": 24}──▶ 게시판
        │ (헤더 X-API-Key 또는 admin 로그인 — admin_required)
        │
        │ ① since = 지금 - hours(기본 24)시간
        │ ② security_events 에서 src_ip 가 같고 created_at >= since 인 행을 최신순으로 전부 조회
        │ ③ _build_summary() 가 네 가지를 만든다
        │      summary : 사람이 읽는 요약 + 타임라인(최대 20줄)
        │      worst   : 이벤트 중 최고 심각도 (Low < Medium < High < Critical, 이벤트 0건이면 'Low')
        │      actions : 이벤트들의 decision 값 모음 ('deny' / 'allow, deny' / '없음')
        │      cnt     : 이벤트 건수
        │ ④ severity = 요청의 severity, 없으면 worst
        │    title    = 요청의 title, 없으면 '보안 인시던트: <ip> (<cnt>건)'  (200자로 자름)
        │ ⑤ Incident.query.filter_by(src_ip=..., status='open').first()
        │      없으면 → Incident(src_ip=..., status='open') 를 새로 add (created = True)
        │ ⑥ title · severity · summary · event_count · actions · student 를 덮어쓰고 commit
        ▼
   201(새로 만듦) 또는 200(갱신)
     {"msg": "인시던트 생성" | "인시던트 갱신", "created": true | false, "incident": to_dict()}

   GET  /api/admin/incidents?status=open|closed  → updated_at 최신순 목록
   POST /api/admin/incident/close {"id": 3}       → status='closed', closed_at=지금

==============================================================================
4. 옵션 설명 — 컬럼별
==============================================================================
  컬럼         파이썬 선언 → MySQL DDL           옵션                        뜻 · 이 값을 준 이유
  -----------  --------------------------------  --------------------------  -----------------------------------------
  id           db.Integer                        primary_key=True            티켓 번호. DB 가 자동으로 매긴다.
               → INTEGER AUTO_INCREMENT                                      /incident/close 가 db.session.get 으로 찾는다.
  title        db.String(200)                    nullable=False              이 모델의 유일한 필수 컬럼(비면 INSERT 실패).
               → VARCHAR(200) NOT NULL                                       컨트롤러가 항상 채운다(없으면 자동 제목).
  src_ip       db.String(45)                     index=True                  사고 출발지 IP. '같은 IP 의 열린 티켓' 찾기 조건이라 인덱스.
               → VARCHAR(45) + ix_incidents_src_ip                           45 = IPv6 최대 표기. NULL 허용이지만 컨트롤러는 없으면 400.
  severity     db.String(10)                     default='Medium'            Low | Medium | High | Critical (최대 8글자).
               → VARCHAR(10)                                                 create_incident 는 늘 값을 넣으므로(요청값 또는 worst)
                                                                             현재 API 경로에서 'Medium' 기본값이 쓰일 일은 없다.
  status       db.String(12)                     default='open', index=True  open | closed. 새 티켓은 open.
               → VARCHAR(12) + ix_incidents_status                           열린 티켓 찾기·목록 필터(?status=)에 쓰여 인덱스.
  summary      db.Text                           (없음)                      자동 취합 요약(여러 줄). 길어질 수 있어 Text.
               → TEXT                                                        타임라인은 최대 20줄로 자른다.
  event_count  db.Integer                        default=0                   취합한 security_events 건수.
               → INTEGER                                                     갱신 때마다 '최근 hours 시간' 기준으로 다시 센 값으로 덮어쓴다.
  actions      db.String(255)                    (없음)                      취해진 조치 요약. 실제로는 decision 값 모음.
               → VARCHAR(255)                                                컨트롤러가 255자로 자른다.
  student      db.String(50)                     (없음)                      실습자 식별자. 요청의 student, 없으면 호출자(actor:
               → VARCHAR(50)                                                 'apikey' 또는 admin 아이디). 50자로 자른다.
  created_at   db.DateTime                       default=datetime.now        티켓을 처음 INSERT 한 시각.
               → DATETIME
  updated_at   db.DateTime                       default=datetime.now,       만들 때 한 번 + ORM 이 이 행을 UPDATE 할 때마다 현재 시각.
               → DATETIME                        onupdate=datetime.now       목록(GET /api/admin/incidents) 정렬 기준.
  closed_at    db.DateTime                       (없음)                      종료 시각. /incident/close 가 채운다. 열린 티켓은 NULL.
               → DATETIME

  옵션 용어 풀이
    primary_key=True (Integer)  : 기본키 + MySQL AUTO_INCREMENT(자동 번호)
    nullable=False              : NOT NULL. 안 적으면(기본키 제외) NULL 허용
    index=True                  : ix_<표>_<컬럼> 이름의 일반 인덱스. unique 가 아니므로 같은 값이 여러 행에 있어도 된다
    default=값 또는 함수        : INSERT 때 비어 있으면 파이썬이 채움. DDL 에는 안 나타남
    onupdate=함수               : UPDATE 문을 보낼 때 파이썬이 채움. DDL 에는 안 나타남
    datetime.now (괄호 없음)    : 함수 자체를 넘겨서 행을 넣고 고칠 때마다 그 순간 시각을 쓴다
    (unique · server_default · ForeignKey · relationship 은 이 모델에 없다)

==============================================================================
5. 예시
==============================================================================
  incidents 표의 행 (IP 는 문서용 예시 대역)
    id  title                            src_ip        severity  status  event_count  actions  student  closed_at
    3   보안 인시던트: 203.0.113.7 (3건)  203.0.113.7   High      open    3            deny     apikey   NULL

  summary 칸에 실제로 들어가는 모양 (_build_summary 형식, 타임라인은 최신순)
    [인시던트 요약] 출발지 203.0.113.7
    - 관련 이벤트: 3건 (ip-guard×1, login-guard×1, login_guard×1)
    - 최초/최종: 2026-09-14 10:00:00 ~ 2026-09-14 10:05:00
    - 취해진 조치: deny
    - 최고 심각도: High
    [타임라인]
    - 2026-09-14 10:05:00 [High/ip-guard] IP 실차단: 203.0.113.7 (users=-)
    - 2026-09-14 10:03:00 [High/login-guard] 계정 잠금: kim (브루트포스) (users=kim)
    - 2026-09-14 10:00:00 [Medium/login_guard] <n8n 이 보낸 사유> (users=kim)

  to_dict() 결과 — POST /api/admin/incident 와 /incident/close 응답의 "incident",
                   GET /api/admin/incidents 응답 "incidents" 배열의 원소
    {"id": 3, "title": "보안 인시던트: 203.0.113.7 (3건)", "src_ip": "203.0.113.7",
     "severity": "High", "status": "open",
     "summary": "[인시던트 요약] 출발지 203.0.113.7 ... (줄바꿈이 들어간 긴 문자열)",
     "event_count": 3, "actions": "deny", "student": "apikey",
     "created_at": "2026-09-14T10:06:00", "updated_at": "2026-09-14T10:06:00",
     "closed_at": null}

  사용 코드
    Incident.query.filter_by(src_ip='203.0.113.7', status='open').first()   # 열린 티켓 찾기
    db.session.get(Incident, 3)                                           # 번호로 찾기(/incident/close)

  화면: templates 에는 인시던트를 보여 주는 곳이 없다 — API(JSON)로만 확인한다.

==============================================================================
6. 자주 걸리는 함정
==============================================================================
  ① '열린 티켓은 IP 당 하나' 는 코드(먼저 조회 → 없으면 추가)로만 지킨다. DB 에 unique 제약이 없어서
     같은 IP 로 거의 동시에 두 번 호출되면 열린 티켓이 2개 생길 수 있다.
  ② event_count·summary 는 누적이 아니라 '최근 hours 시간'으로 매번 다시 계산해 덮어쓴다.
     오래 열어 둔 티켓을 나중에 갱신하면 건수가 줄 수 있고, severity 도 새 값으로 덮여 낮아질 수 있다.
  ③ actions 주석은 '잠금/차단 등' 이라고 하지만 실제로 들어가는 건 이벤트의 decision 값뿐이다.
     잠금·차단 감사기록도 decision='deny' 라서 'deny' 로만 보인다 → 무슨 조치였는지는 summary 의 출처 집계를 본다.
  ④ 출처(source) 이름이 섞여 있다: 로그인 경보 기본값 'login_guard'(밑줄) vs 계정 잠금 'login-guard'(하이픈).
     요약 집계에서 서로 다른 출처로 따로 센다.
  ⑤ updated_at(onupdate)은 ORM 이 실제로 UPDATE 문을 보낼 때만 바뀐다. 갱신 호출이어도 모든 값이
     이전과 같으면 UPDATE 가 나가지 않아 시각도 그대로다. SQL 로 직접 고친 경우에도 바뀌지 않는다.
  ⑥ 닫힌 티켓을 다시 여는 API 는 없다. 같은 IP 로 다시 /incident 를 부르면 새 티켓이 열린다.
     이미 닫힌 티켓에 /incident/close 를 또 부르면 closed_at 이 새 시각으로 덮인다.
  ⑦ severity 는 요청값을 자르지 않고 넣는다. String(10) 을 넘는 값은 MySQL 이 엄격 모드(8.0 기본값)면 에러,
     테스트용 SQLite 는 길이를 검사하지 않아 통과한다.
  ⑧ 시각은 모두 게시판 서버 PC 의 현지 시각(시간대 정보 없음)이다. security_events.created_at 도 같은 기준이라
     hours 범위 계산은 맞지만, 다른 PC(n8n 등)가 만든 시각과 비교할 때는 시간대를 확인한다.
"""
# ─────────────────────────────────────────────────────────────────────────────
# import
# ─────────────────────────────────────────────────────────────────────────────
# datetime.now : created_at·updated_at 의 기본값/갱신값을 만들 함수
from datetime import datetime

# db : extensions.py 의 SQLAlchemy() 객체(모든 모델이 공유)
from extensions import db


# ═════════════════════════════════════════════════════════════════════════════
# Incident — 보안 사고 티켓 1건 = incidents 표의 행 한 개
# ─────────────────────────────────────────────────────────────────────────────
# 비유: 환자(출발지 IP) 한 명의 진료 차트.
# 입력: POST /api/admin/incident 의 src_ip·title·severity·student·hours
#       + 그 IP 의 최근 security_events 를 취합한 결과
# 출력: 표의 행 / to_dict() → /api/admin/incident·/incidents·/incident/close 응답
# 누가 쓰나: admin_controller.create_incident · list_incidents · close_incident
# ═════════════════════════════════════════════════════════════════════════════
class Incident(db.Model):
  """보안 인시던트(사고) 티켓.

  탐지·대응(잠금/차단) 후 '무슨 일이 언제, 무엇을 했나'를 한 건의 추적 단위로
  남긴다. 실무의 티켓(Jira/ServiceNow)·SIR 의 축소판 — 감사·재발방지·인계에 쓴다.
  같은 출발지(src_ip)의 '열린' 티켓은 하나만 두고(중복 방지) 이벤트가 쌓이면 갱신한다.
  """
  # DB 안의 표 이름
  __tablename__ = 'incidents'

  # ── 식별 ──
  # 티켓 번호(대리키). 정수 기본키 → MySQL AUTO_INCREMENT 로 자동 번호
  id = db.Column(db.Integer, primary_key=True)
  # 제목 — 이 모델의 유일한 NOT NULL 컬럼. 컨트롤러가 없으면 '보안 인시던트: <ip> (<n>건)' 로 채운다
  title = db.Column(db.String(200), nullable=False)
  # 출발지 IP. 열린 티켓을 IP 로 찾으므로 인덱스(ix_incidents_src_ip)
  src_ip = db.Column(db.String(45), index=True)

  # ── 분류·상태 ──
  # 심각도. 기본값 'Medium' 은 파이썬 쪽 값이며, create_incident 는 항상 값을 직접 넣는다
  severity = db.Column(db.String(10), default='Medium')     # Low|Medium|High|Critical
  # 상태. 새 티켓은 open, /incident/close 가 closed 로 바꾼다. 필터에 쓰여 인덱스(ix_incidents_status)
  status = db.Column(db.String(12), default='open', index=True)  # open|closed

  # ── 내용(자동 취합) ──
  # 긴 여러 줄 요약이라 Text. _build_summary() 가 만든 문자열이 통째로 들어간다(타임라인 최대 20줄)
  summary = db.Column(db.Text)          # 자동 취합된 사람이 읽는 요약(타임라인·조치)
  # 최근 hours 시간 안의 이벤트 건수. 갱신 때 다시 센 값으로 덮어쓴다(누적 아님)
  event_count = db.Column(db.Integer, default=0)  # 취합한 security_events 개수
  # 실제로는 이벤트 decision 값 모음('deny', 'allow, deny', '없음'). 컨트롤러가 255자로 자른다
  actions = db.Column(db.String(255))   # 취해진 조치 요약(deny/allow, 잠금/차단 등)
  # 실습자 식별자(요청의 student, 없으면 호출자 actor). 컨트롤러가 50자로 자른다
  student = db.Column(db.String(50))

  # ── 시각 3종 ── 모두 서버 PC 현지 시각(시간대 정보 없음)
  # 처음 INSERT 한 시각 (괄호 없는 datetime.now = 저장할 때마다 호출)
  created_at = db.Column(db.DateTime, default=datetime.now)
  # INSERT 때 default, 이후 ORM 이 UPDATE 문을 보낼 때마다 onupdate 로 다시 채움 → 목록 정렬 기준
  updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)
  # 종료 시각. 열린 동안 NULL, /incident/close 가 채운다
  closed_at = db.Column(db.DateTime)

  # ═══════════════════════════════════════════════════════════════════════════
  # to_dict() — 티켓 1건을 JSON 으로 보낼 수 있는 dict 로
  # ───────────────────────────────────────────────────────────────────────────
  # 비유: 진료 차트를 '보고서 양식'에 옮겨 적기.
  # 입력: 없음(self)   출력: 컬럼 12개를 담은 dict (시각은 ISO 8601 문자열 또는 None)
  # 누가 쓰나: admin_controller — POST /api/admin/incident("incident"),
  #            GET /api/admin/incidents("incidents" 배열), POST /api/admin/incident/close("incident")
  # ═══════════════════════════════════════════════════════════════════════════
  def to_dict(self):
    return {
        # 식별·분류
        'id': self.id, 'title': self.title, 'src_ip': self.src_ip,
        'severity': self.severity, 'status': self.status,
        # 내용 — summary 는 줄바꿈이 든 긴 문자열 그대로(JSON 에서는 줄바꿈이 이스케이프되어 나간다)
        'summary': self.summary, 'event_count': self.event_count,
        'actions': self.actions, 'student': self.student,
        # 시각 — None 이면 isoformat() 을 부를 수 없으니 None(JSON null) 그대로
        #   created_at·updated_at 이 None 인 때: 아직 INSERT 전 / SQL 로 직접 넣어 NULL 인 행
        'created_at': self.created_at.isoformat() if self.created_at else None,
        'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        # closed_at 은 열린 티켓이면 항상 None
        'closed_at': self.closed_at.isoformat() if self.closed_at else None,
    }
